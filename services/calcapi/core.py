"""S02 탄소 산정 핵심(순수 계산·검증, 입출력 없음) — 체크리스트 2-2-1.
설계 근거: design/services/S02 §4(DB02·versionSet·P03 검사), §5.2(runKey), §6.4(상태 어휘), 10 T01·T02·T04.
- 수치는 Decimal 문자열·명시 단위. 기간은 시작 포함·종료 제외. 누락 구간을 0이나 추정값으로 채우지 않는다.
- candidate(후보 생성)와 validator(독립 재계산)는 서로 다른 계산 경로(시간 구간 묶음 합 vs 행 단위 합)다. 같은 입력 snapshot을 쓰므로 입력 자체의 오류는 잡지 못한다(잔여 위험).
- SIMULATED 입력은 certified 발행 대상이 아니다(SECURITY-013).
"""
import hashlib, json
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
getcontext().prec = 40
Q3 = Decimal('0.001')
D = Decimal

def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
def sha(o): return hashlib.sha256(canon(o).encode()).hexdigest()
def q(x): return str(D(x).quantize(Q3, rounding=ROUND_HALF_EVEN))      # roundingVersion ROUND_HALF_EVEN-3

# 버전 고정 참조. 아래 계수는 모의(MOCK)이며 공식 계수·실적·certified가 아니다.
METHODOLOGY = dict(id='AMA-S12-ENERGY-V1', version='1', formula='scope2 = Σ(grid_kW × interval_h) × EF_grid ; scope1 = Σ(gas_Nm3/h × interval_h) × EF_gas ; cost = kWh × tariff', rounding='ROUND_HALF_EVEN-3', sampleIntervalS=5)
FACTORS = {
    'MOCK-EF-GRID-KR': dict(version='1', value='0.4594', unit='kgCO2e/kWh', validFrom='2026-01-01', validTo='2027-01-01', origin='MOCK(공식 계수 아님)'),
    'MOCK-EF-GAS': dict(version='1', value='2.10', unit='kgCO2e/Nm3', validFrom='2026-01-01', validTo='2027-01-01', origin='MOCK(공식 계수 아님)'),
    'MOCK-EF-001': dict(version='1', value='0.5', unit='kgCO2e/kWh', validFrom='2026-01-01', validTo='2027-01-01', origin='정본 fixture'),
    'MOCK-TARIFF-001': dict(version='1', value='100', unit='KRW/kWh', validFrom='2026-01-01', validTo='2027-01-01', origin='정본 fixture'),
}
DQ_POLICY = dict(version='1', min_coverage='0.95')       # 기대 표본 대비 실제 표본 비율. 미달이면 DQ 실패(수치를 내지 않고 보충하지 않는다)

def version_set(snapshot_digest, factor_ids, tariff=None):
    f = {i: dict(version=FACTORS[i]['version'], digest=sha(FACTORS[i])) for i in sorted(factor_ids)}
    vs = dict(inputSnapshotDigest=snapshot_digest, methodology=dict(id=METHODOLOGY['id'], version=METHODOLOGY['version'], digest=sha(METHODOLOGY)), factors=f, unitConversion='v1:kW*s/3600', rounding=METHODOLOGY['rounding'], dqPolicy=DQ_POLICY['version'])
    if tariff: vs['tariff'] = dict(id=tariff, version=FACTORS[tariff]['version'], currency='KRW')
    return vs

def run_key(scope, kind, vs, scenario=None):
    """같은 범위·종류·입력·모든 버전(·시나리오)이면 같은 키. 계수 버전 하나만 달라도 다른 키(T02)."""
    return sha(dict(scope=scope, kind=kind, versionSet=vs, scenario=scenario))

def check_factor_period(fid, start_iso):
    f = FACTORS[fid]
    if not (f['validFrom'] <= start_iso[:10] < f['validTo']): raise ValueError('FACTOR_PERIOD_GAP:%s' % fid)

def mode_of(rows_mode):
    """ACTUAL/SIMULATED 혼합 snapshot은 거절(SECURITY-013)."""
    ms = set(rows_mode)
    if len(ms) != 1: raise ValueError('MODE_MIXED_OR_EMPTY:%s' % sorted(ms))
    return ms.pop()

