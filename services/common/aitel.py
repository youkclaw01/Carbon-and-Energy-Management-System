"""Application Insights 텔레메트리(표준 라이브러리만 사용). install() 한 번으로
 - 들어오는 HTTP 요청(Request)을 기록하고(BaseHTTPRequestHandler 훅, /health·/healthz 제외),
 - 나가는 HTTP 호출(RemoteDependency)을 기록한다(urllib OpenerDirector.open 훅, 관리 ID 토큰 호출·수집 호출 제외).
요청 사이는 X-Correlation-Id(작업 ID)와 Request-Id(부모 ID)로 이어 붙인다. 비밀·본문·쿼리 문자열은 기록하지 않는다(경로만).
APPLICATIONINSIGHTS_CONNECTION_STRING 환경 변수가 없으면 아무것도 하지 않는다. 전송 실패는 호출을 막지 않고 버린다(STATS로 확인)."""
import os, json, time, uuid, threading, atexit, collections, urllib.request, urllib.parse, urllib.error, datetime as _dt
from http.server import BaseHTTPRequestHandler
STATS = dict(enabled=False, queued=0, sent=0, dropped=0, last_err=None)
_Q = collections.deque(maxlen=3000); _L = threading.local(); _CFG = {}; _ORIG = {}; _LOCK = threading.Lock(); _WAKE = threading.Event()
SKIP_HOSTS = ('169.254.169.254', '169.254.129.1')
def _parse(cs):
    d = {}
    for part in (cs or '').split(';'):
        if '=' in part: k, v = part.split('=', 1); d[k.strip().lower()] = v.strip()
    return d
def _iso(t): return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % int((t % 1) * 1000)
def _dur(sec):
    ms = int(sec * 1000); return '%02d:%02d:%02d.%03d' % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)
def _env(kind, base, op, parent, t0):
    tags = {'ai.cloud.role': _CFG['role'], 'ai.cloud.roleInstance': _CFG['inst'], 'ai.operation.id': op}
    if parent: tags['ai.operation.parentId'] = parent
    return {'name': 'Microsoft.ApplicationInsights.%s.%s' % (_CFG['ikey'].replace('-', ''), kind), 'time': _iso(t0), 'iKey': _CFG['ikey'], 'tags': tags, 'data': {'baseType': kind + 'Data', 'baseData': dict(base, ver=2)}}
def _push(e):
    if len(_Q) == _Q.maxlen: STATS['dropped'] += 1
    _Q.append(e); STATS['queued'] = len(_Q)
    if len(_Q) >= 40: _WAKE.set()
def track_request(op, rid, parent, method, path, code, t0, dt):
    ok = code < 400 or code == 401
    _push(_env('Request', dict(id=rid, name='%s %s' % (method, path), duration=_dur(dt), success=ok, responseCode=str(code), url=path), op, parent, t0))
def track_dependency(op, parent, did, typ, target, name, data, ok, code, t0, dt):
    _push(_env('RemoteDependency', dict(id=did, name=name, type=typ, target=target, data=data, duration=_dur(dt), success=ok, resultCode=str(code)), op, parent, t0))
def sql_dependency(target, name, ok, t0, dt):
    """서비스 공통 저장소(Repo.tx)가 호출한다. 문장·값은 기록하지 않는다."""
    if not _CFG: return
    op = getattr(_L, 'op', None) or uuid.uuid4().hex
    track_dependency(op, getattr(_L, 'rid', None), uuid.uuid4().hex[:16], 'SQL', target, name, name, ok, 0 if ok else 1, t0, dt)
def _flush():
    items = []
    while _Q and len(items) < 200: items.append(_Q.popleft())
    STATS['queued'] = len(_Q)
    if not items: return
    try:
        rq = urllib.request.Request(_CFG['endpoint'], data=json.dumps(items).encode(), method='POST', headers={'Content-Type': 'application/json'})
        with _ORIG['open'](_ORIG['opener'], rq, None, 8) as r:
            body = r.read()
        try: acc = json.loads(body or b'{}').get('itemsAccepted', len(items))
        except Exception: acc = len(items)
        STATS['sent'] += acc; STATS['dropped'] += len(items) - acc
    except Exception as e:
        STATS['dropped'] += len(items); STATS['last_err'] = (type(e).__name__ + ': ' + str(e))[:160]
def _loop():
    while True:
        _WAKE.wait(5); _WAKE.clear()
        try:
            while _Q: _flush()
        except Exception: pass
