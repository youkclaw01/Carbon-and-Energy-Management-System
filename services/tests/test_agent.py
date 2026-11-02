import urllib.parse
import sys, os, json, time, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agentapi'))
import agent_app as AG, agent_core as K
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
RUN = str(uuid.uuid4())
run = dict(runId=RUN, plantId='KR-01', periodStart='2026-10-29T00:00:00.000Z', periodEnd='2026-10-29T01:00:00.000Z', mode='SIMULATED', businessState='ready', screenLabel='잠정(모의)', dq=dict(coverage='1.000', samples=720, expectedSamples=720),
           values=[dict(metric='scope2_location_based', value='459.400', unit='kgCO2e'), dict(metric='scope1_stationary_fuel', value='210.000', unit='kgCO2e'), dict(metric='grid_energy', value='1000.000', unit='kWh')],
           versionSet=dict(methodology=dict(id='AMA-S12-ENERGY-V1', version='1'), factors={'MOCK-EF-GRID-KR': dict(version='1')}), validation=dict(verdict='PASS'))
F = K.facts_from_run(run)
chk('FACTS: ready run만 사실로 변환, 미완료/값 없음은 None', F is not None and K.facts_from_run(dict(run, businessState='dq_failed')) is None and K.facts_from_run(dict(run, values=[])) is None)
good = '해당 구간(2026-10-29 00:00~01:00)의 Scope 2는 459.400 kgCO2e, Scope 1은 210.000 kgCO2e, 전력은 1000.000 kWh입니다. 표본 720/720(커버리지 1.000)이며 검증은 PASS입니다. 합성 모의 자료 기반 잠정 후보이며 확정·인증이 아닙니다.'
chk('grounding: FACTS 숫자만 쓴 초안 통과', K.grounding(good, F)[0], K.grounding(good, F))
ok2, bad2 = K.grounding('Scope 2는 512.7 kgCO2e로 추정됩니다.', F); chk('grounding: FACTS에 없는 숫자(512.7) 적발', (not ok2) and '512.7' in bad2, bad2)
chk('grounding: 소수 끝 0 생략(459.4)·정수화(210)도 FACTS 동치로 인정', K.grounding('Scope 2는 459.4, Scope 1은 210입니다.', F)[0])
def rej(fn, code):
    try: fn(); return False
    except K.Reject as e: return e.code == code
