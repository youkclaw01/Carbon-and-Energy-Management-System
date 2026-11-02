#!/usr/bin/env python3
"""KRX 배출권 시장 일별매매정보 수집·제공 서비스(표준 라이브러리만 사용).
- 인증키는 환경변수 KRX_AUTH_KEY(Key Vault 참조)로만 받으며 출력·기록하지 않는다.
- 시작 시 최근 N일(기본 420일)을 일별로 받아 메모리·/tmp에 저장하고, 이후 6시간마다 최근 10일을 갱신한다.
- 브라우저는 /api/krx/* (같은 도메인, nginx 프록시)만 호출한다. 자료는 KRX 일별 종가 기준이며 실시간이 아니다."""
import json, os, threading, time, urllib.request, urllib.error
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
try:
    import report_service
except Exception as _e:   # python-pptx 등이 없어도 KRX 시세는 계속 제공
    report_service = None; REPORT_ERR = str(_e)[:200]

URL = 'https://data-dbg.krx.co.kr/svc/apis/gen/ets_bydd_trd'
try:
    import ai_insights
except Exception as _e2:
    ai_insights = None; AI_ERR = str(_e2)[:200]
KEY = os.environ.get('KRX_AUTH_KEY', '').strip()
DAYS = int(os.environ.get('KRX_BACKFILL_DAYS', '420'))
CACHE = os.environ.get('KRX_CACHE', '/tmp/krx-cache.json')
SEED = os.environ.get('KRX_SEED', '/app/seed.json')  # 이미지에 넣어 둔 공개 시세 스냅샷(비밀 없음). 실시간 갱신이 막혀도 이 자료로 먼저 응답한다.
DATA = {}     # 'YYYYMMDD' -> {code: row}
META = {'state': 'starting', 'last_ok': None, 'calls': 0, 'errors': 0, 'asof': None, 'backfilled': 0, 'last_err': None, 'key_set': bool(KEY)}
LOCK = threading.Lock()

def num(x):
    try: return float(str(x).replace(',', ''))
    except Exception: return None