def _req_hook():
    orig_handle = BaseHTTPRequestHandler.handle_one_request; orig_send = BaseHTTPRequestHandler.send_response
    def send_response(self, code, message=None):
        self._ai_code = code; return orig_send(self, code, message)
    def handle_one_request(self):
        t0 = time.time(); self._ai_code = 0
        try: return orig_handle(self)
        finally:
            try:
                cmd = getattr(self, 'command', None); raw = getattr(self, 'path', '') or ''
                path = urllib.parse.urlsplit(raw).path or '/'
                if cmd and self._ai_code and path.rstrip('/') not in ('/health', '/healthz'):
                    parent = (self.headers.get('Request-Id') or '').strip() or None
                    track_request(getattr(_L, 'op', None) or uuid.uuid4().hex, getattr(_L, 'rid', None) or uuid.uuid4().hex[:16], parent, cmd, path, self._ai_code, t0, time.time() - t0)
            except Exception: pass
            _L.op = None; _L.rid = None
    BaseHTTPRequestHandler.send_response = send_response; BaseHTTPRequestHandler.handle_one_request = _wrap_ctx(handle_one_request)
def _wrap_ctx(fn):
    """요청 처리 시작 시 작업 ID·요청 ID를 스레드에 저장한다(나가는 호출이 이어 붙이도록). 헤더는 첫 줄 읽기 뒤에야 알 수 있으므로 parse_request를 감싼다."""
    orig_parse = BaseHTTPRequestHandler.parse_request
    def parse_request(self):
        ok = orig_parse(self)
        try:
            if ok: _L.op = (self.headers.get('X-Correlation-Id') or '').strip() or uuid.uuid4().hex; _L.rid = uuid.uuid4().hex[:16]
        except Exception: pass
        return ok
    BaseHTTPRequestHandler.parse_request = parse_request
    return fn
def _dep_hook():
    orig = urllib.request.OpenerDirector.open; _ORIG['open'] = orig
    def open_(self, fullurl, data=None, timeout=urllib.request.socket._GLOBAL_DEFAULT_TIMEOUT):
        try:
            rq = fullurl if isinstance(fullurl, urllib.request.Request) else None
            url = rq.full_url if rq else str(fullurl); sp = urllib.parse.urlsplit(url); host = sp.hostname or ''
            if not host or host in SKIP_HOSTS or sp.netloc == _CFG['ing_host'] or (os.environ.get('IDENTITY_ENDPOINT') and url.startswith(os.environ['IDENTITY_ENDPOINT'].split('?')[0])) or getattr(_L, 'skip', False):
                return orig(self, fullurl, data, timeout)
        except Exception: return orig(self, fullurl, data, timeout)
        op = getattr(_L, 'op', None) or uuid.uuid4().hex; did = uuid.uuid4().hex[:16]; t0 = time.time(); method = (rq.get_method() if rq else ('POST' if data else 'GET'))
        try:   # 상대 서비스가 이어 붙이도록 헤더를 싣는다
            if rq is None: rq = urllib.request.Request(url, data=data); fullurl = rq
            rq.add_unredirected_header('X-Correlation-Id', op); rq.add_unredirected_header('Request-Id', did)
        except Exception: pass
        ok, code = True, 0
        try:
            r = orig(self, fullurl, data, timeout); code = getattr(r, 'status', 200); ok = code < 400; return r
        except urllib.error.HTTPError as e: code = e.code; ok = False; raise
        except Exception: ok = False; code = 0; raise
        finally:
            try: track_dependency(op, getattr(_L, 'rid', None), did, 'HTTP', (sp.netloc or host), '%s %s' % (method, sp.path or '/'), '%s://%s%s' % (sp.scheme, sp.netloc, sp.path), ok, code, t0, time.time() - t0)
            except Exception: pass
    urllib.request.OpenerDirector.open = open_
def install(role=None):
    """한 번만 적용. 연결 문자열이 없으면 아무 것도 하지 않는다."""
    with _LOCK:
        if _CFG or STATS['enabled']: return STATS['enabled']
        cs = _parse(os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'))
        if not cs.get('instrumentationkey') or not cs.get('ingestionendpoint'): return False
        ep = cs['ingestionendpoint'].rstrip('/') + '/v2/track'
        _CFG.update(ikey=cs['instrumentationkey'], endpoint=ep, ing_host=urllib.parse.urlsplit(ep).netloc, role=role or os.environ.get('CONTAINER_APP_NAME') or os.environ.get('AMA_ROLE') or 'unknown', inst=os.environ.get('CONTAINER_APP_REPLICA_NAME') or os.environ.get('HOSTNAME') or 'local')
        _ORIG['opener'] = urllib.request.build_opener()   # 수집 전송 전용(훅이 걸리지 않는 원본 open을 사용)
        _dep_hook(); _req_hook()
        STATS['enabled'] = True; threading.Thread(target=_loop, daemon=True, name='aitel').start(); atexit.register(lambda: [_flush() for _ in range(5) if _Q])
        return True
