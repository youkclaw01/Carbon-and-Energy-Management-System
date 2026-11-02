#!/usr/bin/env python3
"""AMA 중앙 수신(central-ingest) v0.1: 공장 VM이 보내는 이벤트를 서명·스키마·중복 검사 후 받아 저장하고,
포털이 보는 사이트 요약·실시간 피드·시계열을 제공한다. 표준 라이브러리만 사용.
- 인증: X-AMA-Key-Id + HMAC-SHA256(timestamp + '.' + body). 키는 환경변수 FACTORY_KEYS(JSON)로만 받으며 출력·기록하지 않는다.
- 멱등: event_id(uuid5(site|epoch|seq))로 중복 제거, 같은 ID에 다른 내용이면 conflict로 격리한다.
- 저장: 메모리 링 버퍼(기본 6만 건) + 분 단위 집계. 재시작하면 사라지므로 영속 저장(Azure SQL/Blob)은 다음 단계다(합성 자료 전용)."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, json, time, hmac, hashlib, uuid, threading, collections, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
try:
    import db01; DB = db01.make()
except Exception as _e:
    DB = None; DB_ERR = str(_e)[:160]
NS = uuid.UUID('6f1c5d0a-3b7e-4e4e-9a52-0a11fac70001')
try: KEYS = json.loads(os.environ.get('FACTORY_KEYS', '{}'))
except Exception: KEYS = {}
RING = int(os.environ.get('INGEST_RING', '60000'))
TYPES = {'meter.reading', 'energy.flow', 'process.state', 'production.counter', 'production.workorder', 'alarm.event', 'shipment.dispatched', 'heartbeat'}
LOCK = threading.RLock(); START = time.time()
EVENTS = collections.deque(maxlen=RING); SEEN = collections.OrderedDict(); RID = 0
SITES = {}; META = dict(accepted=0, duplicates=0, rejected=0, auth_fail=0, batches=0, bytes=0)

# ---- 지역 영속 저장(Azure Blob append, 관리 ID 인증). STORE_URL이 없으면 메모리 전용 ----
import threading, urllib.request, urllib.error, queue, re as _re, datetime as _dt
STORE_URL = os.environ.get('STORE_URL', '').rstrip('/'); STORE_CONT = os.environ.get('STORE_CONTAINER', 'bronze')
STORE = dict(enabled=bool(STORE_URL), written=0, bytes=0, errors=0, last_err=None, restored=0, last_ok=None); SQ = queue.Queue(maxsize=20000); _TOK = {'v': None, 'exp': 0}
def _token():
    if _TOK['v'] and _TOK['exp'] - time.time() > 300: return _TOK['v']
    ep, hd = os.environ.get('IDENTITY_ENDPOINT'), os.environ.get('IDENTITY_HEADER')
    if not ep: raise RuntimeError('no managed identity endpoint')
    url = ep + '?resource=https://storage.azure.com/&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'X-IDENTITY-HEADER': hd}), timeout=10) as r: d = json.loads(r.read())
    _TOK['v'] = d['access_token']; _TOK['exp'] = float(d.get('expires_on', time.time() + 3000)); return _TOK['v']
def _blob(method, path, data=None, hdr=None, timeout=20, cont=None):
    h = {'Authorization': 'Bearer ' + _token(), 'x-ms-version': '2023-11-03', 'x-ms-date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}; h.update(hdr or {})
    rq = urllib.request.Request(STORE_URL + '/' + (cont or STORE_CONT) + path, data=data, method=method, headers=h)
    return urllib.request.urlopen(rq, timeout=timeout)
def _day(): return _dt.datetime.utcnow().strftime('%Y-%m-%d')
def store_loop():
    made = set()
    while True:
        batch = [SQ.get()]; t0 = time.time()
        while time.time() - t0 < 2 and len(batch) < 4000:
            try: batch.append(SQ.get(timeout=.5))
            except queue.Empty: break
        by = {}
        for sid, line in batch: by.setdefault(sid, []).append(line)
        for sid, lines in by.items():
            name = '/%s/%s.ndjson' % (sid, _day()); payload = ('\n'.join(lines) + '\n').encode()
            for att in range(4):
                try:
                    if name not in made:
                        try: _blob('PUT', name, b'', {'x-ms-blob-type': 'AppendBlob', 'If-None-Match': '*', 'Content-Length': '0'}).read()
                        except urllib.error.HTTPError as e:
                            if e.code != 409: raise
                        made.add(name)
                    for i in range(0, len(payload), 3 * 1024 * 1024): _blob('PUT', name + '?comp=appendblock', payload[i:i + 3 * 1024 * 1024], {'Content-Type': 'application/octet-stream'}).read()
                    STORE['written'] += len(lines); STORE['bytes'] += len(payload); STORE['last_ok'] = time.time(); break
                except Exception as e:
                    STORE['errors'] += 1; STORE['last_err'] = (type(e).__name__ + ': ' + str(e))[:140]; _TOK['v'] = None; time.sleep(1 + att * 2)
_MADE = set(); _MLOCK = threading.Lock()
def land(sid, lines):
    """접수한 줄을 지역 저장소(Blob append)에 내구 저장한다. 성공해야만 호출 쪽이 ACK한다(S01 설계: 저장 전 성공 ACK 금지). 실패하면 False."""
    name = '/%s/%s.ndjson' % (sid, _day()); payload = ('\n'.join(lines) + '\n').encode(); err = None
    for att in range(3):
        try:
            with _MLOCK:
                if name not in _MADE:
                    try: _blob('PUT', name, b'', {'x-ms-blob-type': 'AppendBlob', 'If-None-Match': '*', 'Content-Length': '0'}).read()
                    except urllib.error.HTTPError as e:
                        if e.code != 409: raise
                    _MADE.add(name)
            off = None
            for i in range(0, len(payload), 3 * 1024 * 1024):
                rs = _blob('PUT', name + '?comp=appendblock', payload[i:i + 3 * 1024 * 1024], {'Content-Type': 'application/octet-stream'}, timeout=15); rs.read()
                if off is None: off = rs.headers.get('x-ms-blob-append-offset')
            STORE['written'] += len(lines); STORE['bytes'] += len(payload); STORE['last_ok'] = time.time(); return True, '%s/%s%s@%s+%d' % (STORE_URL.split('//')[-1].split('.')[0], STORE_CONT, name, off, len(payload))
        except Exception as e:
            err = e; _TOK['v'] = None; time.sleep(.4 * (att + 1))
            with _MLOCK: _MADE.discard(name)
    STORE['errors'] += 1; STORE['last_err'] = (type(err).__name__ + ': ' + str(err))[:140]; return False, None
def restore():
    """재시작 후 오늘·어제 저장분(끝 8MB)을 읽어 상태를 복원한다."""
    global RID
    try:
        with _blob('GET', '?restype=container&comp=list&delimiter=%2F') as r: xml = r.read().decode()
        sites = _re.findall(r'<Name>([^<]+)/</Name>', xml)
        for sid in sites:
            for d in ((_dt.datetime.utcnow() - _dt.timedelta(days=1)).strftime('%Y-%m-%d'), _day()):
                try:
                    # Azure Blob은 접미 범위(bytes=-N)를 지원하지 않아 전체를 돌려주므로, 크기를 먼저 확인해 끝 8MB 구간을 명시한다.
                    with _blob('HEAD', '/%s/%s.ndjson' % (sid, d), None, None, 30) as r: size = int(r.headers.get('Content-Length', '0'))
                    if size <= 0: continue
                    start = max(0, size - 8388608)
                    with _blob('GET', '/%s/%s.ndjson' % (sid, d), None, {'Range': 'bytes=%d-%d' % (start, size - 1)}, 60) as r: raw = r.read().decode('utf-8', 'replace')
                except urllib.error.HTTPError as e:
                    if e.code in (404, 416): continue
                    raise
                lines = raw.split('\n')[1:] if raw and start > 0 else raw.split('\n')
                for ln in lines:
                    if not ln.strip(): continue
                    try: ev = json.loads(ln)
                    except Exception: continue
                    with LOCK:
                        if ev['event_id'] in SEEN: continue
                        SEEN[ev['event_id']] = hashlib.sha256(json.dumps([ev['type'], ev['ref'], ev['ts'], ev['payload']], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
                        RID += 1; rec = float(ev.pop('_recv', time.time())); EVENTS.append(dict(rid=RID, recv=rec, site=ev['site_id'], **ev)); apply(site(ev['site_id']), ev, rec); STORE['restored'] += 1
    except Exception as e: STORE['last_err'] = 'restore: ' + (type(e).__name__ + ': ' + str(e))[:120]

def site(sid):
    s = SITES.get(sid)
    if not s: s = SITES[sid] = dict(id=sid, first=time.time(), last=None, last_event_ts=None, count=0, dup=0, rej=0, by_type=collections.Counter(), latest={}, alarms={}, ship=collections.deque(maxlen=20), wo_done=collections.deque(maxlen=20), rate=collections.deque(maxlen=300), lag=collections.deque(maxlen=200), mins=collections.OrderedDict(), vm=None, epoch=None, last_seq=0, key_id=None, hb=None, q=dict(epoch=None, ranges=[], late=0, epochs=0, first=None, prev=None))
    return s

def q_add(q, seq, ep):
    """수신한 seq를 연속 구간(ranges)으로 합친다. 에포크가 바뀌면 이전 에포크 요약을 남기고 새로 시작한다. 결측을 0으로 채우지 않고 구간으로만 기록한다."""
    ep = str(ep)
    if q['epoch'] != ep:
        if q['epoch'] is not None: q['epochs'] += 1; q['prev'] = dict(epoch=q['epoch'], **q_view(q, 0))
        q.update(epoch=ep, ranges=[], first=seq)
    r = q['ranges']; mx = r[-1][1] if r else None
    if mx is not None and seq < mx: q['late'] += 1      # 더 큰 번호가 먼저 도착한 뒤 늦게 도착(재전송·역순)
    i = 0
    while i < len(r) and r[i][1] + 1 < seq: i += 1
    if i < len(r) and r[i][0] - 1 <= seq <= r[i][1] + 1:
        r[i][0] = min(r[i][0], seq); r[i][1] = max(r[i][1], seq)
        if i + 1 < len(r) and r[i + 1][0] - 1 <= r[i][1]: r[i][1] = max(r[i][1], r[i + 1][1]); del r[i + 1]
    else: r.insert(i, [seq, seq])
    if len(r) > 500: r[:] = r[-500:]                       # 오래된 구간은 버려 메모리 상한을 둔다
def q_view(q, lim=20):
    r = q['ranges']; gaps = [[r[i][1] + 1, r[i + 1][0] - 1] for i in range(len(r) - 1)]
    return dict(first_seq=r[0][0] if r else None, last_seq=r[-1][1] if r else None, missing=sum(b - a + 1 for a, b in gaps), gap_count=len(gaps), gaps=gaps[-lim:] if lim else [], late=q['late'])
def parse_ts(t):
    return time.mktime(time.strptime(t[:19], '%Y-%m-%dT%H:%M:%S')) - time.timezone + float('0' + t[19:-1]) if len(t) > 20 else time.mktime(time.strptime(t[:19], '%Y-%m-%dT%H:%M:%S')) - time.timezone
def verify(hdr, body):
    kid = hdr.get('X-AMA-Key-Id', ''); k = KEYS.get(kid)
    if not k: return None, 'unknown key'
    try: ts = int(hdr.get('X-AMA-Timestamp', '0'))
    except ValueError: return None, 'bad timestamp'
    if abs(time.time() - ts) > 300: return None, 'timestamp skew'
    exp = hmac.new(k['key'].encode(), str(ts).encode() + b'.' + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(exp, hdr.get('X-AMA-Signature', '')): return None, 'bad signature'
    return k, None
def check_event(ev, k, site_id):
    if ev.get('schema') != 'ama.factory.v1': return 'schema'
    if ev.get('site_id') != site_id or site_id != k['site']: return 'site mismatch'
    if ev.get('type') not in TYPES: return 'type not allowed'
    try: seq = int(ev['seq']); ep = str(ev['epoch'])
    except Exception: return 'seq/epoch'
    if ev.get('event_id') != str(uuid.uuid5(NS, '%s|%s|%d' % (site_id, ep, seq))): return 'event_id mismatch'
    if not isinstance(ev.get('payload'), dict) or len(json.dumps(ev['payload'])) > 4096: return 'payload'
    return None
def apply(s, ev, now):
    q_add(s['q'], int(ev['seq']), ev['epoch'])
    s['count'] += 1; s['by_type'][ev['type']] += 1; s['last'] = now; s['last_event_ts'] = ev['ts']; s['last_seq'] = ev['seq']; s['epoch'] = ev['epoch']; s['vm'] = ev.get('source', {}).get('vm')
    s['rate'].append(now); t = parse_ts(ev['ts']); s['lag'].append(max(0.0, now - t))
    ty, ref, pl = ev['type'], ev['ref'], ev['payload']
    s['latest'][(ty, ref)] = dict(ts=ev['ts'], seq=ev['seq'], payload=pl)
    if ty == 'alarm.event':
        aid = pl.get('alarm_id'); a = s['alarms'].get(aid) or dict(id=aid, equip=ref, code=pl.get('code'), msg=pl.get('msg'), sev=pl.get('sev'), raised=None, cleared=None, state='ACTIVE')
        if pl.get('action') == 'RAISED': a.update(raised=ev['ts'], state='ACTIVE', msg=pl.get('msg') or a['msg'])
        elif pl.get('action') == 'CLEARED': a.update(cleared=ev['ts'], state='CLEARED')
        s['alarms'][aid] = a
        if len(s['alarms']) > 200: s['alarms'].pop(next(iter(s['alarms'])))
    elif ty == 'shipment.dispatched': s['ship'].appendleft(dict(ts=ev['ts'], **pl))
    elif ty == 'production.workorder' and pl.get('action') == 'COMPLETED': s['wo_done'].appendleft(dict(ts=ev['ts'], line=ref, **pl))
    elif ty == 'heartbeat': s['hb'] = dict(ts=ev['ts'], **pl)
    m = int(t // 60) * 60; r = s['mins'].get(m)     # 분 단위 집계는 수신 시각이 아니라 이벤트 발생 시각의 분으로 묶는다(묶음 전송이어도 분별 값이 정확)
    if not r:
        r = s['mins'][m] = dict(t=m, n=0, lag=0.0, flow_n=0, demand=0.0, grid=0.0, solar=0.0, ppa=0.0, co2=0.0, batt=0.0)
        while len(s['mins']) > 720: s['mins'].pop(min(s['mins']))
    r['n'] += 1; r['lag'] += s['lag'][-1]
    if ty == 'energy.flow':
        r['flow_n'] += 1
        for kx, ky in (('demand', 'demand'), ('grid', 'grid'), ('solar', 'solar'), ('ppa', 'ppa'), ('co2', 'co2_kg_h'), ('batt', 'batt')): r[kx] += pl.get(ky, 0)
def ingest(hdr, body):
    global RID
    k, err = verify(hdr, body)
    if err:
        with LOCK: META['auth_fail'] += 1
        return 401, {'error': err}
    try: doc = json.loads(body)
    except Exception: return 400, {'error': 'bad json'}
    sid = doc.get('site_id'); evs = doc.get('events') or []
    if sid != k['site'] or not isinstance(evs, list) or len(evs) > 200: return 400, {'error': 'bad batch'}
    acc = dup = 0; rej = []; now = time.time(); bseen = {}; newev = []
    with LOCK:
        s = site(sid); s['key_id'] = hdr.get('X-AMA-Key-Id'); META['batches'] += 1; META['bytes'] += len(body)
        for ev in evs:
            st = ev.get('ref') == 'SELFTEST' and isinstance(ev, dict)      # 자체 시험 이벤트: 검증 결과는 돌려주되 사이트 통계·피드에 넣지 않는다
            if st:
                e = check_event(ev, k, sid)
                if e: rej.append(dict(event_id=ev.get('event_id'), reason=e)); META['selftest_rejected'] = META.get('selftest_rejected', 0) + 1; continue
                h0 = hashlib.sha256(json.dumps([ev['type'], ev['ref'], ev['ts'], ev['payload']], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]; prev = SEEN.get(ev['event_id'])
                if prev is None: SEEN[ev['event_id']] = h0; acc += 1
                elif prev == h0: dup += 1
                else: rej.append(dict(event_id=ev['event_id'], reason='conflict'))
                continue
            e = check_event(ev, k, sid)
            if e: rej.append(dict(event_id=ev.get('event_id'), reason=e)); s['rej'] += 1; META['rejected'] += 1; continue
            h = hashlib.sha256(json.dumps([ev['type'], ev['ref'], ev['ts'], ev['payload']], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
            prev = SEEN.get(ev['event_id'])
            if prev is not None:
                if prev == h: dup += 1; s['dup'] += 1; META['duplicates'] += 1
                else: rej.append(dict(event_id=ev['event_id'], reason='conflict')); s['rej'] += 1; META['rejected'] += 1
                continue
            if ev['event_id'] in bseen:
                if bseen[ev['event_id']] == h: dup += 1; s['dup'] += 1; META['duplicates'] += 1
                else: rej.append(dict(event_id=ev['event_id'], reason='conflict')); s['rej'] += 1; META['rejected'] += 1
                continue
            bseen[ev['event_id']] = h; newev.append((ev, h))
    # 1단계(분류) 끝: 새 이벤트를 먼저 저장소에 내구 저장한다. 저장 실패 시 메모리에 반영하지 않고 503으로 돌려 보내 공장이 같은 event_id로 재전송하게 한다.
    if newev and STORE['enabled']:
        lines = [json.dumps(dict(ev, _recv=round(now, 3)), ensure_ascii=False, separators=(',', ':')) for ev, _ in newev]
        ok, ref = land(sid, lines)
        if not ok: return 503, {'error': 'storage unavailable', 'retryable': True}
        if DB:      # 접수 메타데이터(DB01)를 LANDED+outbox+audit 한 트랜잭션으로 확정한 뒤에만 ACK한다. 실패하면 503(원문은 Bronze에 남고 재전송분은 Silver에서 event_id로 제거)
            try:
                seqs = [int(ev['seq']) for ev, _ in newev]
                DB.record(sid=sid, epoch=str(newev[0][0]['epoch']), first=min(seqs), last=max(seqs), count=len(newev), dup=dup, rej=len(rej), req_digest=hashlib.sha256(body).hexdigest(),
                          raw_digest=hashlib.sha256('\n'.join(lines).encode()).hexdigest(), raw_ref=ref, last_ts=max(ev['ts'] for ev, _ in newev), now=now)
            except Exception as e:
                META['db_errors'] = META.get('db_errors', 0) + 1; META['db_last_err'] = (type(e).__name__ + ': ' + str(e))[:140]
                return 503, {'error': 'metadata store unavailable', 'retryable': True}
    with LOCK:
        s = site(sid)
        for ev, h in newev:
            if SEEN.get(ev['event_id']) is not None: dup += 1; s['dup'] += 1; META['duplicates'] += 1; continue    # 동시 요청이 먼저 반영한 경우
            SEEN[ev['event_id']] = h
            if len(SEEN) > 300000: SEEN.popitem(last=False)
            RID += 1; EVENTS.append(dict(rid=RID, recv=now, site=sid, **ev)); apply(s, ev, now); acc += 1; META['accepted'] += 1
    if rej and DB:      # 격리: 검증 실패·충돌 이벤트의 이유·범위·건수를 DB01에 QUARANTINED로 남긴다(원문은 공장 outbox 보관). 실패해도 응답은 막지 않는다
        try:
            byid = {e.get('event_id'): e for e in evs if isinstance(e, dict)}; rs = [(byid.get(r['event_id']), r['reason']) for r in rej]; seqs = [int(e['seq']) for e, _ in rs if e and str(e.get('seq', '')).lstrip('-').isdigit()] or [0]
            reasons = {}
            for _, r_ in rs: reasons[r_] = reasons.get(r_, 0) + 1
            top = max(reasons, key=reasons.get); ep = str(next((e.get('epoch') for e, _ in rs if e and e.get('epoch')), doc.get('epoch') or ''))
            DB.quarantine(sid=sid, epoch=ep, first=min(seqs), last=max(seqs), count=len(rs), reason=top if len(reasons) == 1 else top + ' (+%d종)' % (len(reasons) - 1), req_digest=hashlib.sha256(body).hexdigest(), ids_digest=hashlib.sha256(','.join(sorted(str(r['event_id']) for r in rej)).encode()).hexdigest(), now=now)
        except Exception as e: META['db_q_errors'] = META.get('db_q_errors', 0) + 1; META['db_last_err'] = ('quarantine ' + type(e).__name__ + ': ' + str(e))[:140]
    return 200, dict(accepted=acc, duplicates=dup, rejected=rej, server_ts=now, last_rid=RID)
def rate(s, win=60):
    now = time.time(); n = sum(1 for t in s['rate'] if now - t <= win); return round(n / win, 2)
# 공장 VM은 초 단위로 수집하고 분 단위(기본 60초)로 묶어 보낸다. 상태 기준은 전송 주기에 맞춰 ONLINE<90초, DELAYED<240초(환경변수로 조정).
ONLINE_S = float(os.environ.get('ONLINE_S', '90')); DELAYED_S = float(os.environ.get('DELAYED_S', '240'))
def site_brief(s):
    now = time.time(); age = (now - s['last']) if s['last'] else None; lag = list(s['lag'])
    return dict(id=s['id'], vm=s['vm'], status=('ONLINE' if age is not None and age < ONLINE_S else ('DELAYED' if age is not None and age < DELAYED_S else 'OFFLINE')), age_s=round(age, 1) if age is not None else None, count=s['count'], dup=s['dup'], rejected=s['rej'], per_s=rate(s), lag_ms=round(1000 * sum(lag) / len(lag)) if lag else None, last_seq=s['last_seq'], epoch=s['epoch'], quality=dict(q_view(s['q'], 0), epochs=s['q']['epochs']), key_id=s['key_id'], by_type=dict(s['by_type']), hb=s['hb'], first=s['first'])
def summary(s):
    L = s['latest']; en = (L.get(('energy.flow', 'SITE')) or {}).get('payload', {})
    eq = {}
    for (ty, ref), v in L.items():
        if ty == 'process.state': eq.setdefault(ref, {}).update(v['payload'], ts=v['ts'])
        if ty == 'meter.reading': eq.setdefault(ref[2:], {}).update(kw=v['payload']['kw'], kwh_total=v['payload']['kwh_total'], mts=v['ts'])
    wos = [dict(line=ref, **v['payload'], ts=v['ts']) for (ty, ref), v in L.items() if ty == 'production.counter']
    return dict(brief=site_brief(s), energy=en, equipment=[dict(id=k, **v) for k, v in sorted(eq.items())], workorders=wos, alarms=sorted(s['alarms'].values(), key=lambda a: a.get('raised') or '', reverse=True)[:30], shipments=list(s['ship'])[:10], completed=list(s['wo_done'])[:10])
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/v1/events':
            n = int(self.headers.get('Content-Length', '0') or 0)
            if n <= 0 or n > 600 * 1024: return self.out(413, {'error': 'bad size'})
            code, obj = ingest(self.headers, self.rfile.read(n)); return self.out(code, obj)
        self.out(404, {'error': 'not found'})
    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; parts = [x for x in u.path.split('/') if x]
        if u.path in ('/healthz', '/v1/health'): return self.out(200, {'ok': True, 'uptime_s': int(time.time() - START), 'sites': len(SITES), 'keys': len(KEYS), 'store': STORE['enabled']})
        if u.path == '/v1/stats':
            with LOCK: return self.out(200, dict(META, store=dict(STORE, queued=SQ.qsize()), db=(DB.stats() if DB else None), ring=len(EVENTS), ring_max=RING, seen=len(SEEN), rid=RID, uptime_s=int(time.time() - START)))
        if u.path == '/v1/sites':
            with LOCK: return self.out(200, dict(sites=[site_brief(s) for s in SITES.values()], stats=dict(META, rid=RID, ring=len(EVENTS))))
        if len(parts) >= 3 and parts[:2] == ['v1', 'sites']:
            with LOCK:
                s = SITES.get(parts[2])
                if not s: return self.out(404, {'error': 'unknown site'})
                tail = parts[3] if len(parts) > 3 else 'summary'
                if tail == 'summary': return self.out(200, summary(s))
                if tail == 'quality': return self.out(200, dict(site=s['id'], epoch=s['q']['epoch'], epochs=s['q']['epochs'], received=s['count'], duplicates=s['dup'], rejected=s['rej'], prev_epoch=s['q']['prev'], note='결측(missing)은 수신하지 못한 seq이며 0으로 채우지 않는다. late는 더 큰 seq 뒤에 늦게 도착한 건수(재전송·역순). 재시작 복원 시 최근 저장분(끝 8MB) 범위만 추적한다.', **q_view(s['q'], 50)))
                if tail == 'gold':
                    if not STORE['enabled']: return self.out(200, {'error': 'store disabled'})
                    try:
                        with _blob('GET', '/api/%s/summary.json' % parts[2], None, None, 15, 'gold') as r: return self.out(200, json.loads(r.read()))
                    except urllib.error.HTTPError as e: return self.out(200, {'error': 'gold not ready' if e.code == 404 else 'HTTP %d' % e.code})
                    except Exception as e: return self.out(200, {'error': (type(e).__name__ + ': ' + str(e))[:100]})
                if tail == 'feed':
                    after = int(q.get('after', '0')); lim = min(int(q.get('limit', '60')), 300); typ = q.get('type')
                    rows = [e for e in EVENTS if e['site'] == parts[2] and e['rid'] > after and (not typ or e['type'] == typ)]
                    if after == 0: rows = rows[-lim:]
                    else: rows = rows[:lim]
                    return self.out(200, dict(events=[dict(rid=e['rid'], recv=e['recv'], ts=e['ts'], seq=e['seq'], type=e['type'], ref=e['ref'], id=e['event_id'][:8], payload=e['payload'], lag_ms=round(1000 * (e['recv'] - parse_ts(e['ts'])))) for e in rows], last_rid=RID))
                if tail == 'series':
                    m = int(q.get('minutes', '60')); rows = sorted([r for r in s['mins'].values() if r['t'] >= time.time() - m * 60 - 60], key=lambda r: r['t'])
                    return self.out(200, [dict(t=r['t'], n=r['n'], lag_ms=round(1000 * r['lag'] / r['n']) if r['n'] else 0, demand=round(r['demand'] / r['flow_n'], 1) if r['flow_n'] else None, grid=round(r['grid'] / r['flow_n'], 1) if r['flow_n'] else None, solar=round(r['solar'] / r['flow_n'], 1) if r['flow_n'] else None, ppa=round(r['ppa'] / r['flow_n'], 1) if r['flow_n'] else None, co2=round(r['co2'] / r['flow_n'], 1) if r['flow_n'] else None) for r in rows])
        self.out(404, {'error': 'not found'})
if __name__ == '__main__':
    print('central-ingest keys=%d ring=%d store=%s' % (len(KEYS), RING, STORE['enabled']), flush=True)
    if STORE['enabled']:
        restore(); print('restored', STORE['restored'], STORE['last_err'], flush=True); threading.Thread(target=store_loop, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
