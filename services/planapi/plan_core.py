"""S03 비용 계획 핵심(순수) — 체크리스트 2-9-1. 설계: design/services/S03 §4·4.1.
ENERGY_COST_ONLY만 계산한다(에너지 사용량×단가×환산율). 배출·탄소비용·전체 totalCost는 계산하지 않고 null(S02 what-if 계약 미합의 → ENERGY_CARBON은 BLOCKED_DEPENDENCY).
수율 0<y≤1, 환율 양수·방향 명시, 투입량=정상품/수율, 투입량≤가용능력(같은 단위). 누락 가격·환율을 0·1로 대체하지 않는다. 십진 정확 연산, 반올림 ROUND_HALF_EVEN-3 버전 고정. 결정론적(같은 입력→같은 결과·hash)."""
import hashlib, json
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, getcontext
getcontext().prec = 40
Q = Decimal('0.001'); SOLVER = 'det-energy-cost-1'; ROUND = 'ROUND_HALF_EVEN-3'
class Reject(Exception):
    def __init__(self, status, code, msg='', fields=None): self.status, self.code, self.msg, self.fields = status, code, msg, fields or []
def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def sha(o): return hashlib.sha256(canon(o)).hexdigest()
def D(v, name, positive=True):
    if not isinstance(v, str): raise Reject(400, 'VALIDATION', name + '는 decimal 문자열이어야 합니다.', [name])
    try: d = Decimal(v)
    except InvalidOperation: raise Reject(400, 'VALIDATION', name + ' 형식 오류', [name])
    if positive and d <= 0: raise Reject(400, 'VALIDATION', name + '는 0보다 커야 합니다.', [name])
    if not positive and d < 0: raise Reject(400, 'VALIDATION', name + '는 0 이상이어야 합니다.', [name])
    return d
def q3(d): return str(d.quantize(Q, rounding=ROUND_HALF_EVEN))
def validate_inputs(plan, cons, price, fx, report_ccy):
    if not plan.get('items'): raise Reject(400, 'VALIDATION', 'plan.items 필요', ['plan.items'])
    cmap = {c.get('processId'): c for c in cons.get('processes', [])}
    for it in plan['items']:
        if it.get('processId') not in cmap: raise Reject(422, 'CONSTRAINT_MISSING', '공정 %s의 제약(능력·수율·원단위)이 없습니다.' % it.get('processId'), ['constraints'])
        D(it.get('goodQty'), 'plan.goodQty')
    for c in cons['processes']:
        y = D(c.get('yieldRatio'), 'constraints.yield')
        if y > 1: raise Reject(400, 'VALIDATION', '수율은 1 이하여야 합니다.', ['constraints.yield'])
        D(c.get('capacityQty'), 'constraints.capacityQty'); D(c.get('energyKwhPerInputUnit'), 'constraints.energyKwhPerInputUnit', positive=False)
    D(price.get('unitPrice'), 'price.unitPrice', positive=False)
    if not price.get('currency') or price.get('perUnit') != 'kWh': raise Reject(422, 'UNIT_MISMATCH', '가격은 currency와 분모 단위 kWh가 필요합니다(묵시 환산 없음).', ['price.perUnit'])
    if price['currency'] != report_ccy:
        if not fx or fx.get('base') != price['currency'] or fx.get('quote') != report_ccy: raise Reject(422, 'FX_MISSING', '환율(base=%s, quote=%s)이 없어 환산할 수 없습니다. 1로 대체하지 않습니다.' % (price['currency'], report_ccy), ['fx'])
        D(fx.get('rate'), 'fx.rate')
def compute(plan, cons, price, fx, report_ccy):
    """반환 result dict(결정론). 가용능력 초과는 INFEASIBLE(위반 목록)이며 비용은 참고로 계산하되 인수 불가."""
    validate_inputs(plan, cons, price, fx, report_ccy); cmap = {c['processId']: c for c in cons['processes']}
    rate = Decimal(1) if price['currency'] == report_ccy else Decimal(fx['rate']); up = Decimal(price['unitPrice'])
    rows = []; viol = []; kwh_total = Decimal(0); cost_total = Decimal(0)
    for it in sorted(plan['items'], key=lambda x: x['processId']):
        c = cmap[it['processId']]; good = Decimal(it['goodQty']); y = Decimal(c['yieldRatio']); inp = good / y; cap = Decimal(c['capacityQty'])
        if it.get('unit') != c.get('unit'): raise Reject(422, 'UNIT_MISMATCH', '공정 %s의 계획 단위와 제약 단위가 다릅니다.' % it['processId'], ['unit'])
        if inp > cap: viol.append(dict(constraintId=it['processId'] + ':capacity', actual=q3(inp), limit=q3(cap), unit=c['unit']))
        kwh = inp * Decimal(c['energyKwhPerInputUnit']); cost = kwh * up * rate; kwh_total += kwh; cost_total += cost
        rows.append(dict(processId=it['processId'], inputQty=q3(inp), unit=c['unit'], energyKwh=q3(kwh), energyCost=q3(cost), currency=report_ccy))
    def tot(f): return q3(sum((Decimal(r['energyKwh']) * up * f * rate for r in rows), Decimal(0)))
    sens = [dict(parameter='price', change='-10%', energyCostTotal=tot(Decimal('0.9'))), dict(parameter='price', change='+10%', energyCostTotal=tot(Decimal('1.1')))]
    feasible = not viol
    res = dict(resultKind='SIMULATED', publishable=False, calculationScope='ENERGY_COST_ONLY', metricStatus=dict(energyCost='COMPLETE', emissions='NOT_REQUESTED', carbonCost='NOT_REQUESTED'), feasibility=feasible, violations=viol, costBreakdown=rows, energy=dict(value=q3(kwh_total), unit='kWh'),
               energyCostTotal=dict(value=q3(cost_total), currency=report_ccy), emissionsEstimate=None, carbonCost=None, totalCost=None, baselineDelta=None, baselineDeltaReason='baselineRef 미제공(S02 기준선 비교 없음)', sensitivity=sens, eligibility=dict(procurementHandoff=False, reason='S04 인수 계약 미합의'), roundingRuleVersion=ROUND, solverVersion=SOLVER)
    res['resultHash'] = sha({k: v for k, v in res.items()}); return res
