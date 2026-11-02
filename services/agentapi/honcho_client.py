"""Honcho 기억 저장소 클라이언트(표준 라이브러리만). 에이전트 5종의 대화·실행 기억을 한국 Honcho(workspace ama-agents, peer=역할 ID)에 남기고 되읽는다.
규칙: ① 정본은 파일/Git·소유 서비스(S02~S06)이며 기억은 문체·주의점·이전 설명 이력 같은 보조 맥락이다. 기억 속 숫자는 FACTS가 아니므로 숫자 근거 검사에서 그대로 차단된다. ② 기억 실패는 실행을 막지 않되 숨기지 않고 실행 기록에 남긴다.
③ JWT 비밀은 환경(ACA 비밀)에서만 읽고 로그에 남기지 않는다."""
import os, json, time, hmac, hashlib, base64, urllib.request, urllib.error
def _b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def mint_admin_jwt(secret):
    h = _b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode()); p = _b64(json.dumps({'t': '', 'ad': True}, separators=(',', ':')).encode())
    return h + '.' + p + '.' + _b64(hmac.new(secret.encode(), (h + '.' + p).encode(), hashlib.sha256).digest())
class Honcho:
    def __init__(self, url=None, secret=None, workspace=None, opener=None):
        self.url = (url or os.environ.get('HONCHO_URL', '')).rstrip('/'); self.secret = secret or os.environ.get('HONCHO_JWT_SECRET', '')
        self.ws = workspace or os.environ.get('HONCHO_WORKSPACE', 'ama-agents'); self.open = opener or urllib.request.urlopen; self._ready = set()
    @property
    def enabled(self): return bool(self.url and self.secret)
    def _call(self, method, path, body=None, timeout=20):
        rq = urllib.request.Request(self.url + path, data=json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None, method=method, headers={'Authorization': 'Bearer ' + mint_admin_jwt(self.secret), 'Content-Type': 'application/json'})
        try:
            with self.open(rq, timeout=timeout) as r: raw = r.read(); return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read()
            try: return e.code, json.loads(raw)
            except Exception: return e.code, {'raw': raw[:200].decode('utf-8', 'replace')}
    def ensure(self, peer, session=None):
        if ('ws',) not in self._ready:
            c, d = self._call('POST', '/v3/workspaces', {'id': self.ws})
            if c not in (200, 201): raise RuntimeError('honcho workspace %s' % c)
            self._ready.add(('ws',))
        if ('p', peer) not in self._ready:
            c, d = self._call('POST', '/v3/workspaces/%s/peers' % self.ws, {'id': peer})
            if c not in (200, 201): raise RuntimeError('honcho peer %s' % c)
            self._ready.add(('p', peer))
        if session and ('s', session) not in self._ready:
            c, d = self._call('POST', '/v3/workspaces/%s/sessions' % self.ws, {'id': session, 'peers': {peer: {}}})
            if c not in (200, 201): raise RuntimeError('honcho session %s' % c)
            self._ready.add(('s', session))
    def remember(self, peer, session, text, metadata=None):
        """역할 peer의 세션에 실행 요약을 메시지로 기록. 반환: 'stored'."""
        self.ensure(peer, session)
        c, d = self._call('POST', '/v3/workspaces/%s/sessions/%s/messages' % (self.ws, session), {'messages': [{'peer_id': peer, 'content': text[:4000], 'metadata': metadata or {}}]})
        if c not in (200, 201): raise RuntimeError('honcho message %s' % c)
        return 'stored'
    def recall(self, peer, session=None, limit_chars=1200):
        """역할 peer의 최근 맥락(요약+표현). 없으면 ''. 숫자 인용 금지 안내와 함께 프롬프트에 붙인다."""
        self.ensure(peer)
        c, d = self._call('GET', '/v3/workspaces/%s/peers/%s/context' % (self.ws, peer))
        if c != 200: raise RuntimeError('honcho context %s' % c)
        rep = d.get('representation') or ''
        if isinstance(rep, (dict, list)): rep = json.dumps(rep, ensure_ascii=False)
        return str(rep)[:limit_chars]
    def health(self):
        c, d = self._call('GET', '/health') if False else self._call('POST', '/v3/workspaces/list', {})
        return c
