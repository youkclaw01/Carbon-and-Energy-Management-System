#!/usr/bin/env python3
"""AMA 가상 공장 VM 앱: 운전 시뮬레이터 + 현장 운영 화면(웹) + 영속 outbox 송신기. 표준 라이브러리만 사용(VM은 외부 인터넷이 막혀 있음).
모든 자료는 합성이며 mode=SIMULATED로 표기한다. 재전송은 원 event_id를 유지하고 중앙은 event_id로 중복을 제거한다."""
import os, sys, json, time, sqlite3, threading, hmac, hashlib, uuid, urllib.request, urllib.error, collections, socket, re, resource
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim
CFG_PATH = os.environ.get('AMAFACTORY_CONFIG', '/etc/amafactory/config.json')
CFG = {'site_id': 'KR-01', 'site_name': '울산', 'vm': socket.gethostname(), 'seed': 20261030, 'ingest_url': '', 'key_id': 'kr01-k1', 'key_file': '/etc/amafactory/site.key', 'data_dir': '/var/lib/amafactory', 'port': 8080, 'tick_s': 1.0, 'collect_s': 1, 'send_interval_s': 60, 'batch_max': 200, 'bind': '0.0.0.0', 'tz': 'Asia/Seoul', 'tz_hours': 9, 'ef_grid': 0.4594}
if os.path.exists(CFG_PATH): CFG.update(json.load(open(CFG_PATH)))
for k_env, k in (('AMAFACTORY_INGEST', 'ingest_url'), ('AMAFACTORY_DATA', 'data_dir'), ('AMAFACTORY_PORT', 'port')):
    if os.environ.get(k_env): CFG[k] = os.environ[k_env]
CFG['port'] = int(CFG['port'])
KEY = (open(CFG['key_file'], 'rb').read().strip() if os.path.exists(CFG['key_file']) else os.environ.get('AMAFACTORY_KEY', 'dev-key').encode())
os.makedirs(CFG['data_dir'], exist_ok=True)
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui')
START = time.time(); NS = uuid.UUID('6f1c5d0a-3b7e-4e4e-9a52-0a11fac70001')
sim.configure(float(CFG['tz_hours']), float(CFG['ef_grid']))
if CFG.get('steel'): sim.configure_steel(CFG['steel']['kw'], CFG['steel']['gas'], CFG['steel']['prod'], CFG['steel'].get('kind', 'mill'))   # 철강 데모 프로필(없으면 기존 소규모 공장)
LOCK = threading.RLock(); PLANT = sim.Plant(CFG['site_id'], CFG['site_name'], CFG['seed'])
EPOCH = None; SEQ = 0
DB = sqlite3.connect(os.path.join(CFG['data_dir'], 'outbox.db'), check_same_thread=False, isolation_level=None)
DB.execute('PRAGMA journal_mode=WAL'); DB.execute('PRAGMA synchronous=NORMAL')
DB.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
DB.execute('CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE, etype TEXT, ref TEXT, body TEXT, created REAL, state TEXT, tries INTEGER DEFAULT 0, next_try REAL DEFAULT 0, acked REAL, ack_ms REAL, err TEXT)')
DB.execute('CREATE INDEX IF NOT EXISTS ix_state ON outbox(state, next_try)')
def meta(k, v=None):
    if v is None:
        r = DB.execute('SELECT v FROM meta WHERE k=?', (k,)).fetchone(); return r[0] if r else None
    DB.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (k, str(v)))
EPOCH = meta('epoch') or str(int(START)); meta('epoch', EPOCH)
SEQ = DB.execute('SELECT COALESCE(MAX(seq),0) FROM outbox').fetchone()[0]
STATS = dict(sent=0, acked=0, dup=0, rejected=0, fail=0, last_ok=None, last_err=None, rtt_ms=[], conn='INIT', bytes=0)
RECENT = collections.deque(maxlen=400)     # 화면용 전송 로그
PERIOD = {'meter.reading': CFG['collect_s'], 'energy.flow': CFG['collect_s'], 'process.state': 10, 'production.counter': 30, 'heartbeat': 15}
NEXT = collections.defaultdict(float)

