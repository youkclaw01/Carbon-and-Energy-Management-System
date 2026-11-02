import sys, os, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'calc'))
import core as c
ok = bad = 0
def chk(n, cond, info=''):
    global ok, bad
    if cond: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, info)
T0 = 1793318400000      # 고정 시각(시계 비의존)
def mk(n, grid=1000.0, gas=100.0, start=T0): return [dict(ts_ms=start + i * 5000, grid_kw=grid, gas_nm3h=gas) for i in range(n)]
P = dict(startMs=T0, endMs=T0 + 3600000)
# T01 정본 fixture oracle
o = c.fixture_oracle(); chk('T01 fixture oracle 5.0/10.0 kgCO2e·1000/2000 KRW', [(x['kgco2e'], x['krw']) for x in o] == [('5.000', '1000.000'), ('10.000', '2000.000')], o)
# 산식: 720표본×1000kW×5s=1000kWh, ×0.4594=459.4 ; gas 100Nm3/h→100Nm3, ×2.10=210
s = mk(720); cd = c.candidate(s, P); v = {x['metric']: x['value'] for x in cd['values']}
chk('산식: 1000kWh→scope2 459.400, scope1 210.000, 커버리지 1.000', v == {'scope2_location_based': '459.400', 'scope1_stationary_fuel': '210.000', 'grid_energy': '1000.000'} and cd['coverage'] == '1.000', (v, cd['coverage']))
r = c.validate(cd, s, P); chk('독립 재계산 PASS', r['verdict'] == 'PASS', r)
# T04 올바른 형식이지만 틀린 수치 → 차단, 값 일치해도 DQ 미달이면 dq_failed
bad_c = copy.deepcopy(cd); bad_c['values'][0]['value'] = '460.000'; r2 = c.validate(bad_c, s, P); chk('T04 틀린 수치(hash/형식 정상) → RECALC_MISMATCH', r2['verdict'] == 'RECALC_MISMATCH' and c.business_state(r2['verdict']) == 'dq_failed', r2['verdict'])
s2 = mk(600); cd2 = c.candidate(s2, P); r3 = c.validate(cd2, s2, P); chk('DQ: 표본 600/720(0.833) → DQ_FAILED, 누락 구간 0·추정 보충 없음', r3['verdict'] == 'DQ_FAILED' and cd2['coverage'] == '0.833' and cd2['values'][2]['value'] == '833.333', (r3['verdict'], cd2['coverage'], cd2['values'][2]))
# 기간 경계: 시작 포함·종료 제외
sb = mk(1, start=P['endMs']) + mk(1, start=P['startMs'] - 5000) + mk(720); cb = c.candidate(sb, P); chk('기간 [시작,종료): 경계 밖 표본 제외', cb['samples'] == 720, cb['samples'])
# 단위: 시간 경계를 넘는 묶음 합과 행 단위 합이 같은 결과(Decimal, 부동소수 오차 없음)
sh = mk(1440, grid=333.33, gas=77.7); Ph = dict(startMs=T0, endMs=T0 + 7200000); ch = c.candidate(sh, Ph); rh = c.validate(ch, sh, Ph); chk('2시간(시 경계 포함) 두 경로 일치', rh['verdict'] == 'PASS', rh)
# T02 runKey 결정론·민감도
vs1 = c.version_set('d1', ['MOCK-EF-GRID-KR', 'MOCK-EF-GAS']); k1 = c.run_key('KR-01|2026-10-31', 'INVENTORY', vs1); k1b = c.run_key('KR-01|2026-10-31', 'INVENTORY', c.version_set('d1', ['MOCK-EF-GAS', 'MOCK-EF-GRID-KR']))
chk('T02 같은 입력·순서 무관 → 같은 runKey', k1 == k1b)
c.FACTORS['MOCK-EF-GRID-KR']['version'] = '2'; k2 = c.run_key('KR-01|2026-10-31', 'INVENTORY', c.version_set('d1', ['MOCK-EF-GRID-KR', 'MOCK-EF-GAS'])); c.FACTORS['MOCK-EF-GRID-KR']['version'] = '1'
chk('T02 계수 버전만 달라도 새 runKey', k1 != k2); chk('T02 입력 snapshot 다르면 새 runKey', k1 != c.run_key('KR-01|2026-10-31', 'INVENTORY', c.version_set('d2', ['MOCK-EF-GRID-KR', 'MOCK-EF-GAS'])))
chk('WHAT_IF는 같은 입력도 다른 runKey', c.run_key('KR-01|x', 'WHAT_IF', vs1, scenario={'id': 's1'}) != c.run_key('KR-01|x', 'INVENTORY', vs1))
# 계수 적용기간 공백, 모드 혼합
try: c.check_factor_period('MOCK-EF-GRID-KR', '2028-01-01'); chk('계수 적용기간 밖 → 차단', False)
except ValueError as e: chk('계수 적용기간 밖 → 차단', 'FACTOR_PERIOD_GAP' in str(e))
try: c.mode_of(['SIMULATED', 'ACTUAL']); chk('모드 혼합 거절', False)
except ValueError as e: chk('ACTUAL/SIMULATED 혼합 snapshot 거절', 'MODE_MIXED' in str(e))
# 상태 어휘·certified 조건(T03/T09)
chk('SIMULATED는 certified 불가(승인·권한 출처가 있어도)', not c.can_certify('SIMULATED', True, True)); chk('ACTUAL이어도 권한 출처 미결이면 certified 차단', not c.can_certify('ACTUAL', True, False)); chk('ACTUAL+승인+권한 출처 확정 → 가능(조건 충족시에만)', c.can_certify('ACTUAL', True, True))
chk('화면 어휘: 후보=잠정(모의), WHAT_IF=추정, 철회/대체/정정 구분', [c.screen_label('SIMULATED'), c.screen_label('SIMULATED', kind='WHAT_IF'), c.screen_label('ACTUAL', 'issued'), c.screen_label('ACTUAL', 'revoked'), c.screen_label('ACTUAL', 'correction_pending')] == ['잠정(모의)', '추정/시뮬레이션(비발행)', '확정(내부 산정 확정)', '철회됨', '사용 차단/정정 중'])
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
