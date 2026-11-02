import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'planapi'))
import plan_core as P
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
def rej(fn, code):
    try: fn(); return False
    except P.Reject as e: return e.code == code
plan = dict(items=[dict(processId='EAF', goodQty='950', unit='t'), dict(processId='ROLL', goodQty='900', unit='t')])
cons = dict(processes=[dict(processId='EAF', unit='t', yieldRatio='0.95', capacityQty='1100', energyKwhPerInputUnit='400'), dict(processId='ROLL', unit='t', yieldRatio='0.9', capacityQty='1100', energyKwhPerInputUnit='120')])
price = dict(unitPrice='120', currency='KRW', perUnit='kWh'); fx = None
r = P.compute(plan, cons, price, fx, 'KRW')
# EAF: 950/0.95=1000t ×400=400000kWh ; ROLL: 900/0.9=1000t ×120=120000kWh ; 합 520000kWh ×120 = 62,400,000
chk('수식: 투입=정상품/수율, kWh=투입×원단위, 비용=kWh×단가 → 520000kWh·62400000 KRW(Decimal 정확)', r['energy']['value'] == '520000.000' and r['energyCostTotal']['value'] == '62400000.000' and r['feasibility'] is True, (r['energy'], r['energyCostTotal']))
chk('범위: ENERGY_COST_ONLY — 배출·탄소비용·totalCost는 null·NOT_REQUESTED(전체 완료 아님)', r['emissionsEstimate'] is None and r['carbonCost'] is None and r['totalCost'] is None and r['metricStatus']['emissions'] == 'NOT_REQUESTED' and r['publishable'] is False and r['resultKind'] == 'SIMULATED')
chk('민감도 ±10%: 56160000/68640000', [s['energyCostTotal'] for s in r['sensitivity']] == ['56160000.000', '68640000.000'], r['sensitivity'])
chk('결정론: 같은 입력 → 같은 resultHash', P.compute(plan, cons, price, fx, 'KRW')['resultHash'] == r['resultHash'])
c2 = dict(processes=[dict(cons['processes'][0], capacityQty='900'), cons['processes'][1]]); r2 = P.compute(plan, c2, price, fx, 'KRW')
chk('가용능력 초과 → INFEASIBLE 위반 목록(actual 1000/limit 900), 인수 불가', r2['feasibility'] is False and r2['violations'][0] == dict(constraintId='EAF:capacity', actual='1000.000', limit='900.000', unit='t') and r2['eligibility']['procurementHandoff'] is False, r2['violations'])
chk('환율: USD 단가·KRW 보고 → fx 없으면 422(1로 대체 안 함), 있으면 환산', rej(lambda: P.compute(plan, cons, dict(price, currency='USD', unitPrice='0.1'), None, 'KRW'), 'FX_MISSING') and P.compute(plan, cons, dict(price, currency='USD', unitPrice='0.1'), dict(base='USD', quote='KRW', rate='1200'), 'KRW')['energyCostTotal']['value'] == '62400000.000')
chk('환율 방향 불일치 거절(base/quote)', rej(lambda: P.compute(plan, cons, dict(price, currency='USD'), dict(base='KRW', quote='USD', rate='0.0008'), 'KRW'), 'FX_MISSING'))
chk('수율: 0·1 초과 거절', rej(lambda: P.compute(plan, dict(processes=[dict(cons['processes'][0], yieldRatio='0'), cons['processes'][1]]), price, fx, 'KRW'), 'VALIDATION') and rej(lambda: P.compute(plan, dict(processes=[dict(cons['processes'][0], yieldRatio='1.1'), cons['processes'][1]]), price, fx, 'KRW'), 'VALIDATION'))
chk('단위 불일치/제약 누락/가격 분모 단위 오류 거절', rej(lambda: P.compute(dict(items=[dict(processId='EAF', goodQty='950', unit='kg')]), dict(processes=[cons['processes'][0]]), price, fx, 'KRW'), 'UNIT_MISMATCH') and rej(lambda: P.compute(dict(items=[dict(processId='X', goodQty='1', unit='t')]), cons, price, fx, 'KRW'), 'CONSTRAINT_MISSING') and rej(lambda: P.compute(plan, cons, dict(price, perUnit='MWh'), fx, 'KRW'), 'UNIT_MISMATCH'))
chk('float 입력 거절(decimal 문자열만)', rej(lambda: P.compute(dict(items=[dict(processId='EAF', goodQty=950.0, unit='t')]), cons, price, fx, 'KRW'), 'VALIDATION'))
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
