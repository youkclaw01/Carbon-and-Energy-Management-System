import sys, os, json, base64, hmac, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agentapi'))
import honcho_client as HC, agent_core as K
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
calls = []; mode = dict(code=200)
class Resp:
    def __init__(s, code, body): s.status = code; s._b = json.dumps(body).encode()
    def read(s): return s._b
    def __enter__(s): return s
    def __exit__(s, *a): return False
def opener(rq, timeout=20):
    calls.append((rq.get_method(), rq.full_url.split('.io')[-1], json.loads(rq.data) if rq.data else None, rq.get_header('Authorization')))
    if mode['code'] != 200:
        import urllib.error, io; raise urllib.error.HTTPError(rq.full_url, mode['code'], 'x', {}, io.BytesIO(b'{"detail":"x"}'))
    return Resp(200, {'representation': 'AI-A01은 간결한 3~5문장을 선호'} if rq.get_method() == 'GET' else {'id': 'ok'})
H = HC.Honcho('https://h.example.io', 'secret1', 'ama-agents', opener)
chk('설정 없으면 비활성', not HC.Honcho('', '').enabled and H.enabled)
t = HC.mint_admin_jwt('secret1'); h, p, s = t.split('.'); pad = lambda x: x + '=' * (-len(x) % 4)
chk('JWT: HS256 서명 검증·admin 클레임', json.loads(base64.urlsafe_b64decode(pad(p))) == {'t': '', 'ad': True} and base64.urlsafe_b64encode(hmac.new(b'secret1', (h + '.' + p).encode(), hashlib.sha256).digest()).rstrip(b'=').decode() == s)
chk('기록: workspace→peer→session→messages 순서·내용', H.remember('AI-A02', 'run-1', '요약', {'k': 1}) == 'stored' and [(c[0], c[1]) for c in calls] == [('POST', '/v3/workspaces'), ('POST', '/v3/workspaces/ama-agents/peers'), ('POST', '/v3/workspaces/ama-agents/sessions'), ('POST', '/v3/workspaces/ama-agents/sessions/run-1/messages')] and calls[-1][2]['messages'][0]['peer_id'] == 'AI-A02', calls)
n = len(calls); H.remember('AI-A02', 'run-2', 'x'); chk('같은 workspace·peer는 다시 만들지 않음(세션·메시지만)', [c[1] for c in calls[n:]] == ['/v3/workspaces/ama-agents/sessions', '/v3/workspaces/ama-agents/sessions/run-2/messages'])
chk('모든 호출에 Bearer JWT', all(c[3].startswith('Bearer ') for c in calls))
chk('회상: 표현 문자열 반환', H.recall('AI-A02').startswith('AI-A01은'))
mode['code'] = 503
try: H.recall('AI-A09'); chk('실패 시 예외(숨기지 않음)', False)
except RuntimeError as e: chk('실패 시 예외(숨기지 않음): ' + str(e), 'honcho' in str(e))
mode['code'] = 200
pr = K.build_prompt({'a': '1'}, '', 'explain_scenario', '이전에는 간결한 문장을 선호'); chk('프롬프트: 기억은 숫자·사실 근거 아님 안내와 함께 포함', '이전 실행 기억' in pr and '근거가 아니며' in pr and 'FACTS=' in pr)
chk('기억이 없으면 프롬프트에 기억 문구 없음', '이전 실행 기억' not in K.build_prompt({'a': '1'}, '', 'explain_scenario', ''))
chk('기억 속 숫자는 FACTS가 아니므로 숫자 검사에서 차단', not K.grounding('지난번 값 999.5를 다시 씁니다.', {'v': '1'})[0])
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
