"""서비스 공통(체크리스트 2-x): 오류 봉투·저장소(Sql/sqlite 시험)·해시 체인 감사·HTTP 처리기. 각 서비스는 route()와 순수 core만 제공한다.
오류 봉투: {code, message, retryable, correlationId}. 저장소 오류는 503(재시도 가능), 질의는 직렬화하고 연결 오류는 재연결 후 1회 재시도한다."""
import os, sys, json, time, uuid, hashlib, threading, datetime as dt, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel as _ai; _ai.install()
except Exception: _ai = None
class ApiError(Exception):
    def __init__(self, status, code, msg='', retry=False): self.status, self.code, self.msg, self.retry = status, code, msg, retry
def now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def ts(d=None): d = d or now(); return d.strftime('%Y-%m-%d %H:%M:%S.') + '%03d' % (d.microsecond // 1000)
def iso(v):
    if hasattr(v, 'strftime'): return v.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (v.microsecond // 1000)
    return (str(v).replace(' ', 'T') + 'Z') if v and 'T' not in str(v) else v
def sha(b): return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()
def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
class Repo:
    def __init__(self, kind, cf): self.kind, self.cf, self.conn, self.lock, self.err, self.last_err = kind, cf, None, threading.RLock(), 0, None
    def q(self, sql): return sql.replace('%s', '?').replace('dbo.', '') if self.kind == 'sqlite' else sql
    def top(self, sql, n=1): return sql.replace('SELECT', 'SELECT TOP %d' % n, 1) if self.kind == 'sql' else sql + ' LIMIT %d' % n
    def tx(self, fn):
        t0 = time.time(); ok = False
        try: r = self._tx(fn); ok = True; return r
        finally:
            if _ai:
                try: _ai.sql_dependency(os.environ.get('SQL_SERVER') or self.kind, 'tx', ok, t0, time.time() - t0)
                except Exception: pass
    def _tx(self, fn):
        with self.lock:
            for t in (0, 1):
                try:
                    if self.conn is None: self.conn = self.cf()
                    cur = self.conn.cursor(); r = fn(cur); self.conn.commit(); return r
                except ApiError: self._rb(); raise
                except Exception as e:
                    self.err += 1; self.last_err = (type(e).__name__ + ': ' + str(e))[:160]; self._rb()
                    if self.kind == 'sql':
                        try: self.conn.close()
                        except Exception: pass
                        self.conn = None
                    if t or self.kind == 'sqlite': raise ApiError(503, 'STORE_UNAVAILABLE', '저장소 오류로 처리하지 못했습니다.', True)
                    time.sleep(0.3)
    def _rb(self):
        try: self.conn.rollback()
        except Exception: pass
    def ex(self, cur, sql, p=()): cur.execute(self.q(sql), p); return cur
    def chain(self, cur, table, hashcol, seqcol, fields, prevcol='prevHash'):
        """추가 전용 해시 체인 감사 기록(상태 변경과 같은 트랜잭션). fields: {열: 값}. 실패하면 호출 쪽 트랜잭션 전체가 롤백된다."""
        self.ex(cur, self.top('SELECT %s FROM dbo.%s ORDER BY %s DESC' % (hashcol, table, seqcol))); r = cur.fetchall(); prev = r[0][0] if r else None
        fields = dict(fields); fields['at'] = ts(); h = sha('|'.join([str(prev)] + [str(fields[k]) for k in sorted(fields)])); fields[prevcol] = prev; fields[hashcol] = h
        cols = list(fields); self.ex(cur, 'INSERT INTO dbo.%s(%s) VALUES (%s)' % (table, ', '.join(cols), ', '.join(['%s'] * len(cols))), tuple(fields[c] for c in cols)); return h
def sql_repo():
    import pytds, certifi; srv, db = os.environ['SQL_SERVER'], os.environ['SQL_DB']
    def tok():
        q = {'resource': 'https://database.windows.net/', 'api-version': '2019-08-01'}
        if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
        return json.loads(urllib.request.urlopen(urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=10).read())['access_token']
    return Repo('sql', lambda: pytds.connect(srv, db, port=1433, access_token_callable=tok, cafile=certifi.where(), autocommit=False, login_timeout=20, timeout=30))
def http_get(url, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=timeout) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
    except Exception: return 0, b''
def make_server(port, route, health, stats, host='0.0.0.0'):
    """route(method, path, qs, body, headers, cid) -> (status, obj) | (status, bytes, ctype, extra_headers). ApiError는 오류 봉투로 변환."""
    class H(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *a): pass
        def send(self, code, obj, cid, raw=None, ctype='application/json; charset=utf-8', extra=None):
            b = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store'); self.send_header('X-Correlation-Id', cid)
            for k, v in (extra or {}).items(): self.send_header(k, v)
            self.end_headers(); self.wfile.write(b)
        def go(self, m):
            stats['requests'] = stats.get('requests', 0) + 1; cid = self.headers.get('X-Correlation-Id') or str(uuid.uuid4()); u = urlparse(self.path); qs = parse_qs(u.query); p = u.path.rstrip('/') or '/'
            try:
                body = {}
                if m == 'POST':
                    n = int(self.headers.get('Content-Length') or 0)
                    if n > 30000: raise ApiError(413, 'PAYLOAD_TOO_LARGE')
                    try: body = json.loads(self.rfile.read(n) or b'{}')
                    except Exception: raise ApiError(400, 'BAD_REQUEST', 'JSON 형식이 아닙니다.')
                if m == 'GET' and p == '/health': return self.send(200, dict(ok=True, **health()), cid)
                r = route(m, p, qs, body, self.headers, cid)
                if r is None: raise ApiError(405 if p.startswith('/v1/') else 404, 'METHOD_NOT_ALLOWED' if p.startswith('/v1/') else 'NOT_FOUND')
                if len(r) == 2: return self.send(r[0], r[1], cid)
                return self.send(r[0], None, cid, raw=r[1], ctype=r[2], extra=r[3])
            except ApiError as e:
                if e.status >= 500: stats['errors'] = stats.get('errors', 0) + 1
                self.send(e.status, dict(code=e.code, message=e.msg, retryable=e.retry, correlationId=cid), cid)
            except Exception: stats['errors'] = stats.get('errors', 0) + 1; self.send(500, dict(code='INTERNAL', retryable=False, correlationId=cid), cid)
        def do_GET(self): self.go('GET')
        def do_POST(self): self.go('POST')
    class TS(ThreadingHTTPServer): daemon_threads = True; request_queue_size = 64
    return TS((host, port), H)
