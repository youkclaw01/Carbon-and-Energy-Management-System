#!/usr/bin/env python3
"""agent-api — S11 업무 Agent AI-A01(산정 지원) POST /agent-runs · GET /agent-runs/{id} · stop-requests (체크리스트 2-12-2~2-12-4). 설계: design/services/S11 §2~5.
도구는 TOOL01 읽기 1종(S02 calc-api GET /v1/calc-runs/{id})뿐이다: 쓰기·승인·실행·S07/S08/S09 호출·SQL·URL 임의 조회 없음. 모델: 신규 Foundry fdry-cems-prd-krc-02의 gpt-6.1-sol(관리 ID, 사설 연결), 자동 fallback·다른 모델 대체 없음, 모델 실패는 실패로 표시.
수치는 S02 값이며 초안의 숫자는 FACTS 일치 검사(grounding)를 통과해야 한다(2회 시도 후에도 실패하면 BLOCKED, 값 보충 없음). 결과는 DRAFT·SIMULATED·미인증 표시. 편차: 사용자 위임 토큰·현재 grant 확인(S07 이후)이 없어 내부 전용(X-Actor 미검증 라벨), S12 미구축으로 내부 작업자가 대행.
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, CALC_API_URL, AI_PROJECT, AI_MODEL."""
import re, os, sys, json, uuid, time, hashlib, threading, datetime as dt, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import agent_core as K
VERSION = 'agent-api/0.17'; COUNTRY, ORG, STATS = 'KR', 'AMA-KR', {}; R = None; FETCH = http_get
PROJECT = os.environ.get('AI_PROJECT', 'https://fdry-cems-prd-krc-02.services.ai.azure.com/api/projects/proj-cems-prd-krc-02'); MODEL = os.environ.get('AI_MODEL', 'gpt-6-1-sol'); PROMPT_V, TOOL_V = 'p1', 't1'
def model_call(prompt):
    """Foundry Responses API. 반환 (text, response dict). 실패는 예외(대체 없음)."""
    qp = {'resource': 'https://ai.azure.com', 'api-version': '2019-08-01'}
    if os.environ.get('AZURE_CLIENT_ID'): qp['client_id'] = os.environ['AZURE_CLIENT_ID']
    q = os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(qp)
    tok = json.loads(urllib.request.urlopen(urllib.request.Request(q, headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=20).read())['access_token']
    pl = {'model': MODEL, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}], 'max_output_tokens': 3000, 'store': False, 'stream': False, 'tools': [], 'tool_choice': 'none'}
    try: r = json.loads(urllib.request.urlopen(urllib.request.Request(PROJECT + '/openai/v1/responses', data=json.dumps(pl, ensure_ascii=False).encode('utf-8'), headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}), timeout=120).read())
    except urllib.error.HTTPError as e: raise RuntimeError('model HTTP %s: %s' % (e.code, e.read()[:300].decode('utf-8', 'replace')))
    return ''.join(c.get('text', '') for o in r.get('output', []) if o.get('type') == 'message' for c in o.get('content', [])), r