def iso(ts): return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ts)) + '.%03dZ' % int((ts % 1) * 1000)
def emit(etype, ref, payload, ts):
    global SEQ
    SEQ += 1; eid = str(uuid.uuid5(NS, '%s|%s|%d' % (CFG['site_id'], EPOCH, SEQ)))
    ev = dict(schema='ama.factory.v1', event_id=eid, site_id=CFG['site_id'], epoch=EPOCH, seq=SEQ, ts=iso(ts), type=etype, ref=ref, payload=payload,
              source=dict(vm=CFG['vm'], mode='SIMULATED', generator='amafactory/0.1', seed=CFG['seed']))
    body = json.dumps(ev, ensure_ascii=False, separators=(',', ':'))
    DB.execute('INSERT INTO outbox(seq,event_id,etype,ref,body,created,state) VALUES(?,?,?,?,?,?,?)', (SEQ, eid, etype, ref, body, ts, 'pending'))
    RECENT.appendleft(dict(seq=SEQ, id=eid[:8], type=etype, ref=ref, ts=iso(ts), size=len(body), state='pending', tries=0, ack_ms=None, payload=payload))
    return ev
def gen_events(now, discrete):
    P = PLANT; evs = []
    for (t, ref, pl) in discrete: evs.append(emit(t, ref, pl, now))
    if now >= NEXT['meter.reading']:
        NEXT['meter.reading'] = now + PERIOD['meter.reading']
        for e in P.eq.values(): evs.append(emit('meter.reading', 'M-' + e['id'], dict(equip=e['id'], kw=round(e['kw'], 2), kwh_total=round(e['kwh'], 2), state=e['state']), now))
    if now >= NEXT['energy.flow']:
        NEXT['energy.flow'] = now + PERIOD['energy.flow']; g = P.energy
        evs.append(emit('energy.flow', 'SITE', {k: round(g[k], 2) for k in ('demand', 'grid', 'solar', 'ppa', 'batt', 'soc', 'co2_kg_h', 'scope1', 'scope2', 'whr_kw', 'gas_nm3h', 'water_m3h')}, now))
    if now >= NEXT['process.state']:
        NEXT['process.state'] = now + PERIOD['process.state']
        for e in P.eq.values(): evs.append(emit('process.state', e['id'], dict(state=e['state'], speed=round(e['speed'], 2), temp=round(e['temp'], 1), pressure=round(e['pressure'], 2), line=e['line'], fault=e['fault']), now))
    if now >= NEXT['production.counter']:
        NEXT['production.counter'] = now + PERIOD['production.counter']
        for ln, w in P.wo.items(): evs.append(emit('production.counter', ln, dict(wo=w['id'], product=w['product'], done=round(w['done'], 1), scrap=round(w['scrap'], 1), target=w['target'], unit=w['unit'], status=w['status']), now))
    if now >= NEXT['heartbeat']:
        NEXT['heartbeat'] = now + PERIOD['heartbeat']
        evs.append(emit('heartbeat', 'VM', dict(uptime_s=int(now - START), outbox_pending=DB.execute("SELECT COUNT(*) FROM outbox WHERE state='pending'").fetchone()[0], rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1), load1=round(os.getloadavg()[0], 2)), now))
    return evs
def sim_loop():
    while True:
        t0 = time.time()
        with LOCK:
            try: gen_events(t0, PLANT.step(t0))
            except Exception as e: STATS['last_err'] = 'sim:' + str(e)[:80]
        time.sleep(max(.2, CFG['tick_s'] - (time.time() - t0)))
