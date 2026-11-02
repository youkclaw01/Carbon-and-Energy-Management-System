import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'planapi'))
import plan_app as PL
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE PlanningInput(country, orgId, kind, inputId, version, contentJson, digest, createdAt, PRIMARY KEY(country,orgId,kind,inputId,version));
CREATE TABLE Scenario(scenarioId, scenarioVersion, country, orgId, plantId, principal, idemKey, requestDigest, planRef, constraintRef, priceRef, fxRef, baselineRef, objective, typedOverrides, calculationScope, inputDigest, periodStart, periodEnd, reportingTimezone, createdAt, PRIMARY KEY(scenarioId,scenarioVersion), UNIQUE(country,orgId,principal,idemKey));
CREATE TABLE SimulationRun(runId TEXT PRIMARY KEY, scenarioId, scenarioVersion, solverVersion, status, stateVersion, resultKind DEFAULT 'SIMULATED', publishable DEFAULT 0, feasibility, metricStatus, resultJson, resultHash, blockedReason, checkedAt);
CREATE TABLE PlanningAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
PL.R = Repo('sqlite', cf); srv = make_server(8854, PL.route, PL.health, PL.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8854'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
PLAN = dict(id='plan-2610', version=1, items=[dict(processId='EAF', goodQty='950', unit='t'), dict(processId='ROLL', goodQty='900', unit='t')])
CONS = dict(id='cons-1', version=1, processes=[dict(processId='EAF', unit='t', yieldRatio='0.95', capacityQty='1100', energyKwhPerInputUnit='400'), dict(processId='ROLL', unit='t', yieldRatio='0.9', capacityQty='1100', energyKwhPerInputUnit='120')])
PRICE = dict(id='price-1', version=1, unitPrice='120', currency='KRW', perUnit='kWh')
BODY = dict(schemaVersion='1', purpose='monthly-planning', objective='min-energy-cost', calculationScope='ENERGY_COST_ONLY', reportCurrency='KRW', scope=dict(country='KR', plantId='KR-01', periodStart='2026-11-01T00:00:00Z', periodEnd='2026-12-01T00:00:00Z', reportingTimezone='Asia/Seoul'), plan=PLAN, constraints=CONS, price=PRICE)
def post(b, k, a='planner1'): return call('POST', '/v1/scenarios', b, {'Idempotency-Key': k, 'X-Actor': a})
c, d = call('POST', '/v1/scenarios', BODY); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = post(BODY, 's1'); chk('202: SUCCEEDED·SIMULATED·비발행·에너지 비용 62400000 KRW·totalCost null', c == 202 and d['status'] == 'SUCCEEDED' and d['publishable'] is False and d['result']['energyCostTotal']['value'] == '62400000.000' and d['result']['totalCost'] is None and d['metricStatus']['emissions'] == 'NOT_REQUESTED', (c, d))
rid, sid, rh = d['runId'], d['scenarioRef']['scenarioId'], d['scenarioRef']['resultHash']
chk('S04 인수용 고정 참조: scenarioRef{id,version,resultHash}·inputDigest·plan/constraint/price 버전 참조, 조달 인수 불가 표시', d['inputDigest'] and d['planRef'] == 'plan-2610@1' and d['priceRef'] == 'price-1@1' and d['eligibility']['procurementHandoff'] is False)
c, d2 = post(BODY, 's1'); chk('같은 키·같은 내용 → 200 같은 run', c == 200 and d2['runId'] == rid and d2['replay'] is True, (c, d2))
c, d2 = post(dict(BODY, objective='other'), 's1'); chk('같은 키·다른 내용 → 409', c == 409, d2)
c, d2 = post(dict(BODY, constraints=dict(CONS, processes=[dict(CONS['processes'][0], capacityQty='900'), CONS['processes'][1]])), 's2'); chk('같은 id·version의 다른 내용 제출 → 409 REF_CONFLICT(버전 덮어쓰기 금지)', c == 409 and d2['code'] == 'REF_CONFLICT', (c, d2))
c, d2 = post(dict(BODY, constraints=dict(CONS, version=2, processes=[dict(CONS['processes'][0], capacityQty='900'), CONS['processes'][1]])), 's3'); chk('새 버전(v2) 제약으로 용량 초과 → 202 INFEASIBLE·위반 목록·인수 불가', c == 202 and d2['status'] == 'INFEASIBLE' and d2['feasibility'] is False and d2['result']['violations'][0]['constraintId'] == 'EAF:capacity', (c, d2))
c, d2 = post(dict(BODY, calculationScope='ENERGY_CARBON'), 's4'); chk('ENERGY_CARBON → BLOCKED_DEPENDENCY(수치·탄소비용 없음, 성공 아님)', c == 202 and d2['status'] == 'BLOCKED_DEPENDENCY' and 'result' not in d2 and d2['metricStatus']['emissions'] == 'BLOCKED_DEPENDENCY', (c, d2))
c, d2 = post(dict(BODY, calculationScope='ENERGY_X'), 's5'); chk('미지원 범위 422', c == 422 and d2['code'] == 'UNSUPPORTED_CALCULATION_SCOPE', d2)
c, d2 = post(dict(BODY, typedOverrides=[dict(a=1)]), 's6'); chk('typedOverrides 거절 422(허용 규칙 미합의)', c == 422 and d2['code'] == 'OVERRIDE_UNSUPPORTED', d2)
c, d2 = post(dict(BODY, price=dict(PRICE, id='price-usd', currency='USD', unitPrice='0.1')), 's7'); chk('환율 없는 외화 가격 → 422 FX_MISSING(1로 대체 안 함)', c == 422 and d2['code'] == 'FX_MISSING', (c, d2))
c, d2 = post(dict(BODY, scope=dict(BODY['scope'], plantId='JP-01')), 's8'); chk('다른 국가 공장 422', c == 422, d2)
c, d2 = post(dict(BODY, scope=dict(BODY['scope'], periodEnd='2026-10-01T00:00:00Z')), 's9'); chk('기간 역전 400', c == 400, d2)
c, d = call('GET', '/v1/scenarios/' + sid + '?scenarioVersion=1'); chk('시나리오 조회: 같은 resultHash', c == 200 and d['scenarioRef']['resultHash'] == rh, d)
c, d = call('GET', '/v1/simulation-runs/' + rid); chk('실행 조회', c == 200 and d['runId'] == rid, d)
c, d = call('GET', '/v1/simulation-runs/' + str(uuid.uuid4())); chk('없는 실행 404', c == 404, d)
c, d = call('POST', '/v1/simulation-runs/' + rid + '/cancellations', dict(expectedVersion=1, reason='x')); chk('종료된 실행 취소 409', c == 409 and d['code'] == 'TERMINAL_STATE', (c, d))
rows = PL.R.tx(lambda cur: (PL.R.ex(cur, 'SELECT prevHash, hash FROM dbo.PlanningAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and len(rows) >= 3)
c, d = call('GET', '/health'); chk('health', c == 200 and 'ENERGY_COST_ONLY' in d['mode'], d)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