def candidate(samples, period, ef_grid='MOCK-EF-GRID-KR', ef_gas='MOCK-EF-GAS', dt_s=5):
    """후보 생성 경로: 시(hour) 단위로 묶어 kWh/Nm3를 합산한 뒤 계수를 곱한다. samples=[{ts_ms, grid_kw, gas_nm3h}]"""
    start_ms, end_ms = period['startMs'], period['endMs']
    inside = [s for s in samples if start_ms <= s['ts_ms'] < end_ms]
    hours = {}
    for s in inside: hours.setdefault(s['ts_ms'] // 3600000, []).append(s)
    kwh = sum((sum((D(str(x['grid_kw'])) for x in v), D(0)) * D(dt_s) / D(3600) for v in hours.values()), D(0))
    nm3 = sum((sum((D(str(x['gas_nm3h'])) for x in v), D(0)) * D(dt_s) / D(3600) for v in hours.values()), D(0))
    expected = (end_ms - start_ms) // (dt_s * 1000)
    cov = D(len(inside)) / D(expected) if expected else D(0)
    return dict(values=[dict(metric='scope2_location_based', value=q(kwh * D(FACTORS[ef_grid]['value'])), unit='kgCO2e', boundaryRef='SITE'),
                        dict(metric='scope1_stationary_fuel', value=q(nm3 * D(FACTORS[ef_gas]['value'])), unit='kgCO2e', boundaryRef='SITE'),
                        dict(metric='grid_energy', value=q(kwh), unit='kWh', boundaryRef='SITE')],
                samples=len(inside), expectedSamples=expected, coverage=q(cov))

def validate(cand, samples, period, ef_grid='MOCK-EF-GRID-KR', ef_gas='MOCK-EF-GAS', dt_s=5):
    """독립 재계산(P03): 행 단위 합으로 다시 계산해 후보 수치·표본 수와 대조하고 DQ 정책을 적용한다. 일부 통과를 전체 통과로 보고하지 않는다."""
    s_ms, e_ms = period['startMs'], period['endMs']; kwh = D(0); nm3 = D(0); n = 0
    for s in samples:
        if s_ms <= s['ts_ms'] < e_ms: kwh += D(str(s['grid_kw'])) * D(dt_s) / D(3600); nm3 += D(str(s['gas_nm3h'])) * D(dt_s) / D(3600); n += 1
    exp = {'scope2_location_based': q(kwh * D(FACTORS[ef_grid]['value'])), 'scope1_stationary_fuel': q(nm3 * D(FACTORS[ef_gas]['value'])), 'grid_energy': q(kwh)}
    checks = []
    for v in cand['values']: checks.append(dict(checkId='RECALC:' + v['metric'], status='PASS' if v['value'] == exp.get(v['metric']) else 'FAIL', observed=v['value'], expected=exp.get(v['metric']), unit=v['unit']))
    checks.append(dict(checkId='ROWCOUNT', status='PASS' if cand['samples'] == n else 'FAIL', observed=cand['samples'], expected=n, unit='rows'))
    expected = (e_ms - s_ms) // (dt_s * 1000); cov = D(n) / D(expected) if expected else D(0)
    checks.append(dict(checkId='DQ:coverage', status='PASS' if cov >= D(DQ_POLICY['min_coverage']) else 'FAIL', observed=q(cov), expected='>=' + DQ_POLICY['min_coverage'], unit='ratio'))
    bad = [c for c in checks if c['status'] != 'PASS']
    # 후보 수치가 맞아도 DQ가 미달이면 dq_failed, 수치 불일치면 recalc_mismatch로 구분한다
    verdict = 'PASS' if not bad else ('DQ_FAILED' if all(c['checkId'].startswith('DQ:') for c in bad) else 'RECALC_MISMATCH')
    return dict(verdict=verdict, checks=checks, dqPolicyVersion=DQ_POLICY['version'])

def business_state(verdict): return {'PASS': 'ready', 'DQ_FAILED': 'dq_failed', 'RECALC_MISMATCH': 'dq_failed'}[verdict]

def screen_label(mode, release_status=None, restricted=False, kind='INVENTORY'):
    """§6.4 상태 어휘. 후보·202·job 성공은 확정이 아니며 SIMULATED는 모의 표시다."""
    if kind == 'WHAT_IF': return '추정/시뮬레이션(비발행)'
    if release_status in ('revoked', 'superseded'): return '철회됨' if release_status == 'revoked' else '대체됨'
    if restricted or release_status == 'correction_pending': return '사용 차단/정정 중'
    if release_status == 'issued' and mode == 'ACTUAL': return '확정(내부 산정 확정)'
    return '잠정(모의)' if mode == 'SIMULATED' else '잠정(후보)'

def can_certify(mode, approvals_ok, grant_authority_resolved):
    """certified는 ACTUAL + 분리된 사람 승인(S07) + 권한 출처 확정이 모두 있을 때만. 하나라도 없으면 차단."""
    return mode == 'ACTUAL' and bool(approvals_ok) and bool(grant_authority_resolved)

def fixture_oracle():
    """정본 fixture(KR01-MOCK-E0001/E0002, 10/20 kWh, EF 0.5, 요율 100) → 5.0/10.0 kgCO2e, 1000/2000 KRW."""
    out = []
    for kwh in ('10', '20'): out.append(dict(kgco2e=q(D(kwh) * D(FACTORS['MOCK-EF-001']['value'])), krw=q(D(kwh) * D(FACTORS['MOCK-TARIFF-001']['value']))))
    return out