def sign(ts, body): return hmac.new(KEY, ts.encode() + b'.' + body, hashlib.sha256).hexdigest()
def sender_loop():
    """수집은 초 단위(VM 내부), 중앙 전송은 분 단위(send_interval_s, 기본 60초). 전송 시각이 되면 대기 이벤트를 batch_max(중앙 한도 200)씩 모두 비운다.
    실패하면 지수 백오프로 재시도하고, 재시도 중에도 이벤트는 영속 outbox에 계속 쌓인다(원 event_id 유지, 중앙이 중복 제거)."""
    backoff = 1.0; every = max(5.0, float(CFG['send_interval_s'])); nmax = min(200, int(CFG['batch_max'])); STATS['next_send'] = time.time() + every
    while True:
        try:
            if not CFG['ingest_url']: STATS['conn'] = 'NO_ENDPOINT'; time.sleep(2); continue
            if time.time() < STATS['next_send']: time.sleep(min(1.0, max(0.05, STATS['next_send'] - time.time()))); continue
            rows = DB.execute("SELECT seq,event_id,body FROM outbox WHERE state='pending' AND next_try<=? ORDER BY seq LIMIT ?", (time.time(), nmax)).fetchall()
            if not rows: STATS['next_send'] = time.time() + every; STATS['conn'] = STATS['conn'] if STATS['conn'] != 'NO_ENDPOINT' else 'ONLINE'; continue
            body = ('{"site_id":"%s","epoch":"%s","events":[%s]}' % (CFG['site_id'], EPOCH, ','.join(r[2] for r in rows))).encode()
            ts = str(int(time.time())); t0 = time.time()
            rq = urllib.request.Request(CFG['ingest_url'].rstrip('/') + '/v1/events', data=body, method='POST', headers={'Content-Type': 'application/json', 'X-AMA-Site': CFG['site_id'], 'X-AMA-Key-Id': CFG['key_id'], 'X-AMA-Timestamp': ts, 'X-AMA-Signature': sign(ts, body)})
            for r in rows: DB.execute('UPDATE outbox SET tries=tries+1 WHERE seq=?', (r[0],))
            STATS['sent'] += len(rows); STATS['bytes'] += len(body)
            with urllib.request.urlopen(rq, timeout=15) as resp: ans = json.loads(resp.read())
            ms = (time.time() - t0) * 1000; STATS['rtt_ms'] = (STATS['rtt_ms'] + [ms])[-50:]; STATS['conn'] = 'ONLINE'; STATS['last_ok'] = time.time(); backoff = 1.0
            rej = {x['event_id']: x.get('reason') for x in ans.get('rejected', [])}; now = time.time()
            for (seq, eid, _) in rows:
                if eid in rej: DB.execute("UPDATE outbox SET state='rejected', err=? WHERE seq=?", (str(rej[eid])[:120], seq)); STATS['rejected'] += 1; st = 'rejected'
                else: DB.execute("UPDATE outbox SET state='acked', acked=?, ack_ms=? WHERE seq=?", (now, ms, seq)); STATS['acked'] += 1; st = 'acked'
                for rc in RECENT:
                    if rc['seq'] == seq: rc.update(state=st, ack_ms=round(ms, 1), tries=rc['tries'] + 1); break
            STATS['dup'] += ans.get('duplicates', 0)
            if len(rows) == nmax: continue     # 아직 남았으면 같은 전송 주기 안에서 계속 비운다
            STATS['next_send'] = time.time() + every
        except Exception as e:
            STATS['fail'] += 1; STATS['conn'] = 'OFFLINE'; STATS['last_err'] = (type(e).__name__ + ': ' + str(e))[:140]
            t = time.time() + backoff
            DB.execute("UPDATE outbox SET next_try=? WHERE state='pending'", (t,)); backoff = min(30.0, backoff * 2); time.sleep(min(backoff, 5))
        if int(time.time()) % 600 == 0: DB.execute("DELETE FROM outbox WHERE state='acked' AND acked<?", (time.time() - 86400,))
def outbox_info():
    r = DB.execute("SELECT SUM(state='pending'), SUM(state='acked'), SUM(state='rejected'), COUNT(*), MIN(CASE WHEN state='pending' THEN created END), MAX(CASE WHEN state='acked' THEN seq END) FROM outbox").fetchone()
    pend = r[0] or 0; rtt = STATS['rtt_ms']
    return dict(pending=pend, acked=r[1] or 0, rejected=r[2] or 0, total=r[3] or 0, oldest_pending_s=round(time.time() - r[4], 1) if r[4] else 0, last_acked_seq=r[5] or 0, seq=SEQ, epoch=EPOCH, conn=STATS['conn'], last_ok=STATS['last_ok'], last_err=STATS['last_err'],
                sent=STATS['sent'], send_interval_s=CFG['send_interval_s'], collect_s=CFG['collect_s'], next_send_in_s=max(0, round(STATS.get('next_send', 0) - time.time(), 1)), dup=STATS['dup'], fail=STATS['fail'], bytes=STATS['bytes'], rtt_avg=round(sum(rtt) / len(rtt), 1) if rtt else None, rtt_last=round(rtt[-1], 1) if rtt else None, endpoint=re.sub(r'^https?://', '', CFG['ingest_url']) or None, key_id=CFG['key_id'])