B0 = dict(schemaVersion='1', role='AI-A01', task='explain_calc_run', purpose='explain', plantScope='KR-01', contextRefs=[dict(owner='S02', id=RUN)])
chk('요청 검증: 미등록 task/role 불일치/owner 불일치/금지 필드', rej(lambda: K.validate_run(dict(B0, task='trade')), 'UNSUPPORTED_TASK') and rej(lambda: K.validate_run(dict(B0, role='AI-A03')), 'ROLE_TASK_MISMATCH') and rej(lambda: K.validate_run(dict(B0, contextRefs=[dict(owner='S08', id='x')])), 'CONTEXT_REF_INVALID') and rej(lambda: K.validate_run(dict(B0, signedPermit='x')), 'FORBIDDEN_FIELD'))
DDL = '''CREATE TABLE AgentRun(agentRunId TEXT PRIMARY KEY, country, orgId, agentId, task, subjectRef, idemKey, requestDigest, purpose, plantScope, contextRefs, modelPolicyRef, promptVersion, toolSchemaVersion, state, version, blockedReason, createdAt, deadline, updatedAt, UNIQUE(country,orgId,subjectRef,idemKey));
CREATE TABLE ToolCallAudit(agentRunId, toolCallId, auditSequence, toolId, requestDigest, resultDigest, effectClass, phase, status, recordedAt);
CREATE TABLE EvaluationRef(agentRunId, evaluationId, evaluatorVersion, sourceVersions, numericResult, citationResult, schemaResult, detail);
CREATE TABLE DraftArtifact(agentRunId, artifactId, facts, citations, draftText, sourceVersions, classification, modelDeployment, responseModel, responseId, usage, status, createdAt);
CREATE TABLE RunAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
AG.R = Repo('sqlite', cf); os.environ['CALC_API_URL'] = 'http://calc'; calls = []; mode = dict(st=200, texts=[good])
AG.FETCH = lambda url: (mode['st'], json.dumps(run).encode()) if mode['st'] == 200 else (mode['st'], b'{}')
def fake_model(prompt):
    calls.append(prompt); i = min(len(calls) - 1, len(mode['texts']) - 1); return mode['texts'][i], dict(model='gpt-6.1-sol-test', id='resp-%d' % len(calls), usage=dict(total_tokens=100))
AG.MODEL_CALL = fake_model
srv = make_server(8853, AG.route, AG.health, AG.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8853'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def wait(rid):
    for _ in range(100):
        c, d = call('GET', '/agent-runs/' + rid)
        if d['state'] in ('DRAFT', 'BLOCKED', 'FAILED'): return d
        time.sleep(0.1)
    return d
c, d = call('POST', '/agent-runs', B0); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a1', 'X-Actor': 'u1'}); rid = d['agentRunId']; chk('접수 202(효과 성공 아님)', c == 202 and d['state'] == 'ACCEPTED', (c, d))
r = wait(rid); chk('초안 DRAFT: 읽기 도구 1회(TOOL01)·숫자 근거 통과·DRAFT-SIMULATED·확정·인증 아님 문구 없음', r['state'] == 'DRAFT' and r['draft']['status'] == 'DRAFT' and '확정·인증 아님' not in r['draft']['label'] and r['classification'] == 'DRAFT-SIMULATED' and [t['toolId'] for t in r['toolCalls']] == ['TOOL01.get_run'] and r['evaluation']['numeric'] == 'passed', r)
chk('근거 연결: facts·citations(S02 run)·모델 사용량 기록', r['citations'][0]['owner'] == 'S02' and r['facts']['values']['scope2_location_based']['value'] == '459.400' and r['usage']['model'] == 'gpt-6.1-sol-test')
c, d2 = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a1', 'X-Actor': 'u1'}); chk('같은 키·같은 내용 → 200 같은 run(재추론 없음)', c == 200 and d2['agentRunId'] == rid and len(calls) == 1, (c, d2, len(calls)))
c, d2 = call('POST', '/agent-runs', dict(B0, purpose='other'), {'Idempotency-Key': 'a1', 'X-Actor': 'u1'}); chk('같은 키·다른 내용 → 409', c == 409, d2)
calls.clear(); mode['texts'] = ['Scope 2는 512.7 kgCO2e입니다.', good]; c, d = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a2', 'X-Actor': 'u1'}); r2 = wait(d['agentRunId']); chk('1차 초안의 근거 없는 숫자 → 피드백 후 재작성 통과(2회 호출)', r2['state'] == 'DRAFT' and len(calls) == 2 and r2['evaluation']['rounds'][0]['bad_numbers'] == ['512.7'], (r2['state'], len(calls), r2.get('evaluation')))
calls.clear(); mode['texts'] = ['Scope 2는 512.7 kgCO2e입니다.', '합계는 999.9입니다.']; c, d = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a3', 'X-Actor': 'u1'}); r3 = wait(d['agentRunId']); chk('2회 모두 근거 없는 숫자 → BLOCKED·초안 없음(값 보충 안 함)', r3['state'] == 'BLOCKED' and r3['draft'] is None and r3['evaluation']['numeric'] == 'failed', r3)
mode['st'] = 503; mode['texts'] = [good]; calls.clear(); c, d = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a4', 'X-Actor': 'u1'}); r4 = wait(d['agentRunId']); chk('S02 조회 실패 → BLOCKED(모델 호출 없음)', r4['state'] == 'BLOCKED' and len(calls) == 0 and r4['draft'] is None, r4); mode['st'] = 200
c, d = call('POST', '/agent-runs', dict(B0, plantScope='JP-01'), {'Idempotency-Key': 'a5'}); chk('다른 국가 공장 422', c == 422, d)
c, d = call('POST', '/agent-runs', dict(B0, signedPermit='x'), {'Idempotency-Key': 'a6'}); chk('실행 자격 필드 거절 422', c == 422 and d['code'] == 'FORBIDDEN_FIELD', d)
c, d = call('POST', '/agent-runs/' + rid + '/stop-requests', dict(expectedVersion=call('GET', '/agent-runs/' + rid)[1]['version'], reason='x'), {'X-Actor': 'u1'}); chk('종료된 실행의 중단 요청 409', c == 409, (c, d))
def slow(prompt): time.sleep(0.6); return good, dict(model='m', id='r', usage={})
AG.MODEL_CALL = slow; c, d = call('POST', '/agent-runs', B0, {'Idempotency-Key': 'a7', 'X-Actor': 'u1'}); rid7 = d['agentRunId']; time.sleep(0.2); v = call('GET', '/agent-runs/' + rid7)[1]['version']
c, d = call('POST', '/agent-runs/' + rid7 + '/stop-requests', dict(expectedVersion=v + 5, reason='x')); chk('중단 요청: 버전 불일치 412', c == 412, (c, d)); AG.MODEL_CALL = fake_model; wait(rid7)
c, d = call('GET', '/agent-runs/not-uuid'); chk('형식 오류 400', c == 400, d)
c, d = call('GET', '/agent-runs/' + str(uuid.uuid4())); chk('없는 실행 404', c == 404, d)
rows = AG.R.tx(lambda cur: (AG.R.ex(cur, 'SELECT prevHash, hash FROM dbo.RunAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and len(rows) >= 8)
c, d = call('GET', '/health'); chk('health', c == 200 and 'AI-A01' in d['mode'], d)
# ---- v0.7 지식 검색(AI Search 읽기 전용) ----
c, d = call('GET', '/knowledge/search?q=' + urllib.parse.quote('허브 방화벽')); chk('검색 엔드포인트 미구성 → 503 SEARCH_NOT_CONFIGURED', c == 503 and d['code'] == 'SEARCH_NOT_CONFIGURED', d)
AG.SEARCH_URL = 'https://srch.test'; sq = []
def fake_search(q, top): sq.append((q, top)); return {'value': [{'title': '허브', 'section': '방화벽', 'source': '06-infrastructure-review.md', 'chunkNo': 2, 'content': '가' * 500, '@search.score': 1.2, '@search.rerankerScore': 2.5}]}
AG.SEARCH_CALL = fake_search
c, d = call('GET', '/knowledge/search?q=' + urllib.parse.quote('허브 방화벽') + '&top=3'); chk('검색 200: 출처·점수·발췌(280자)·정본 안내', c == 200 and d['count'] == 1 and d['items'][0]['source'].endswith('.md') and len(d['items'][0]['snippet']) == 280 and '정본' in d['note'] and sq[-1][1] == 3, d)
c, d = call('GET', '/knowledge/search?q=' + urllib.parse.quote('허브') + '&top=99'); chk('top 상한 8', c == 200 and sq[-1][1] == 8, sq)
c, d = call('GET', '/knowledge/search?q=a'); chk('짧은 질의 400', c == 400, d)
c, d = call('GET', '/knowledge/search?q=' + 'x' * 201); chk('긴 질의 400', c == 400, d)
def boom(q, top): raise RuntimeError('down')
AG.SEARCH_CALL = boom; c, d = call('GET', '/knowledge/search?q=' + urllib.parse.quote('허브 방화벽')); chk('검색 서비스 오류 → 503 재시도 가능(내용 지어내지 않음)', c == 503 and d['retryable'] and d['code'] == 'SEARCH_UNAVAILABLE', d)
# SEARCH_CALL 실제 요청 형식(2024-07-01에서 허용되지 않는 queryLanguage 금지)
import io, importlib
cap = {}
class FR:
    def __init__(s, b): s.b = b
    def read(s): return s.b
    def __enter__(s): return s
    def __exit__(s, *a): return False
real_open, real_tok = AG.urllib.request.urlopen, AG._search_token
AG.urllib.request.urlopen = lambda rq, timeout=0: (cap.update(url=rq.full_url, body=json.loads(rq.data), auth=rq.get_header('Authorization')), FR(b'{"value": []}'))[1]; AG._search_token = lambda: 'T'
importlib.reload  # (no-op) SEARCH_CALL는 위에서 가짜로 바꿨으므로 원본을 다시 읽는다
src = open(os.path.join(os.path.dirname(__file__), '..', 'agentapi', 'agent_app.py'), encoding='utf-8').read(); ns = {}
exec(compile(src[src.index('def SEARCH_CALL'):src.index('def knowledge_search')], 'sc', 'exec'), dict(AG.__dict__, **ns), ns)
ns['SEARCH_CALL']('허브', 3)
chk('검색 요청: 허용된 필드만(queryLanguage 없음)·시맨틱 구성·Bearer 토큰·api-version 2024-07-01', set(cap['body']) == {'search', 'queryType', 'semanticConfiguration', 'select', 'top'} and cap['auth'] == 'Bearer T' and 'api-version=2024-07-01' in cap['url'] and '/indexes/ama-knowledge-v1/docs/search' in cap['url'], cap)
AG.urllib.request.urlopen, AG._search_token = real_open, real_tok
# 벡터 질의(임베딩 성공/실패 모두 투명하게 표시)
src = open(os.path.join(os.path.dirname(__file__), '..', 'agentapi', 'agent_app.py'), encoding='utf-8').read(); ns2 = dict(AG.__dict__)
exec(compile(src[src.index('EMBED_URL = '):src.index('def knowledge_search')], 'sc2', 'exec'), ns2)
cap2 = {}; ns2['_search_token'] = lambda: 'T'; ns2['_mi_token'] = lambda r: 'E'
def fake_open(rq, timeout=0):
    cap2.setdefault('urls', []).append(rq.full_url)
    if 'embeddings' in rq.full_url: return FR(json.dumps({'data': [{'embedding': [0.1] * 1536}]}).encode())
    cap2['body'] = json.loads(rq.data); return FR(b'{"value": []}')
ns2['urllib'] = type('U', (), dict(request=type('R', (), dict(urlopen=staticmethod(fake_open), Request=AG.urllib.request.Request)), error=AG.urllib.error, parse=AG.urllib.parse))
ns2['EMBED_URL'] = 'https://emb.test/openai/deployments/emb-3-small/embeddings?api-version=2024-10-21'
ns2['SEARCH_CALL']('허브', 3)
vq = (cap2['body'].get('vectorQueries') or [{}])[0]; chk('임베딩 구성 시 vectorQueries 포함(contentVector·1536차원·k≥10)', ns2['VEC']['used'] and vq.get('fields') == 'contentVector' and len(vq.get('vector', [])) == 1536 and vq.get('k', 0) >= 10, cap2.get('body'))
def boom(rq, timeout=0):
    if 'embeddings' in rq.full_url: raise AG.urllib.error.HTTPError(rq.full_url, 403, 'x', {}, None)
    cap2['body2'] = json.loads(rq.data); return FR(b'{"value": []}')
ns2['urllib'].request.urlopen = staticmethod(boom); ns2['SEARCH_CALL']('허브', 3)
chk('임베딩 실패는 숨기지 않음: 벡터 없이 시맨틱 검색·vector=false·오류 코드 기록', not ns2['VEC']['used'] and ns2['VEC']['error'] == 'HTTP_403' and 'vectorQueries' not in cap2['body2'], (ns2['VEC'], cap2.get('body2')))
# ---- 배출권 포지션 판단(judge_allowance_position, 규칙 계산 결과의 설명) ----
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'procapi')); import allowance_core as AC
POS = AC.position(); FA = K.facts_allowance(POS)
chk('배출권 FACTS: 모의 포지션만 사실로, 계산 결과 없으면 None', FA is not None and K.facts_allowance(dict(POS, mode='LIVE')) is None and K.facts_allowance(dict(POS, result=None)) is None)
chk('배출권 task 등록: AI-A03·S04, 요청 검증 통과(다른 role은 불일치)', K.TASKS['judge_allowance_position'][:2] == ('AI-A03', 'S04') and rej(lambda: K.validate_run(dict(B0, task='judge_allowance_position', role='AI-A01', contextRefs=[dict(owner='S04', id=AC.DEMO_ID)])), 'ROLE_TASK_MISMATCH') and K.validate_run(dict(B0, task='judge_allowance_position', role='AI-A03', contextRefs=[dict(owner='S04', id=AC.DEMO_ID)])) is None)
pr = K.build_prompt(FA, '', 'judge_allowance_position'); chk('배출권 프롬프트: 초안·승인 필요·새 수량 제안 금지·FACTS 인용', '권한이 없고' in pr and '새로운 매매 수량' in pr and 'FACTS=' in pr and '960000' in pr)
good_a = '규칙상 잉여업체는 순매도량의 6배까지만 이월할 수 있어 허용 구간은 912609~968259t이고 권고 수량은 960000t입니다. 3000000t 매도는 다음 해 부족 2031741t이 생겨 비권고입니다. 2026 할당과 배출은 모의 가정이며 이 결과는 초안으로 사람의 승인이 필요합니다.'
chk('배출권 grounding: FACTS 숫자만 쓴 설명 통과·임의 수량(1200000) 적발', K.grounding(good_a, FA)[0] and not K.grounding(good_a + ' 1200000t도 가능합니다.', FA)[0], K.grounding(good_a, FA))
import re as _re
_ids = _re.findall(r"'(TOOL\d\d\.[a-z_]+)'", open(os.path.join(os.path.dirname(__file__), '..', 'agentapi', 'agent_app.py'), encoding='utf-8').read())
chk('도구 ID 길이 ≤ 20(DB ToolCallAudit.toolId NVARCHAR(20), 초과 시 STORE_UNAVAILABLE)', len(_ids) >= 6 and all(len(i) <= 20 for i in _ids), _ids)
fx = {'values': {'x': 1}}
pr = K.build_prompt(fx, '', 'judge_allowance_position', '', [dict(source='law/kr/ets-act.md', section='제30조', text='이월 한도')])
chk('RAG: 프롬프트에 LAW_CONTEXT·출처 규칙 포함', 'LAW_CONTEXT' in pr and 'law/kr/ets-act.md' in pr, pr[:80])
chk('RAG: 법령 발췌의 숫자는 근거 검사에서 허용', K.grounding('제30조에 따라 6배입니다.', dict(fx, _rag=[dict(section='제30조', text='순매도량의 6배')]))[0], '')
chk('검색 필터: 정상 허용', AG._filter({'docType': ['law'], 'country': ['KR']}) == "docType eq 'law' and country eq 'KR'", '')
try: AG._filter({'country': ["KR' or 1 eq 1"]}); inj = False
except Exception: inj = True
chk('검색 필터: OData 주입 거절', inj, '')
import inspect
_src = inspect.getsource(AG.create)
chk('범위: JP·SG 판단은 집계 범위(JP-01·SG-01)만 추가 허용, 다른 과제는 KR-01만', "'judge_gx_position': ('KR-01', 'JP-01', 'JP-02', 'JP-03', 'JP-04')" in _src and "'judge_sg_tax_position': ('KR-01', 'SG-01', 'SG-02', 'SG-03')" in _src and "get(body['task'], ('KR-01',))" in _src, '')
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