def fetch(day):
    r = urllib.request.Request(URL, data=json.dumps({'basDd': day}).encode(), method='POST',
        headers={'AUTH_KEY': KEY, 'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(r, timeout=30) as x: return json.load(x).get('OutBlock_1', [])

def store(day, rows):
    out = {}
    for r in rows:
        c = r.get('ISU_NM')
        if not c: continue
        out[c] = {'n': c, 'cd': r.get('ISU_CD'), 'o': num(r.get('TDD_OPNPRC')), 'h': num(r.get('TDD_HGPRC')), 'l': num(r.get('TDD_LWPRC')),
                  'c': num(r.get('TDD_CLSPRC')), 'chg': num(r.get('CMPPREVDD_PRC')), 'rt': num(r.get('FLUC_RT')), 'v': num(r.get('ACC_TRDVOL')), 'val': num(r.get('ACC_TRDVAL'))}
    if out:
        with LOCK: DATA[day] = out

def pull(days_back, pause=0.12):
    today = datetime.now(timezone(timedelta(hours=9))).date(); n = 0; bad = 0
    for i in range(days_back, -1, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5: continue
        day = d.strftime('%Y%m%d')
        with LOCK:
            have = day in DATA and i > 10
        if have: continue
        try:
            rows = fetch(day); META['calls'] += 1; store(day, rows); n += 1; bad = 0
        except urllib.error.HTTPError as e:
            META['errors'] += 1; META['last_err'] = 'HTTP %s' % e.code
            if e.code in (401, 403): META['state'] = 'auth-error'; return
            time.sleep(2)
        except Exception as e:
            META['errors'] += 1; bad += 1; META['last_err'] = (type(e).__name__ + ': ' + str(e))[:160]; time.sleep(2)
            if bad >= 3: return n
        time.sleep(pause)
    return n

def save():
    try:
        with LOCK: snap = dict(DATA)
        with open(CACHE, 'w') as f: json.dump(snap, f)
    except Exception: pass

def load():
    for p in (SEED, CACHE):
        try:
            with open(p) as f: d = json.load(f)
            with LOCK: DATA.update(d)
        except Exception: pass

def refresh_meta():
    with LOCK: ds = sorted(DATA)
    META['asof'] = ds[-1] if ds else None; META['backfilled'] = len(ds)

def worker():
    load(); refresh_meta()
    if not KEY:
        META['state'] = 'snapshot' if DATA else 'no-key'; return
    META['state'] = 'backfilling' if not DATA else 'snapshot'
    while META['state'] != 'auth-error':
        n = pull(DAYS) or 0; save(); refresh_meta()
        if META['state'] == 'auth-error': break
        if n > 0: META['state'] = 'ready'; META['last_ok'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        elif DATA: META['state'] = 'snapshot'
        time.sleep(6 * 3600 if META['state'] == 'ready' else 600)

def series(code, d_from, d_to):
    with LOCK: items = [(d, v[code]) for d, v in sorted(DATA.items()) if code in v and (not d_from or d >= d_from) and (not d_to or d <= d_to)]
    return [{'d': d, 'o': r['o'], 'h': r['h'], 'l': r['l'], 'c': r['c'], 'v': r['v'], 'val': r['val'], 'chg': r['chg'], 'rt': r['rt']} for d, r in items]

def products():
    with LOCK: ds = sorted(DATA)
    if not ds: return []
    last = DATA[ds[-1]]
    return sorted([{'code': k, 'cd': v['cd'], 'last': v['c'], 'v': v['v']} for k, v in last.items()], key=lambda x: -(x['v'] or 0))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Cache-Control', 'no-store' if self.path.startswith(('/api/report/', '/api/ai/')) else 'public, max-age=300'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.startswith('/api/report/') and report_service:
            n = int(self.headers.get('Content-Length', '0') or 0); parts = u.path.strip('/').split('/')
            if n < 0 or n > 200 * 1024: return self.send(413, {'error': 'bad size'})
            body = self.rfile.read(n) if n else b''
            if parts == ['api', 'report', 'uploads']: return self.send(202, {'id': report_service.new_upload()})
            if len(parts) == 5 and parts[2] == 'uploads' and parts[4] == 'chunk': return self.send(200 if report_service.put_chunk(parts[3], int(q.get('i', '-1')), body) else 400, {'ok': True})
            if len(parts) == 5 and parts[2] == 'uploads' and parts[4] == 'start':
                jid, err = report_service.start_upload(parts[3], int(q.get('n', '0')))
                return self.send(202 if jid else 400, {'id': jid} if jid else {'error': err})
        self.send(404, {'error': 'not found'})
    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.startswith('/api/report/'):
            if not report_service: return self.send(503, {'error': 'report service unavailable', 'why': REPORT_ERR})
            parts = u.path.strip('/').split('/')
            if len(parts) == 4 and parts[2] == 'jobs':
                st = report_service.status(parts[3])
                return self.send(200, st) if st else self.send(404, {'error': 'no job'})
            if len(parts) == 5 and parts[2] == 'jobs' and parts[4] == 'file':
                j = report_service.JOBS.get(parts[3])
                if not j or j.get('status') != 'done': return self.send(404, {'error': 'not ready'})
                self.send_response(200); self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'); self.send_header('Content-Length', str(len(j['file']))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(j['file']); return
        if u.path in ('/api/ai/ping', '/api/ai/insights'):
            if not ai_insights: return self.send(503, {'error': 'ai module unavailable', 'why': AI_ERR})
            try: return self.send(200, ai_insights.ping() if u.path.endswith('ping') else ai_insights.insights(q.get('site', 'KR-01')))
            except Exception as e: return self.send(502, {'error': type(e).__name__, 'detail': str(e)[:300]})
        if u.path in ('/healthz', '/api/krx/health'): return self.send(200, {'ok': True, **META})
        if u.path == '/api/krx/products': return self.send(200, {'asof': META['asof'], 'products': products()})
        if u.path == '/api/krx/series':
            code = q.get('code', 'KAU26'); rows = series(code, q.get('from'), q.get('to'))
            return self.send(200, {'source': 'KRX Data Marketplace OPEN API (배출권 시장 일별매매정보)', 'code': code, 'asof': META['asof'], 'state': META['state'], 'delay': '영업일 다음 날 오후 갱신 · 실시간 아님', 'rows': rows})
        self.send(404, {'error': 'not found'})

if __name__ == '__main__':
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