def sysinfo():
    try: mem = {l.split(':')[0]: int(l.split()[1]) for l in open('/proc/meminfo').read().splitlines()[:5]}
    except Exception: mem = {}
    st = os.statvfs(CFG['data_dir']); return dict(vm=CFG['vm'], uptime_s=int(time.time() - START), load=[round(x, 2) for x in os.getloadavg()], mem_total_mb=round(mem.get('MemTotal', 0) / 1024), mem_avail_mb=round(mem.get('MemAvailable', 0) / 1024), disk_free_gb=round(st.f_bavail * st.f_frsize / 1e9, 1), disk_total_gb=round(st.f_blocks * st.f_frsize / 1e9, 1), pid=os.getpid(), py=sys.version.split()[0], data_dir=CFG['data_dir'], seed=CFG['seed'], mode='SIMULATED', version='0.1')
MIME = {'.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8'}
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def out(self, code, body, ctype='application/json; charset=utf-8'):
        b = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; p = u.path
        base = re.match(r'^/plant-vm/[^/]+', p)
        if base: p = p[len(base.group(0)):] or '/'      # 포털이 /plant-vm/<site>/ 로 프록시해도 동작
        if p in ('/healthz', '/api/health'): return self.out(200, {'ok': True, 'site': CFG['site_id'], 'conn': STATS['conn'], 'seq': SEQ})
        if p == '/api/state':
            with LOCK: return self.out(200, dict(PLANT.snapshot(), cfg=dict(site_id=CFG['site_id'], site_name=CFG['site_name'], vm=CFG['vm'], mode='SIMULATED', tz=CFG['tz'], ef_grid=CFG['ef_grid']), outbox=outbox_info()))
        if p == '/api/history':
            with LOCK: return self.out(200, list(PLANT.hist))
        if p == '/api/outbox':
            n = int(q.get('n', '60')); return self.out(200, dict(info=outbox_info(), recent=list(RECENT)[:n], rates=dict(per_min=sum(1 for r in list(RECENT) if time.time() - time.mktime(time.strptime(r['ts'][:19], '%Y-%m-%dT%H:%M:%S')) + time.timezone < 60))))
        if p == '/api/events':
            after = int(q.get('after', '0')); lim = min(int(q.get('limit', '80')), 300)
            return self.out(200, dict(events=[r for r in list(RECENT) if r['seq'] > after][:lim], seq=SEQ))
        if p == '/api/system': return self.out(200, sysinfo())
        if p == '/api/central':
            if not CFG['ingest_url']: return self.out(200, {'error': 'endpoint not set'})
            try:
                with urllib.request.urlopen(CFG['ingest_url'].rstrip('/') + '/v1/sites/%s/summary' % CFG['site_id'], timeout=4) as r: d = json.loads(r.read())
                return self.out(200, {'brief': d.get('brief')})
            except Exception as e: return self.out(200, {'error': (type(e).__name__ + ': ' + str(e))[:100]})
        if p in ('/', '/index.html'): p = '/index.html'
        fp = os.path.realpath(os.path.join(UI_DIR, p.lstrip('/')))
        if fp.startswith(os.path.realpath(UI_DIR) + os.sep) and os.path.isfile(fp): return self.out(200, open(fp, 'rb').read(), MIME.get(os.path.splitext(fp)[1], 'application/octet-stream'))
        self.out(404, {'error': 'not found'})
if __name__ == '__main__':
    threading.Thread(target=sim_loop, daemon=True).start(); threading.Thread(target=sender_loop, daemon=True).start()
    print('amafactory', CFG['site_id'], 'port', CFG['port'], 'ingest', CFG['ingest_url'] or '-', flush=True)
    ThreadingHTTPServer((CFG['bind'], CFG['port']), H).serve_forever()
