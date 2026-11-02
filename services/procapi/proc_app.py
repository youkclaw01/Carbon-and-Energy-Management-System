#!/usr/bin/env python3
"""proc-api — S04 조달 의도 초안(API04의 S04 부분)·포지션 조회 (체크리스트 2-10-1~2-10-3). 설계: design/services/S04 §2~4.
propose-only: 의도는 DRAFT(모의)로만 만든다. intentDigest·정규화 규약은 합의 전이라 NULL·bindingState=UNRESOLVED, 정책(API07)·승인(API08)·예약·permit·S08 실행으로 가는 경로는 열지 않는다. mode는 SIMULATED 고정(모의 포지션을 실제 보유와 합치지 않음).
S03 시나리오는 소유 API로 재조회해 scenarioRef(resultHash 일치)·SUCCEEDED·feasibility=true·에너지 비용 COMPLETE를 확인한다. 통과해도 S03→S04 인수 계약 미합의라 externalReady=false이다.
원업무 식별: businessOperationId는 S04가 발급하고 같은 businessRequestRef는 하나로 묶는다(클라이언트 재발급 불가, 중복 등록은 기존 원업무에 새 intent 버전). 사용자 인가는 S07 이후(X-Actor 미검증 라벨)."""
import os, sys, json, uuid, datetime as dt
from decimal import Decimal, InvalidOperation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import allowance_core as AL
VERSION = 'proc-api/0.2'; COUNTRY, ORG = 'KR', 'AMA-KR'; STATS = {}; R = None; FETCH = http_get
INSTR = {'electricity', 'rec', 'eac', 'allowance'}; UNITS = {'electricity': {'kWh', 'MWh'}, 'rec': {'MWh'}, 'eac': {'MWh'}, 'allowance': {'t'}}; CCY = {'KRW', 'USD', 'JPY', 'SGD'}
def A(cur, actor, action, target, reason='', cid=None, before=None, after=None):
    R.chain(cur, 'ProcurementAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def pos(v, name, allow_zero=False):
    if not isinstance(v, str): raise ApiError(400, 'VALIDATION', name + '는 decimal 문자열이어야 합니다.')
    try: d = Decimal(v)
    except InvalidOperation: raise ApiError(400, 'VALIDATION', name + ' 형식 오류')
    if d < 0 or (d == 0 and not allow_zero): raise ApiError(400, 'VALIDATION', name + '는 ' + ('0 이상' if allow_zero else '양수') + '여야 합니다.')
    return d
def pdt(s, name):
    try: return dt.datetime.strptime(s.replace('Z', '').split('.')[0], '%Y-%m-%dT%H:%M:%S')
    except Exception: raise ApiError(400, 'VALIDATION', name + '은 UTC ISO여야 합니다.')
def check_scenario(ref):
    """S03 소유 API 재조회. 반환 blockers(목록). 이벤트·과거 응답으로 대신하지 않는다."""
    url = os.environ.get('PLAN_API_URL', '').rstrip('/') + '/v1/scenarios/%s?scenarioVersion=%s' % (ref['scenarioId'], ref['scenarioVersion'])
    st, body = FETCH(url)
    if st == 404: return ['S03_SCENARIO_NOT_FOUND']
    if st != 200: return ['S03_STATE_UNKNOWN']
    d = json.loads(body); b = []
    if d['scenarioRef']['resultHash'] != ref.get('resultHash'): b.append('S03_RESULT_HASH_MISMATCH')
    if d['status'] != 'SUCCEEDED' or d.get('feasibility') is not True: b.append('S03_NOT_FEASIBLE_OR_INCOMPLETE')
    if (d.get('metricStatus') or {}).get('energyCost') != 'COMPLETE': b.append('S03_ENERGY_COST_INCOMPLETE')
    return b
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    for k in ('businessRequestRef', 'instrumentType', 'purpose', 'quantity', 'currency', 'delivery', 'scenarioRef', 'assumption'):
        if not body.get(k): raise ApiError(400, 'VALIDATION', k + ' 필요')
    if body.get('mode', 'SIMULATED') != 'SIMULATED': raise ApiError(422, 'MODE_NOT_ALLOWED', '모의(SIMULATED) 의도만 만들 수 있습니다. 실제 조달 모드는 닫혀 있습니다.')
    if body.get('plantId', 'KR-01') != 'KR-01': raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역 DB04는 KR-01만 다룹니다.')
    it = body['instrumentType']
    if it not in INSTR: raise ApiError(422, 'INSTRUMENT_UNSUPPORTED', '허용 상품 목록 밖입니다(임의 기본값 없음).')
    q = body['quantity']; pos(q.get('value'), 'quantity.value')
    if q.get('unit') not in UNITS[it]: raise ApiError(422, 'UNIT_UNSUPPORTED', '상품에 허용된 단위가 아닙니다: ' + ', '.join(sorted(UNITS[it])))
    if body['currency'] not in CCY: raise ApiError(422, 'CURRENCY_UNSUPPORTED', '허용 통화 목록 밖입니다.')
    if body.get('priceCap') is not None: pos(body['priceCap'], 'priceCap', True)
    ds, de = pdt(str(body['delivery'].get('start', '')), 'delivery.start'), pdt(str(body['delivery'].get('end', '')), 'delivery.end')
    if not ds < de: raise ApiError(400, 'VALIDATION', 'delivery.start < delivery.end여야 합니다.')
    sref = body['scenarioRef']
    if not all(sref.get(k) for k in ('scenarioId', 'scenarioVersion', 'resultHash')): raise ApiError(400, 'VALIDATION', 'scenarioRef{scenarioId, scenarioVersion, resultHash} 필요')
    a = body['assumption']
    for k in ('unitPrice', 'priceUnit', 'quoteCurrency'): 
        if a.get(k) is None: raise ApiError(422, 'ASSUMPTION_MISSING', 'assumption.%s 누락(0·1로 대체하지 않습니다).' % k)
    pos(a['unitPrice'], 'assumption.unitPrice', True)
    if a['quoteCurrency'] != body['currency'] and not a.get('fxRate'): raise ApiError(422, 'ASSUMPTION_MISSING', '통화가 다르면 assumption.fxRate가 필요합니다(1로 대체하지 않음).')
    blockers = check_scenario(sref) + ['S03_HANDOFF_CONTRACT_UNAGREED']
    rd = sha(canon(body)); iid, bid = str(uuid.uuid4()), str(uuid.uuid4()); t = ts()
    def f(cur):
        R.ex(cur, 'SELECT intentId, intentVersion, requestDigest, businessOperationId, state, blockers FROM dbo.ProcurementIntent WHERE country=%s AND orgId=%s AND principalRef=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem[:100])); x = cur.fetchall()
        if x:
            if x[0][2] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, x[0][0], x[0][1], x[0][3], json.loads(x[0][5]), x[0][4]
        R.ex(cur, 'SELECT businessOperationId, rootIntentId, activeIntentVersion, holdState FROM dbo.BusinessOperation WHERE country=%s AND orgId=%s AND businessRequestRef=%s', (COUNTRY, ORG, body['businessRequestRef'][:100])); bo = cur.fetchall(); ver = 1
        if bo:
            if bo[0][3] != 'none': raise ApiError(409, 'BUSINESS_HOLD', '원업무가 hold 상태라 새 intent를 만들 수 없습니다(새 ID 우회 금지).')
            bid2, rid2, ver = bo[0][0], bo[0][1], bo[0][2] + 1; iid2 = rid2
            R.ex(cur, 'UPDATE dbo.BusinessOperation SET activeIntentVersion=%s, rowVersion=rowVersion+1 WHERE country=%s AND sourceService=%s AND businessOperationId=%s', (ver, COUNTRY, 'S04', bid2))
        else:
            bid2, iid2 = bid, iid; R.ex(cur, 'INSERT INTO dbo.BusinessOperation(country, sourceService, businessOperationId, orgId, businessRequestRef, rootIntentId, activeIntentVersion, holdState, rowVersion) VALUES (%s,%s,%s,%s,%s,%s,1,%s,1)', (COUNTRY, 'S04', bid2, ORG, body['businessRequestRef'][:100], iid2, 'none'))
        dg = intent_digest(dict(businessOperationId=bid2, intentId=iid2, intentVersion=ver, plantId='KR-01', mode='SIMULATED', instrumentType=it, purpose=body['purpose'][:40], quantity=q, currency=body['currency'], priceCap=body.get('priceCap'), delivery=dict(start=iso(ds), end=iso(de)), scenarioRef=sref, assumption=a))
        R.ex(cur, 'INSERT INTO dbo.ProcurementIntent(intentId, intentVersion, country, orgId, businessOperationId, plantId, mode, principalRef, idemKey, requestDigest, instrumentType, purpose, quantityValue, quantityUnit, currency, priceCapMinorText, deliveryStart, deliveryEnd, scenarioRef, assumption, intentDigest, canonicalizationVersion, digestAlgorithm, bindingState, state, blockers, rowVersion, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)',
            (iid2, ver, COUNTRY, ORG, bid2, 'KR-01', 'SIMULATED', actor, idem[:100], rd, it, body['purpose'][:40], q['value'], q['unit'], body['currency'], body.get('priceCap'), ts(ds), ts(de), json.dumps(sref), json.dumps(a), dg, CANON_V, ALG_ID, 'BOUND', 'DRAFT', json.dumps(blockers), t))
        A(cur, actor, 'INTENT_DRAFT', iid2, ','.join(blockers)[:280], cid, after=str(ver)); return 202, iid2, ver, bid2, blockers, 'DRAFT'
    c, iid3, ver3, bid3, bl, state = R.tx(f)
    dgx = R.tx(lambda cur: (R.ex(cur, 'SELECT intentDigest FROM dbo.ProcurementIntent WHERE intentId=%s AND intentVersion=%s', (iid3, ver3)), cur.fetchall()[0][0])[1])
    return c, dict(intentId=iid3, intentVersion=ver3, businessOperationId=bid3, mode='SIMULATED', state=state, bindingState='BOUND', intentDigest=dgx, canonicalizationVersion=CANON_V, digestAlgorithmId=ALG_ID, externalReady=False, blockers=bl, statusUrl='/v1/procurement-intents/' + iid3, note='초안(모의)입니다. 정책·승인·예약·실행 경로는 열려 있지 않고 접수는 체결·계약이 아닙니다.')
CANON_V, ALG_ID = 'ama.intent.v1/jcs-1', 'sha256'
def intent_digest(f):
    """공통 intentDigest 규약 ama.intent.v1/jcs-1(총괄 결정): 아래 의미 필드만 키 정렬·공백 없는 UTF-8 JSON(JCS 호환 부분집합)으로 직렬화해 SHA-256. 수량·금액·가격은 모두 문자열로 고정해 부동소수를 쓰지 않는다.
    필드: schema, businessOperationId, intentId, intentVersion, plantId, mode, instrumentType, purpose, quantity{value,unit}, currency, priceCap, delivery{start,end}, scenarioRef{scenarioId,scenarioVersion,resultHash}, assumption."""
    def s(v): return None if v is None else str(v)
    q, d, sr, asm = f['quantity'], f['delivery'], f['scenarioRef'], f['assumption']
    doc = dict(schema='ama.intent.v1', businessOperationId=f['businessOperationId'], intentId=f['intentId'], intentVersion=int(f['intentVersion']), plantId=f['plantId'], mode=f['mode'], instrumentType=f['instrumentType'], purpose=f['purpose'],
               quantity=dict(value=s(q['value']), unit=q['unit']), currency=f['currency'], priceCap=s(f.get('priceCap')), delivery=dict(start=f['delivery']['start'], end=f['delivery']['end']),
               scenarioRef=dict(scenarioId=s(sr['scenarioId']), scenarioVersion=s(sr['scenarioVersion']), resultHash=s(sr['resultHash'])), assumption={k: (s(v) if not isinstance(v, (dict, list)) else v) for k, v in asm.items()})
    return sha(canon(doc))
def rule_verdict(i):
    """배출권 의도의 규칙 판정(읽기 전용): 한국 매도는 허용 구간(이월 한도 기준), 일본 매입은 예상 부족 수량 기준. 계산은 allowance_core의 결정론이다."""
    try:
        if i['instrumentType'] != 'allowance': return None
        q = float(i['quantity'])
        if i['purpose'] == 'sell' and i['currency'] == 'KRW':
            r = AL.position()['result']; ok = r['minSellTon'] <= q <= r['maxSellTon']
            return dict(verdict='recommended' if ok else 'not-recommended', reason='허용 구간 %s~%st %s' % (format(int(r['minSellTon']), ','), format(int(r['maxSellTon']), ','), '안' if ok else '밖'))
        if i['purpose'] == 'buy' and i['currency'] == 'JPY':
            s = AL.gx_position()['result']['shortageTon']; ok = s * 0.9 <= q <= s * 1.05
            return dict(verdict='recommended' if ok else 'not-recommended', reason='예상 부족 %st의 90~105%% %s' % (format(int(s), ','), '안' if ok else '밖'))
    except Exception: return None
    return None
def intent_summaries(ops):
    """businessOperationId 목록(최대 50)의 요약(읽기 전용, 열거 불가): 거래 진행 화면이 건의 상품·방향·수량을 사람이 읽는 문장으로 보여 주기 위함."""
    ids = [o for o in str(ops or '').split(',') if o][:50]
    for o in ids:
        try: uuid.UUID(o)
        except Exception: raise ApiError(400, 'BAD_REQUEST', 'ops는 businessOperationId(UUID) 목록입니다.')
    if not ids: return dict(items=[])
    ph = ','.join(['%s'] * len(ids))
    rows = R.tx(lambda cur: (R.ex(cur, 'SELECT p.businessOperationId, p.instrumentType, p.purpose, p.quantityValue, p.quantityUnit, p.currency, p.priceCapMinorText FROM dbo.ProcurementIntent p JOIN (SELECT businessOperationId AS b, MAX(intentVersion) AS v FROM dbo.ProcurementIntent WHERE businessOperationId IN (' + ph + ') GROUP BY businessOperationId) m ON p.businessOperationId = m.b AND p.intentVersion = m.v', tuple(ids)), cur.fetchall())[1])
    items = [dict(businessOperationId=r[0], instrumentType=r[1], purpose=r[2], quantity=str(r[3]), unit=r[4], currency=r[5], priceCap=r[6]) for r in rows]
    for it in items: it['rule'] = rule_verdict(it)
    return dict(items=items)
def get_intent(iid, version=None):
    try: uuid.UUID(iid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'intentId 형식이 올바르지 않습니다.')
    if version is not None and not str(version).isdigit(): raise ApiError(400, 'BAD_REQUEST', 'version은 양의 정수입니다.')
    sql = 'SELECT intentId, intentVersion, businessOperationId, mode, state, bindingState, instrumentType, quantityValue, quantityUnit, currency, deliveryStart, deliveryEnd, blockers, scenarioRef, createdAt, intentDigest, canonicalizationVersion, digestAlgorithm, purpose, priceCapMinorText, assumption FROM dbo.ProcurementIntent WHERE intentId=%s' + (' AND intentVersion=%s' if version is not None else '') + ' ORDER BY intentVersion DESC'
    x = R.tx(lambda cur: (R.ex(cur, sql, (iid, int(version)) if version is not None else (iid,)), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 의도가 없습니다.')
    latest = R.tx(lambda cur: (R.ex(cur, 'SELECT MAX(intentVersion) FROM dbo.ProcurementIntent WHERE intentId=%s', (iid,)), cur.fetchall()[0][0])[1])
    x = x[0]; return dict(intentId=x[0], intentVersion=x[1], latestVersion=latest, businessOperationId=x[2], mode=x[3], state=x[4], bindingState=x[5], intentDigest=x[15], canonicalizationVersion=x[16], digestAlgorithmId=x[17], instrumentType=x[6], purpose=x[18], quantity=dict(value=x[7], unit=x[8]), currency=x[9], priceCap=x[19], delivery=dict(start=iso(x[10]), end=iso(x[11])), blockers=json.loads(x[12]), scenarioRef=json.loads(x[13]), assumption=json.loads(x[20]), createdAt=iso(x[14]), externalReady=False)
def positions():
    rows = R.tx(lambda cur: (R.ex(cur, 'SELECT positionKey, version, mode, contractedQty, deliveredQty, retiredQty, pendingQty, unknownExposure, asOf, quality FROM dbo.PositionSnapshot ORDER BY asOf DESC'), cur.fetchall())[1])
    return dict(items=[dict(positionKey=r[0], version=r[1], mode=r[2], contractedQty=r[3], deliveredQty=r[4], retiredQty=r[5], pendingQty=r[6], unknownExposure=r[7], asOf=iso(r[8]), quality=r[9]) for r in rows], state='no-positions' if not rows else 'ok', note='체결·인도·말소 기록이 없어 포지션은 비어 있습니다. 의도·승인·예약은 약정량을 늘리지 않으며 모의 값을 실제 보유와 합치지 않습니다.' if not rows else None)
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/procurement-intents': return create(body, h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'procurement-intents': return 200, get_intent(P[3], (qs.get('version') or [None])[0])
    if m == 'GET' and p == '/v1/positions': return 200, positions()
    if m == 'GET' and p == '/v1/intent-summaries': return 200, intent_summaries((qs.get('ops') or [''])[0])
    if m == 'GET' and len(P) == 4 and P[2] == 'allowance-positions':
        kinds = {AL.DEMO_ID: AL.position, AL.DEMO_ID_JP: AL.gx_position, AL.DEMO_ID_SG: AL.sg_position}
        if P[3] not in kinds: raise ApiError(404, 'NOT_FOUND', '해당 배출권 포지션이 없습니다(데모 포지션만 제공).')
        return 200, kinds[P[3]]()
    if m == 'POST' and len(P) == 5 and P[2] == 'procurement-intents' and P[4] in ('policy-requests', 'freeze'):
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'INTENT_ADVANCE_ATTEMPT', P[3], 'BLOCKED:' + P[4], cid)); raise ApiError(422, 'EXTERNAL_PROGRESS_BLOCKED', '이 의도는 초안에서 더 진행할 수 없습니다: 정규화·digest 규약 미합의, 정책(D12) 미결, S03 인수 계약 미합의. 정책 요청·동결을 만들지 않았습니다.')
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.ProcurementIntent), (SELECT COUNT(*) FROM dbo.PositionSnapshot), (SELECT COUNT(*) FROM dbo.ProcurementAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, intents=s[0], positions=s[1], audits=s[2], errors=R.err, last_err=R.last_err), mode='propose-only(초안·모의)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
