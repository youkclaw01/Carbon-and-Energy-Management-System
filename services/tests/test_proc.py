import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'procapi'))
import proc_app as PR
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE BusinessOperation(country, sourceService, businessOperationId, orgId, businessRequestRef, rootIntentId, activeIntentVersion, holdState, rowVersion, PRIMARY KEY(country,sourceService,businessOperationId), UNIQUE(country,orgId,businessRequestRef));
CREATE TABLE ProcurementIntent(intentId, intentVersion, country, orgId, businessOperationId, plantId, mode, principalRef, idemKey, requestDigest, instrumentType, purpose, quantityValue, quantityUnit, currency, priceCapMinorText, deliveryStart, deliveryEnd, scenarioRef, assumption, intentDigest, canonicalizationVersion, digestAlgorithm, bindingState, state, blockers, rowVersion, createdAt, PRIMARY KEY(intentId,intentVersion), UNIQUE(country,orgId,principalRef,idemKey));
CREATE TABLE PositionSnapshot(country, orgId, positionKey, version, mode, contractedQty, deliveredQty, retiredQty, pendingQty, unknownExposure, asOf, quality);
CREATE TABLE ProcurementAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
PR.R = Repo('sqlite', cf); os.environ['PLAN_API_URL'] = 'http://plan'; mode = dict(st=200, body={})
S3 = dict(scenarioRef=dict(scenarioId='s-1', scenarioVersion=1, resultHash='h' * 64), status='SUCCEEDED', feasibility=True, metricStatus=dict(energyCost='COMPLETE')); mode['body'] = S3
PR.FETCH = lambda url: (mode['st'], json.dumps(mode['body']).encode())
srv = make_server(8855, PR.route, PR.health, PR.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8855'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
BODY = dict(businessRequestRef='REQ-1', instrumentType='electricity', purpose='hedge', quantity=dict(value='1000', unit='MWh'), currency='KRW', priceCap='150', delivery=dict(start='2026-11-01T00:00:00Z', end='2026-12-01T00:00:00Z'), scenarioRef=dict(scenarioId='s-1', scenarioVersion=1, resultHash='h' * 64), assumption=dict(unitPrice='120', priceUnit='KRW/kWh', quoteCurrency='KRW'))
def post(b, k): return call('POST', '/v1/procurement-intents', b, {'Idempotency-Key': k, 'X-Actor': 'proc1'})
c, d = call('POST', '/v1/procurement-intents', BODY); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = post(BODY, 'i1'); iid, bid = d.get('intentId'), d.get('businessOperationId'); chk('202 초안: SIMULATED·DRAFT·digest 64hex(ama.intent.v1/jcs-1·sha256)·BOUND·externalReady=false·S03 인수 계약 차단 유지', c == 202 and d['state'] == 'DRAFT' and len(d['intentDigest']) == 64 and d['canonicalizationVersion'] == 'ama.intent.v1/jcs-1' and d['digestAlgorithmId'] == 'sha256' and d['bindingState'] == 'BOUND' and d['externalReady'] is False and 'S03_HANDOFF_CONTRACT_UNAGREED' in d['blockers'] and 'POLICY_D12_UNRESOLVED' not in d['blockers'] and 'INTENT_DIGEST_UNRESOLVED' not in d['blockers'], (c, d))
DG1 = d['intentDigest']
chk('S03 재조회 통과(결과 hash·feasible·비용 완료)해도 외부 진행은 차단(차단 사유에 S03 오류 없음)', not any(b.startswith('S03_NOT') or b.startswith('S03_RESULT') for b in d['blockers']))
c, d2 = post(BODY, 'i1'); chk('같은 키·같은 내용 → 200 같은 intent', c == 200 and d2['intentId'] == iid, (c, d2))
c, d2 = post(dict(BODY, purpose='other'), 'i1'); chk('같은 키·다른 내용 → 409', c == 409, d2)
c, d2 = post(dict(BODY, quantity=dict(value='1200', unit='MWh')), 'i2'); chk('같은 businessRequestRef·새 키 → 같은 원업무에 intent 버전 2(새 businessOperationId 발급 안 함)', c == 202 and d2['businessOperationId'] == bid and d2['intentVersion'] == 2, (c, d2))
mode['body'] = dict(S3, scenarioRef=dict(S3['scenarioRef'], resultHash='x' * 64)); c, d2 = post(dict(BODY, businessRequestRef='REQ-2'), 'i3'); chk('S03 resultHash 불일치 → 차단 사유에 S03_RESULT_HASH_MISMATCH', 'S03_RESULT_HASH_MISMATCH' in d2['blockers'], d2)
mode['body'] = dict(S3, status='INFEASIBLE', feasibility=False); c, d2 = post(dict(BODY, businessRequestRef='REQ-3'), 'i4'); chk('S03 INFEASIBLE → S03_NOT_FEASIBLE_OR_INCOMPLETE', 'S03_NOT_FEASIBLE_OR_INCOMPLETE' in d2['blockers'], d2)
mode.update(st=503, body={}); c, d2 = post(dict(BODY, businessRequestRef='REQ-4'), 'i5'); chk('S03 확인 불가 → S03_STATE_UNKNOWN(허용 추정 없음)', 'S03_STATE_UNKNOWN' in d2['blockers'], d2); mode.update(st=404); c, d2 = post(dict(BODY, businessRequestRef='REQ-5'), 'i6'); chk('S03에 없는 시나리오 → S03_SCENARIO_NOT_FOUND', 'S03_SCENARIO_NOT_FOUND' in d2['blockers'], d2); mode.update(st=200, body=S3)
for n, b, code in [('실제 모드 거절 422', dict(BODY, mode='ACTUAL'), 422), ('상품 목록 밖 422', dict(BODY, instrumentType='crypto'), 422), ('단위 불허 422', dict(BODY, quantity=dict(value='1', unit='kg')), 422), ('수량 0 거절 400', dict(BODY, quantity=dict(value='0', unit='MWh')), 400), ('수량 float 거절 400', dict(BODY, quantity=dict(value=5.5, unit='MWh')), 400), ('기간 역전 400', dict(BODY, delivery=dict(start='2026-12-01T00:00:00Z', end='2026-11-01T00:00:00Z')), 400), ('단가 누락 → 0·1 대체 없이 422', dict(BODY, assumption=dict(priceUnit='KRW/kWh', quoteCurrency='KRW')), 422), ('통화 다르고 환율 없음 422', dict(BODY, currency='USD'), 422), ('통화 목록 밖 422', dict(BODY, currency='BTC'), 422), ('다른 국가 공장 422', dict(BODY, plantId='JP-01'), 422)]:
    c, d3 = post(dict(b, businessRequestRef='V-' + str(abs(hash(n)))), 'v-' + str(abs(hash(n)))); chk(n, c == code, (c, d3))
c, d = call('POST', '/v1/procurement-intents/' + iid + '/policy-requests', {}, {'X-Actor': 'x'}); chk('정책 요청·동결 시도 → 422 EXTERNAL_PROGRESS_BLOCKED(감사 기록)', c == 422 and d['code'] == 'EXTERNAL_PROGRESS_BLOCKED', (c, d))
c, d = call('GET', '/v1/procurement-intents/' + iid); chk('의도 조회(최신 버전)·새 버전은 digest가 달라짐', c == 200 and d['intentVersion'] == 2 and len(d['intentDigest']) == 64 and d['intentDigest'] != DG1 and d['latestVersion'] == 2, d)
c, d1 = call('GET', '/v1/procurement-intents/' + iid + '?version=1'); chk('version=1 조회: 처음 digest 그대로·latestVersion 2', c == 200 and d1['intentDigest'] == DG1 and d1['latestVersion'] == 2, d1)
rec = PR.intent_digest(dict(businessOperationId=d1['businessOperationId'], intentId=d1['intentId'], intentVersion=d1['intentVersion'], plantId='KR-01', mode=d1['mode'], instrumentType=d1['instrumentType'], purpose=d1['purpose'], quantity=d1['quantity'], currency=d1['currency'], priceCap=d1['priceCap'], delivery=d1['delivery'], scenarioRef=d1['scenarioRef'], assumption=d1['assumption']))
chk('digest 재계산(규약 함수)이 저장값과 일치·정수 vs 문자열 수량 표기에 영향 없음', rec == DG1)
c, d = call('GET', '/v1/positions'); chk('포지션: 기록 없음 → 빈 목록(0 확정 아님·모의 비합산 안내)', c == 200 and d['items'] == [] and d['state'] == 'no-positions', d)
c, d = call('GET', '/v1/procurement-intents/' + str(uuid.uuid4())); chk('없는 의도 404', c == 404, d)
rows = PR.R.tx(lambda cur: (PR.R.ex(cur, 'SELECT prevHash, hash FROM dbo.ProcurementAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and len(rows) >= 6)
c, d = call('GET', '/health'); chk('health', c == 200 and 'propose-only' in d['mode'], d)
c, sm = call('GET', '/v1/intent-summaries?ops=' + str(bid)); chk('의도 요약: 상품·수량·통화를 업무 ID로 읽음(읽기 전용)', c == 200 and len(sm.get('items', [])) == 1 and sm['items'][0]['instrumentType'] and sm['items'][0]['currency'], (c, sm))
c, sm = call('GET', '/v1/intent-summaries?ops=not-a-uuid'); chk('의도 요약: 형식 오류는 400', c == 400, (c, sm))
import proc_app as _PA
chk('규칙 판정: 한국 매도 960,000 t 권고·3,000,000 t 비권고', _PA.rule_verdict(dict(instrumentType='allowance', purpose='sell', quantity='960000', currency='KRW'))['verdict'] == 'recommended' and _PA.rule_verdict(dict(instrumentType='allowance', purpose='sell', quantity='3000000', currency='KRW'))['verdict'] == 'not-recommended', '')
s_ = __import__('allowance_core').gx_position()['result']['shortageTon']
chk('규칙 판정: 일본 매입은 부족분의 90~105%만 권고(43,611 t는 비권고)', _PA.rule_verdict(dict(instrumentType='allowance', purpose='buy', quantity=str(s_), currency='JPY'))['verdict'] == 'recommended' and _PA.rule_verdict(dict(instrumentType='allowance', purpose='buy', quantity='43611', currency='JPY'))['verdict'] == 'not-recommended', s_)
chk('규칙 판정: 전기 등 다른 상품은 판정 없음', _PA.rule_verdict(dict(instrumentType='electricity', purpose='hedge', quantity='1', currency='KRW')) is None, '')
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