MODEL_CALL = model_call
import honcho_client as HC
MEM = HC.Honcho()
def role_of(task): return K.TASKS[task][0]
def A(cur, actor, action, target, reason='', cid=None, before=None, after=None):
    R.chain(cur, 'RunAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def setstate(rid, state, reason='', cid=None):
    def f(cur):
        R.ex(cur, 'SELECT version FROM dbo.AgentRun WHERE agentRunId=%s', (rid,)); v = cur.fetchall()[0][0]
        R.ex(cur, 'UPDATE dbo.AgentRun SET state=%s, version=%s, blockedReason=%s, updatedAt=%s WHERE agentRunId=%s AND version=%s', (state, v + 1, reason[:200] or None, ts(), rid, v)); A(cur, 'agent-worker', 'RUN_STATE', rid, reason, cid, str(v), str(v + 1))
    R.tx(f)
SRC = {'explain_calc_run': ('CALC_API_URL', '/v1/calc-runs/%s', 'TOOL01.get_run'), 'explain_scenario': ('PLAN_API_URL', '/v1/simulation-runs/%s', 'TOOL02.get_sim_run'), 'explain_procurement_intent': ('PROC_API_URL', '/v1/procurement-intents/%s', 'TOOL03.get_intent'), 'judge_allowance_position': ('PROC_API_URL', '/v1/allowance-positions/%s', 'TOOL03.get_allowance'), 'judge_gx_position': ('PROC_API_URL', '/v1/allowance-positions/%s', 'TOOL03.get_gx'), 'judge_sg_tax_position': ('PROC_API_URL', '/v1/allowance-positions/%s', 'TOOL03.get_sgtax'), 'explain_footprint_request': ('FP_API_URL', '/v1/footprint-requests/%s', 'TOOL04.get_footprint'), 'explain_evidence_manifest': ('EVID_API_URL', '/v1/manifests/%s', 'TOOL05.get_manifest')}
def remember(rid, task, run_id, state, draft, cid):
    """실행 요약을 Honcho 역할 peer 기억에 기록(숫자 근거 아님). 실패는 감사에 남기고 실행은 막지 않는다."""
    if not MEM.enabled: return
    try:
        MEM.remember(role_of(task), rid, '[%s] %s 대상 %s 결과 %s%s' % (task, K.TASKS[task][1], run_id, state, (' — 초안: ' + draft[:600]) if draft else ''), dict(agentRunId=rid, task=task, state=state))
        R.tx(lambda cur: A(cur, 'agent-worker', 'MEMORY_WRITE', rid, 'honcho stored', cid))
    except Exception as e:
        try: R.tx(lambda cur: A(cur, 'agent-worker', 'MEMORY_WRITE_FAILED', rid, ('%s: %s' % (type(e).__name__, e))[:200], cid))
        except Exception: pass
def work(rid, run_id, cid, task='explain_calc_run'):
    try:
        R.tx(lambda cur: R.ex(cur, 'UPDATE dbo.AgentRun SET state=%s, updatedAt=%s WHERE agentRunId=%s AND state=%s', ('RUNNING', ts(), rid, 'ACCEPTED')))
        tc = str(uuid.uuid4()); base, pth, tid = SRC[task]; url = os.environ.get(base, '').rstrip('/') + pth % run_id; st, body = FETCH(url)
        rdig = sha(url)
        def tool(cur): R.ex(cur, 'INSERT INTO dbo.ToolCallAudit(agentRunId, toolCallId, auditSequence, toolId, requestDigest, resultDigest, effectClass, phase, status, recordedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (rid, tc, 1, tid, rdig, sha(body) if st == 200 else None, 'READ', 'COMPLETED', 'ok' if st == 200 else 'http_%s' % st, ts()))
        R.tx(tool)
        if st != 200: return setstate(rid, 'BLOCKED', '%s 조회 실패(%s) — 근거 없음, 값 보충 안 함' % (K.TASKS[task][1], st), cid)
        facts = K.TASKS[task][3](json.loads(body))
        if facts is None: return setstate(rid, 'BLOCKED', '소유 서비스에 설명할 수 있는 확정된 값이 없습니다(상태·DQ·선행 서비스) — 값을 보충하지 않았습니다', cid)
        mem_state, mem_ctx = 'disabled', ''
        if MEM.enabled:
            try: mem_ctx = MEM.recall(role_of(task)); mem_state = 'recalled' if mem_ctx else 'empty'
            except Exception as e: mem_state = 'recall_failed:' + type(e).__name__
        rag_state, rag = RAG_FOR(task, facts); gfacts = dict(facts, _rag=rag) if rag else facts
        fb = ''; rounds = []; draft = resp = None
        for att in range(2):
            prompt = K.build_prompt(facts, fb, task, mem_ctx, rag); txt, resp = MODEL_CALL(prompt); ok, bad = K.grounding(txt, gfacts); rounds.append(dict(bad_numbers=bad))
            if ok and txt.strip(): draft = txt.strip(); break
            fb = '직전 출력에 FACTS에 없는 숫자가 있습니다: ' + ', '.join(bad) + '. FACTS의 값만 그대로 쓰세요.' if bad else '직전 출력이 비어 있습니다.'
        def save(cur):
            R.ex(cur, 'INSERT INTO dbo.EvaluationRef(agentRunId, evaluationId, evaluatorVersion, sourceVersions, numericResult, citationResult, schemaResult, detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', (rid, str(uuid.uuid4()), 'grounding-1', json.dumps({K.TASKS[task][1]: run_id}), 'passed' if draft else 'failed', 'passed' if draft else 'not_run', 'passed', json.dumps(dict(rounds=rounds, memory=mem_state, rag=rag_state, ragSources=[x['source'] for x in rag]), ensure_ascii=False)))
            if draft: R.ex(cur, 'INSERT INTO dbo.DraftArtifact(agentRunId, artifactId, facts, citations, draftText, sourceVersions, classification, modelDeployment, responseModel, responseId, usage, status, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (rid, str(uuid.uuid4()), json.dumps(facts, ensure_ascii=False), json.dumps([dict(owner=K.TASKS[task][1], id=run_id, metrics=list(facts['values']) if isinstance(facts.get('values'), dict) else [])] + [dict(owner='AI-SEARCH', id=x['source'], section=x['section']) for x in rag]), draft, json.dumps({K.TASKS[task][1]: run_id}), 'DRAFT-SIMULATED', MODEL, (resp or {}).get('model'), (resp or {}).get('id'), json.dumps((resp or {}).get('usage')), 'DRAFT', ts()))
        R.tx(save); setstate(rid, 'DRAFT' if draft else 'BLOCKED', '' if draft else '초안이 숫자 근거 검사를 통과하지 못했습니다(FACTS 외 숫자). 값을 보충하지 않았습니다.', cid)
        remember(rid, task, run_id, 'DRAFT' if draft else 'BLOCKED', draft, cid)
    except Exception as e:
        try: setstate(rid, 'FAILED', ('%s: %s' % (type(e).__name__, e))[:190], cid)
        except Exception: pass
def work_case(rid, run_id, cid, question, history, reason=''):
    """거래 건 질의응답: proc-api의 건 요약(규칙 판정 포함)과 해당 포지션 계산 결과(읽기 2회)만 FACTS로 쓰고, 질문에 답하는 초안을 만든다. 승인·실행·쓰기 도구 없음, 숫자는 FACTS(+질문에 적힌 숫자)만 허용."""
    task = 'ask_procurement_case'
    try:
        R.tx(lambda cur: R.ex(cur, 'UPDATE dbo.AgentRun SET state=%s, updatedAt=%s WHERE agentRunId=%s AND state=%s', ('RUNNING', ts(), rid, 'ACCEPTED')))
        base = os.environ.get('PROC_API_URL', '').rstrip('/'); seq = [0]
        def audit(tid, url, st, body):
            seq[0] += 1; n = seq[0]
            R.tx(lambda cur: R.ex(cur, 'INSERT INTO dbo.ToolCallAudit(agentRunId, toolCallId, auditSequence, toolId, requestDigest, resultDigest, effectClass, phase, status, recordedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (rid, str(uuid.uuid4()), n, tid, sha(url), sha(body) if st == 200 else None, 'READ', 'COMPLETED', 'ok' if st == 200 else 'http_%s' % st, ts())))
        u1 = base + '/v1/intent-summaries?ops=' + urllib.parse.quote(run_id); st, b1 = FETCH(u1); audit('TOOL03.get_case', u1, st, b1)
        if st != 200: return setstate(rid, 'BLOCKED', '거래 건 요약 조회 실패(%s) — 근거 없음, 값 보충 안 함' % st, cid)
        items = (json.loads(b1) or {}).get('items') or []; item = items[0] if items else None
        pos = K.case_position(item); pf = None
        if pos:
            u2 = base + '/v1/allowance-positions/' + pos[1]; st2, b2 = FETCH(u2); audit('TOOL03.get_allowance' if pos[0] == 'kr' else 'TOOL03.get_gx', u2, st2, b2)
            if st2 == 200: pj = json.loads(b2); pf = K.facts_allowance(pj) if pos[0] == 'kr' else K.facts_site_position(pj)
        facts = K.facts_case(item, pf)
        if facts is None: return setstate(rid, 'BLOCKED', '이 거래 건의 요약을 읽지 못했습니다(소유 서비스에 값 없음) — 값을 보충하지 않았습니다', cid)
        facts['positionState'] = 'ok' if pf else ('unavailable' if pos else 'not-applicable')
        fq = dict(facts, question=question); (fq.update(requesterReason=reason) if reason else None); fb = ''; rounds = []; draft = resp = None
        for att in range(2):
            prompt = K.build_case_prompt(facts, question, history, fb, reason); txt, resp = MODEL_CALL(prompt); ok, bad = K.grounding(txt, fq); rounds.append(dict(bad_numbers=bad))
            if ok and txt.strip(): draft = txt.strip(); break
            fb = '직전 출력에 FACTS에 없는 숫자가 있습니다: ' + ', '.join(bad) + '. FACTS의 값만 그대로 쓰세요.' if bad else '직전 출력이 비어 있습니다.'
        def save(cur):
            R.ex(cur, 'INSERT INTO dbo.EvaluationRef(agentRunId, evaluationId, evaluatorVersion, sourceVersions, numericResult, citationResult, schemaResult, detail) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', (rid, str(uuid.uuid4()), 'grounding-1', json.dumps({'S04': run_id}), 'passed' if draft else 'failed', 'passed' if draft else 'not_run', 'passed', json.dumps(dict(rounds=rounds, memory='skipped', rag='skipped'), ensure_ascii=False)))
            if draft: R.ex(cur, 'INSERT INTO dbo.DraftArtifact(agentRunId, artifactId, facts, citations, draftText, sourceVersions, classification, modelDeployment, responseModel, responseId, usage, status, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (rid, str(uuid.uuid4()), json.dumps(fq, ensure_ascii=False), json.dumps([dict(owner='S04', id=run_id, metrics=['case', 'rule', 'position'])]), draft, json.dumps({'S04': run_id}), 'DRAFT-SIMULATED', MODEL, (resp or {}).get('model'), (resp or {}).get('id'), json.dumps((resp or {}).get('usage')), 'DRAFT', ts()))
        R.tx(save); setstate(rid, 'DRAFT' if draft else 'BLOCKED', '' if draft else '답변이 숫자 근거 검사를 통과하지 못했습니다(FACTS 외 숫자). 값을 보충하지 않았습니다.', cid)
    except Exception as e:
        try: setstate(rid, 'FAILED', ('%s: %s' % (type(e).__name__, e))[:190], cid)
        except Exception: pass
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    try: K.validate_run(body)
    except K.Reject as e: raise ApiError(e.status, e.code, e.msg)
    ok_scope = {'judge_gx_position': ('KR-01', 'JP-01', 'JP-02', 'JP-03', 'JP-04'), 'judge_sg_tax_position': ('KR-01', 'SG-01', 'SG-02', 'SG-03')}.get(body['task'], ('KR-01',))   # JP·SG 판단은 승인된 집계(S10)만 본사에서 다룸
    if body['plantScope'] not in ok_scope: raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 과제의 허용 범위는 %s입니다.' % ', '.join(ok_scope))
    ref = body['contextRefs'][0]
    try: uuid.UUID(str(ref['id']))
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'contextRefs[0].id는 run UUID입니다.')
    rd = sha(canon(body)); rid = str(uuid.uuid4()); t0 = now()
    def f(cur):
        R.ex(cur, 'SELECT agentRunId, requestDigest, state, version FROM dbo.AgentRun WHERE country=%s AND orgId=%s AND subjectRef=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem[:100])); x = cur.fetchall()
        if x:
            if x[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, x[0][0], False
        R.ex(cur, 'INSERT INTO dbo.AgentRun(agentRunId, country, orgId, agentId, task, subjectRef, idemKey, requestDigest, purpose, plantScope, contextRefs, modelPolicyRef, promptVersion, toolSchemaVersion, state, version, createdAt, deadline, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)',
            (rid, COUNTRY, ORG, body['role'], body['task'], actor, idem[:100], rd, body['purpose'][:40], body['plantScope'], json.dumps(body['contextRefs']), 'fdry-krc-02/' + MODEL, PROMPT_V, TOOL_V, 'ACCEPTED', ts(t0), ts(t0 + dt.timedelta(minutes=10)), ts(t0)))
        A(cur, actor, 'AGENT_RUN_CREATE', rid, body['task'], cid, after='1'); return 202, rid, True
    c, rid2, new = R.tx(f)
    if new:
        if body['task'] == 'ask_procurement_case': threading.Thread(target=work_case, args=(rid2, str(ref['id']), cid, body['question'].strip(), body.get('history') or [], (body.get('requesterReason') or '').strip()), daemon=True).start()
        else: threading.Thread(target=work, args=(rid2, str(ref['id']), cid, body['task']), daemon=True).start()
    return c, dict(agentRunId=rid2, state='ACCEPTED' if new else None, version=1, statusUrl='/agent-runs/' + rid2, correlationId=cid, note='202는 접수이며 효과 성공이 아닙니다. 결과는 DRAFT입니다.')
def get_run(rid):
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'agentRunId 형식이 올바르지 않습니다.')
    def f(cur):
        R.ex(cur, 'SELECT agentRunId, agentId, task, state, version, blockedReason, plantScope, purpose, createdAt, updatedAt, modelPolicyRef, promptVersion FROM dbo.AgentRun WHERE agentRunId=%s', (rid,)); x = cur.fetchall()
        if not x: return None
        x = x[0]; d = dict(agentRunId=x[0], role=x[1], task=x[2], state=x[3], version=x[4], blockedReasons=[x[5]] if x[5] else [], plantScope=x[6], purpose=x[7], createdAt=iso(x[8]), updatedAt=iso(x[9]), modelPolicyRef=x[10], promptVersion=x[11], draft=None, classification='DRAFT-SIMULATED', ownerOperationRefs=[])
        R.ex(cur, 'SELECT artifactId, facts, citations, draftText, responseModel, responseId, usage, status FROM dbo.DraftArtifact WHERE agentRunId=%s', (rid,)); a = cur.fetchall()
        if a: d['draft'] = dict(artifactId=a[0][0], text=a[0][3], status=a[0][7], label='초안(DRAFT) · 합성 모의 자료 기반'); d['facts'] = json.loads(a[0][1]); d['citations'] = json.loads(a[0][2]); d['usage'] = dict(model=a[0][4], responseId=a[0][5], tokens=json.loads(a[0][6]) if a[0][6] else None)
        R.ex(cur, 'SELECT toolId, status FROM dbo.ToolCallAudit WHERE agentRunId=%s', (rid,)); d['toolCalls'] = [dict(toolId=t[0], status=t[1]) for t in cur.fetchall()]
        R.ex(cur, 'SELECT numericResult, detail FROM dbo.EvaluationRef WHERE agentRunId=%s', (rid,)); e = cur.fetchall(); det = json.loads(e[0][1]) if e else None; d['evaluation'] = (dict(numeric=e[0][0], rounds=det['rounds'] if isinstance(det, dict) else det, memory=det.get('memory') if isinstance(det, dict) else None)) if e else None
        return d
    d = R.tx(f)
    if not d: raise ApiError(404, 'NOT_FOUND', '해당 실행이 없습니다.')
    return d
def stop(rid, body, h, cid):
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    if not isinstance(body.get('expectedVersion'), int) or not body.get('reason'): raise ApiError(400, 'BAD_REQUEST', 'expectedVersion(정수), reason 필요')
    def f(cur):
        R.ex(cur, 'SELECT state, version FROM dbo.AgentRun WHERE agentRunId=%s', (rid,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 실행이 없습니다.')
        if x[0][1] != body['expectedVersion']: raise ApiError(412, 'CAS_MISMATCH', '현재 version과 다릅니다(%s).' % x[0][1])
        if x[0][0] in ('DRAFT', 'BLOCKED', 'FAILED', 'STOPPED'): raise ApiError(409, 'TERMINAL_STATE', '이미 종료된 실행입니다.')
        R.ex(cur, 'UPDATE dbo.AgentRun SET state=%s, version=%s, updatedAt=%s WHERE agentRunId=%s AND version=%s', ('STOP_REQUESTED', x[0][1] + 1, ts(), rid, x[0][1])); A(cur, actor, 'AGENT_STOP_REQUEST', rid, body['reason'], cid, str(x[0][1]), str(x[0][1] + 1)); return dict(agentRunId=rid, state='STOP_REQUESTED', version=x[0][1] + 1, note='새 호출 중단 요청 접수입니다(외부 거래 취소 아님).')
    return R.tx(f)
SEARCH_URL = os.environ.get('AI_SEARCH_ENDPOINT', '').rstrip('/'); SEARCH_INDEX = os.environ.get('AI_SEARCH_INDEX', 'ama-knowledge-v1')
def _search_token():
    ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=https://search.azure.com&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
EMBED_URL = os.environ.get('AI_EMBED_URL', ''); VEC = {'used': False, 'error': None}
def _mi_token(resource):
    ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=' + resource + '&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
def EMBED_CALL(q):
    """질의 임베딩(Foundry emb-3-small, 관리 ID·Cognitive Services OpenAI User). 색인 때와 같은 모델·1536차원이어야 한다."""
    rq = urllib.request.Request(EMBED_URL, data=json.dumps({'input': [q[:2000]]}).encode(), method='POST', headers={'Authorization': 'Bearer ' + _mi_token('https://cognitiveservices.azure.com'), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(rq, timeout=20) as r: v = json.loads(r.read())['data'][0]['embedding']
    if len(v) != 1536: raise ValueError('dims')
    return v
def SEARCH_CALL(q, top, flt=None):
    """AI Search 시맨틱(+벡터) 검색(읽기 전용; Search Index Data Reader 관리 ID). 벡터는 임베딩이 성공할 때만 더하며, 실패는 숨기지 않고 응답의 vector=false·vectorError로 드러낸다."""
    body = {'search': q, 'queryType': 'semantic', 'semanticConfiguration': 'sem1', 'select': 'title,section,source,sourceUrl,docType,country,siteId,period,chunkNo,content', 'top': top}
    if flt: body['filter'] = flt
    VEC['used'], VEC['error'] = False, None
    if EMBED_URL:
        try: body['vectorQueries'] = [{'kind': 'vector', 'vector': EMBED_CALL(q), 'fields': 'contentVector', 'k': max(top * 3, 10)}]; VEC['used'] = True
        except urllib.error.HTTPError as e: VEC['error'] = 'HTTP_%s' % e.code
        except Exception as e: VEC['error'] = type(e).__name__
    rq = urllib.request.Request('%s/indexes/%s/docs/search?api-version=2024-07-01' % (SEARCH_URL, SEARCH_INDEX), data=json.dumps(body, ensure_ascii=False).encode('utf-8'), method='POST', headers={'Authorization': 'Bearer ' + _search_token(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(rq, timeout=20) as r: return json.loads(r.read())
def _filter(qs):
    """docType·country·siteId만 허용(영숫자·하이픈) — OData 필터 주입을 막는다."""
    parts = []
    for k in ('docType', 'country', 'siteId'):
        v = (qs.get(k) or [''])[0]
        if v:
            if not re.fullmatch(r'[A-Za-z0-9\-]{1,20}', v): raise ApiError(400, 'BAD_REQUEST', k + ' 형식이 올바르지 않습니다.')
            parts.append("%s eq '%s'" % (k, v))
    return ' and '.join(parts) or None
def RAG_FOR(task, facts):
    """판단 설명에 쓸 근거 검색(법령·5년 이력). 실패는 숨기지 않고 상태로 남기며, 근거 없이도 초안은 FACTS만으로 만든다."""
    Q = {'judge_allowance_position': (('배출권 이월 한도 순매도량 잉여업체', "docType eq 'law' and country eq 'KR'"), ('KR-01 연간 배출량 원단위 요약', "docType eq 'history' and siteId eq 'KR-01'")),
         'judge_gx_position': (('排出枠 保有 義務 翌年度 一月三十一日 参考上限取引価格', "docType eq 'law' and country eq 'JP'"), ('일본 공장 연간 배출량 요약', "docType eq 'history' and country eq 'JP'")),
         'judge_sg_tax_position': (('carbon tax rate ICC offset 5% payment deadline', "docType eq 'law' and country eq 'SG'"), ('싱가포르 공장 연간 배출량 요약', "docType eq 'history' and country eq 'SG'"))}
    if task not in Q or not SEARCH_URL: return 'skipped', []
    out = []
    try:
        for q, flt in Q[task]:
            d = SEARCH_CALL(q, 2, flt)
            for x in d.get('value', [])[:2]: out.append(dict(source=x.get('source'), section=x.get('section'), docType=x.get('docType'), text=(x.get('content') or '')[:700]))
        return ('ok' if out else 'empty'), out
    except Exception as e: return 'failed:' + type(e).__name__, []
def knowledge_search(qs):
    q = (qs.get('q') or [''])[0].strip()
    if not SEARCH_URL: raise ApiError(503, 'SEARCH_NOT_CONFIGURED', 'AI Search 엔드포인트가 구성되지 않았습니다.')
    if len(q) < 2 or len(q) > 200: raise ApiError(400, 'BAD_REQUEST', 'q는 2~200자여야 합니다.')
    try: top = max(1, min(8, int((qs.get('top') or ['5'])[0])))
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'top은 정수입니다.')
    flt = _filter(qs)
    try: d = SEARCH_CALL(q, top, flt) if flt else SEARCH_CALL(q, top)
    except urllib.error.HTTPError as e:
        try: why = (json.loads(e.read()).get('error') or {}).get('message', '')[:140]
        except Exception: why = ''
        raise ApiError(503, 'SEARCH_UNAVAILABLE', '검색을 완료하지 못했습니다(HTTP %s %s).' % (e.code, why), e.code in (429, 500, 502, 503))
    except Exception as e: raise ApiError(503, 'SEARCH_UNAVAILABLE', '검색을 완료하지 못했습니다(%s).' % type(e).__name__, True)
    items = [dict(title=x.get('title'), section=x.get('section'), source=x.get('source'), sourceUrl=x.get('sourceUrl'), docType=x.get('docType'), country=x.get('country'), siteId=x.get('siteId'), chunkNo=x.get('chunkNo'), snippet=(x.get('content') or '')[:280], score=x.get('@search.score'), rerankerScore=x.get('@search.rerankerScore')) for x in d.get('value', [])]
    return 200, dict(query=q, count=len(items), items=items, vector=VEC['used'], vectorError=VEC['error'], note='색인은 설계 문서(파일/Git 정본)의 검색용 사본입니다. 근거는 source 경로의 원문으로 확인하세요.')
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/agent-runs': return create(body, h, cid)
    if m == 'GET' and len(P) == 3 and P[1] == 'agent-runs': return 200, get_run(P[2])
    if m == 'POST' and len(P) == 4 and P[1] == 'agent-runs' and P[3] == 'stop-requests': return 202, stop(P[2], body, h, cid)
    if m == 'GET' and p == '/agent-runs':
        rows = R.tx(lambda cur: (R.ex(cur, R.top('SELECT agentRunId, state, task, createdAt FROM dbo.AgentRun ORDER BY createdAt DESC', 20)), cur.fetchall())[1]); return 200, dict(items=[dict(agentRunId=r[0], state=r[1], task=r[2], createdAt=iso(r[3])) for r in rows])
    if m == 'GET' and p == '/knowledge/search': return knowledge_search(qs)
    if m == 'GET' and p == '/agent-ping':
        t0 = time.time()
        try: txt, r = MODEL_CALL('한국어로 "응답 확인"이라고만 답하세요.'); return 200, dict(ok=True, deployment=MODEL, responseModel=r.get('model'), text=txt.strip()[:60], latencyMs=int((time.time() - t0) * 1000))
        except Exception as e: raise ApiError(503, 'MODEL_UNAVAILABLE', ('모델 호출 실패: %s' % type(e).__name__), True)
    if m == 'GET' and p == '/memory/status':   # Honcho 연결 점검(읽기): 워크스페이스·peer·세션 수
        if not MEM.enabled: return 200, dict(state='disabled', note='HONCHO_URL/JWT 미설정')
        try:
            c1, d1 = MEM._call('POST', '/v3/workspaces/list', {}); out = dict(state='ok' if c1 == 200 else 'error', workspaces=[x.get('id') for x in (d1.get('items') or [])] if c1 == 200 else None, http=c1)
            if c1 == 200 and MEM.ws in out['workspaces']:
                c2, d2 = MEM._call('POST', '/v3/workspaces/%s/peers/list' % MEM.ws, {}); c3, d3 = MEM._call('POST', '/v3/workspaces/%s/sessions/list' % MEM.ws, {})
                out.update(peers=[x.get('id') for x in (d2.get('items') or [])] if c2 == 200 else c2, sessions=(d3.get('total') if c3 == 200 else c3))
            return 200, out
        except Exception as e: raise ApiError(503, 'MEMORY_UNAVAILABLE', '기억 저장소 연결 실패: %s' % type(e).__name__, True)
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.AgentRun), (SELECT COUNT(*) FROM dbo.RunAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, runs=s[0], audits=s[1], errors=R.err, last_err=R.last_err), model=MODEL, mode='AI-A01~A05 초안 전용(읽기 도구 5종, 실행·승인 권한 없음)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
