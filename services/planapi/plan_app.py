#!/usr/bin/env python3
"""plan-api — S03 API04 POST /v1/scenarios · GET /v1/scenarios/{id} · GET /v1/simulation-runs/{id} · 취소 (체크리스트 2-9-2~2-9-4). 설계: design/services/S03 §3~5.
계산은 결정론적 ENERGY_COST_ONLY만. ENERGY_CARBON은 S02 what-if 계약 미합의라 BLOCKED_DEPENDENCY 실행(수치·탄소비용 없음). 결과는 SIMULATED·publishable=false이며 조달(S04) 인수·반출·공개는 열지 않는다.
편차: S12 미구축이라 같은 요청 안에서 동기 계산 후 202로 응답(statusUrl 제공). 입력 4종은 요청에 인라인으로 받아 PlanningInput에 불변 버전으로 저장. 사용자 인가는 S07 이후(X-Actor 미검증 라벨)."""
import os, sys, json, uuid, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import plan_core as K
VERSION = 'plan-api/0.1'; COUNTRY, ORG = 'KR', 'AMA-KR'; STATS = {}; R = None
def A(cur, actor, action, target, reason='', cid=None, before=None, after=None):
    R.chain(cur, 'PlanningAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def pdt(s, name):
    try: return dt.datetime.strptime(s.replace('Z', '').split('.')[0], '%Y-%m-%dT%H:%M:%S')
    except Exception: raise ApiError(400, 'BAD_REQUEST', name + '은 UTC ISO여야 합니다.')
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]; sc = body.get('scope') or {}
    for k in ('schemaVersion', 'purpose', 'objective', 'calculationScope', 'reportCurrency'):
        if not body.get(k): raise ApiError(400, 'BAD_REQUEST', k + ' 필요')
    for k in ('plan', 'constraints', 'price'):
        if not isinstance(body.get(k), dict) or not body[k].get('id') or not isinstance(body[k].get('version'), int): raise ApiError(400, 'BAD_REQUEST', k + '{id, version(정수), …} 필요')
    if body['calculationScope'] not in ('ENERGY_COST_ONLY', 'ENERGY_CARBON'): raise ApiError(422, 'UNSUPPORTED_CALCULATION_SCOPE', '지원하지 않는 계산 범위입니다.')
    if sc.get('plantId') != 'KR-01' or sc.get('country', COUNTRY) != COUNTRY: raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역 DB03은 KR-01만 다룹니다.')
    ps, pe = pdt(str(sc.get('periodStart', '')), 'scope.periodStart'), pdt(str(sc.get('periodEnd', '')), 'scope.periodEnd')
    if not ps < pe: raise ApiError(400, 'BAD_PERIOD', 'periodStart < periodEnd(시작 포함·종료 제외)여야 합니다.')
    plan, cons, price, fx = body['plan'], body['constraints'], body['price'], body.get('fx')
    if body.get('typedOverrides'): raise ApiError(422, 'OVERRIDE_UNSUPPORTED', 'typedOverrides는 허용 목록(생산량·수율·가격·환율)과 digest 결합 규칙 합의 전이라 받지 않습니다.')
    rd = sha(canon(body)); sid = str(uuid.uuid4()); runid = str(uuid.uuid4())
    if body['calculationScope'] == 'ENERGY_CARBON': status, res, blocked, feas = 'BLOCKED_DEPENDENCY', None, 'S02 what-if(비발행) 계산 계약 미합의 — 배출·탄소비용·전체 totalCost 없음', None
    else:
        try: res = K.compute(plan, cons, price, fx, body['reportCurrency'])
        except K.Reject as e: raise ApiError(e.status, e.code, e.msg + (' (' + ', '.join(e.fields) + ')' if e.fields else ''))
        status = 'SUCCEEDED' if res['feasibility'] else 'INFEASIBLE'; blocked, feas = None, res['feasibility']
    inputs = [('plan', plan), ('constraints', cons), ('price', price)] + ([('fx', fx)] if fx else [])
    indig = K.sha({k: dict(id=v['id'], version=v['version'], digest=K.sha(v)) for k, v in inputs}); t = ts()
    def f(cur):
        R.ex(cur, 'SELECT scenarioId, requestDigest FROM dbo.Scenario WHERE country=%s AND orgId=%s AND principal=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem[:100])); x = cur.fetchall()
        if x:
            if x[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            R.ex(cur, 'SELECT runId FROM dbo.SimulationRun WHERE scenarioId=%s', (x[0][0],)); return 200, x[0][0], cur.fetchall()[0][0], True
        for kind, v in inputs:
            R.ex(cur, 'SELECT digest FROM dbo.PlanningInput WHERE country=%s AND orgId=%s AND kind=%s AND inputId=%s AND version=%s', (COUNTRY, ORG, kind, v['id'], v['version'])); y = cur.fetchall()
            if y and y[0][0] != K.sha(v): raise ApiError(409, 'REF_CONFLICT', '%s %s v%s는 이미 다른 내용으로 고정되어 있습니다(새 버전으로 제출).' % (kind, v['id'], v['version']))
            if not y: R.ex(cur, 'INSERT INTO dbo.PlanningInput(country, orgId, kind, inputId, version, contentJson, digest, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', (COUNTRY, ORG, kind, v['id'], v['version'], json.dumps(v, ensure_ascii=False), K.sha(v), t))
        R.ex(cur, 'INSERT INTO dbo.Scenario(scenarioId, scenarioVersion, country, orgId, plantId, principal, idemKey, requestDigest, planRef, constraintRef, priceRef, fxRef, baselineRef, objective, typedOverrides, calculationScope, inputDigest, periodStart, periodEnd, reportingTimezone, createdAt) VALUES (%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (sid, COUNTRY, ORG, 'KR-01', actor, idem[:100], rd, '%s@%s' % (plan['id'], plan['version']), '%s@%s' % (cons['id'], cons['version']), '%s@%s' % (price['id'], price['version']), ('%s@%s' % (fx['id'], fx['version'])) if fx else 'none', None, body['objective'][:40], '[]', body['calculationScope'], indig, ts(ps), ts(pe), sc.get('reportingTimezone', 'Asia/Seoul'), t))
        R.ex(cur, 'INSERT INTO dbo.SimulationRun(runId, scenarioId, scenarioVersion, solverVersion, status, stateVersion, feasibility, metricStatus, resultJson, resultHash, blockedReason, checkedAt) VALUES (%s,%s,1,%s,%s,1,%s,%s,%s,%s,%s,%s)',
            (runid, sid, K.SOLVER, status, None if feas is None else (1 if feas else 0), json.dumps(res['metricStatus'] if res else dict(energyCost='NOT_REQUESTED', emissions='BLOCKED_DEPENDENCY', carbonCost='BLOCKED_DEPENDENCY')), json.dumps(res, ensure_ascii=False) if res else None, res['resultHash'] if res else None, blocked, t))
        A(cur, actor, 'SCENARIO_CREATE', sid, status, cid, after='1'); return 202, sid, runid, False
    c, sid2, run2, replay = R.tx(f)
    return c, run_view(run2, replay=replay)
def run_view(runid, replay=False):
    def f(cur):
        R.ex(cur, 'SELECT r.runId, r.scenarioId, r.scenarioVersion, r.status, r.stateVersion, r.feasibility, r.metricStatus, r.resultJson, r.resultHash, r.blockedReason, r.checkedAt, s.inputDigest, s.planRef, s.constraintRef, s.priceRef, s.fxRef, s.calculationScope FROM dbo.SimulationRun r JOIN dbo.Scenario s ON s.scenarioId=r.scenarioId AND s.scenarioVersion=r.scenarioVersion WHERE r.runId=%s', (runid,)); return cur.fetchall()
    x = R.tx(f)
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 실행이 없습니다.')
    x = x[0]; d = dict(runId=x[0], scenarioRef=dict(scenarioId=x[1], scenarioVersion=x[2], resultHash=x[8]), status=x[3], stateVersion=x[4], resultKind='SIMULATED', publishable=False, calculationScope=x[16], metricStatus=json.loads(x[6]), feasibility=None if x[5] is None else bool(x[5]), inputDigest=x[11],
                      planRef=x[12], constraintRef=x[13], priceRef=x[14], fxRef=x[15], blockedReason=x[9], checkedAt=iso(x[10]), statusUrl='/v1/simulation-runs/' + x[0], eligibility=dict(procurementHandoff=False, reason='S04 인수 계약 미합의'), replay=replay)
    if x[7]: d['result'] = json.loads(x[7])
    return d
def get_scenario(sid, qs):
    try: uuid.UUID(sid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'scenarioId 형식이 올바르지 않습니다.')
    x = R.tx(lambda cur: (R.ex(cur, 'SELECT runId FROM dbo.SimulationRun WHERE scenarioId=%s AND scenarioVersion=%s', (sid, int((qs.get('scenarioVersion') or ['1'])[0]))), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 시나리오가 없습니다.')
    return run_view(x[0][0])
def cancel(rid, body, h, cid):
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    if not isinstance(body.get('expectedVersion'), int) or not body.get('reason'): raise ApiError(400, 'BAD_REQUEST', 'expectedVersion(정수), reason 필요')
    def f(cur):
        R.ex(cur, 'SELECT status, stateVersion FROM dbo.SimulationRun WHERE runId=%s', (rid,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 실행이 없습니다.')
        if x[0][1] != body['expectedVersion']: raise ApiError(412, 'CAS_MISMATCH', '현재 stateVersion과 다릅니다(%s).' % x[0][1])
        if x[0][0] in ('SUCCEEDED', 'INFEASIBLE', 'CANCELLED', 'FAILED', 'BLOCKED_DEPENDENCY'): raise ApiError(409, 'TERMINAL_STATE', '이미 종료된 실행은 취소할 수 없습니다(상태: %s).' % x[0][0])
        raise ApiError(409, 'TERMINAL_STATE', 'unreachable')
    R.tx(f)
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/scenarios': return create(body, h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'scenarios': return 200, get_scenario(P[3], qs)
    if m == 'GET' and len(P) == 4 and P[2] == 'simulation-runs': return 200, run_view(P[3])
    if m == 'POST' and len(P) == 5 and P[2] == 'simulation-runs' and P[4] == 'cancellations': cancel(P[3], body, h, cid)
    if m == 'GET' and p == '/v1/scenarios':
        rows = R.tx(lambda cur: (R.ex(cur, R.top('SELECT runId FROM dbo.SimulationRun ORDER BY checkedAt DESC', 20)), cur.fetchall())[1]); return 200, dict(items=[run_view(r[0]) for r in rows])
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.Scenario), (SELECT COUNT(*) FROM dbo.PlanningInput), (SELECT COUNT(*) FROM dbo.PlanningAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, scenarios=s[0], inputs=s[1], audits=s[2], errors=R.err, last_err=R.last_err), mode='ENERGY_COST_ONLY(탄소 연계 차단)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
