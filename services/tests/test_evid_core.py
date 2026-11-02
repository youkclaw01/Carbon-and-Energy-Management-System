import sys, os, json, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'evidapi'))
import evid_core as c
ok = bad = 0
def chk(n, cond, info=''):
    global ok, bad
    if cond: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, info)
CTX = dict(country='KR', orgId='AMA-KR', plantId='KR-01', manifestId='m-1', manifestVersion=1, sourceBinding=dict(kind='run', runId='r-1'), snapshotId='snap-1', periodStart='2026-10-25T00:00:00+09:00', periodEnd='2026-10-25T00:15:00+09:00', timeZone='Asia/Seoul', purpose='AUDIT_DRAFT', recipientScope='LOCAL', mode='SIMULATED', classification='INTERNAL')
# T01 정본 fixture: KR01-MOCK-E0001/E0002 입력·기대값이 항목·단위·계수·요율과 함께 그대로 보존된다
fx = [dict(event_id='KR01-MOCK-E0001', facility_id='KR-01', mode='SIMULATED', measurement_kind='interval_energy', quantity='10', unit='kWh', expected_emissions_kgco2e='5.0', expected_energy_cost_krw='1000'), dict(event_id='KR01-MOCK-E0002', facility_id='KR-01', mode='SIMULATED', measurement_kind='interval_energy', quantity='20', unit='kWh', expected_emissions_kgco2e='10.0', expected_energy_cost_krw='2000')]
bodies = {'KR01-MOCK-E0001': c.canon(fx[0]), 'KR01-MOCK-E0002': c.canon(fx[1])}
items = [c.item_ref(k, 'S01', 'event:' + k, '1', v, fact=[dict(metric='expected_emissions_kgco2e', value=fx[i]['expected_emissions_kgco2e'], unit='kgCO2e', boundary='SITE'), dict(metric='expected_energy_cost_krw', value=fx[i]['expected_energy_cost_krw'], unit='KRW', boundary='SITE')]) for i, (k, v) in enumerate(bodies.items())]
lin = [dict(edgeId='e1', fromRef='event:KR01-MOCK-E0001', toRef='run:r-1', method='S02 MOCK-EF-001/MOCK-TARIFF-001'), dict(edgeId='e2', fromRef='event:KR01-MOCK-E0002', toRef='run:r-1', method='S02 MOCK-EF-001/MOCK-TARIFF-001')]
body = c.build_manifest(CTX, items, lin); mb, mh = c.seal(body)
chk('T01 fixture 기대값·단위·필드명(event_id/facility_id/mode/quantity)이 증거 안에 원문 그대로 보존', json.loads(bodies['KR01-MOCK-E0002'])['expected_emissions_kgco2e'] == '10.0' and items[0]['factRef'][1]['value'] == '1000' and body['mode'] == 'SIMULATED' and body['flags']['draftOnly'], body['flags'])
chk('manifest 본체에 자기 hash·서명·ZIP hash가 없다(순환 방지)', not any(k in body for k in ('manifestHash', 'artifactHash', 'signature')))
b2, h2 = c.seal(c.build_manifest(CTX, list(reversed(items)), list(reversed(lin)))); chk('항목·계보 입력 순서와 무관하게 같은 manifestHash(정규화)', h2 == mh)
files = {k + '.json': v for k, v in bodies.items()}; z, ah = c.make_zip(mb, files, c.readme(body, 'NOT_CONFIGURED')); z2, ah2 = c.make_zip(mb, files, c.readme(body, 'NOT_CONFIGURED')); chk('ZIP 결정론: 같은 입력 → 같은 artifactHash', ah == ah2)
chk('정상 패키지 재개봉 검사 PASS(ZIP·manifest·항목별 hash)', c.verify_package(z, ah, mh)['verdict'] == 'PASS')
# T04 1바이트 변조
zb = bytearray(z); i = zb.find(b'"quantity"'); zb[i + 2] ^= 1; r = c.verify_package(bytes(zb), ah, mh); chk('T04 1바이트 변조 → BLOCKED(artifact hash 불일치)', r['verdict'] == 'BLOCKED' and not r['checks'][0]['ok'])
bad_files = dict(files); bad_files['KR01-MOCK-E0001.json'] = c.canon(dict(fx[0], quantity='11')); z3, ah3 = c.make_zip(mb, bad_files, 'x'); r = c.verify_package(z3, ah3, mh); chk('T04 항목 내용 변경(ZIP 재생성)도 항목 hash로 적발 → BLOCKED', r['verdict'] == 'BLOCKED' and any(x['check'] == 'ITEM:KR01-MOCK-E0001' and not x['ok'] for x in r['checks']), r)
chk('T04 manifest 변경 → BLOCKED', c.verify_package(z, ah, 'f' * 64)['verdict'] == 'BLOCKED')
# 항목 규칙
try: c.item_ref('x', 'S01', 's', '1', None); chk('INCLUDED인데 바이트 없음 거절', False)
except ValueError: chk('INCLUDED인데 바이트 없음 거절', True)
ms = c.item_ref('m1', 'S05', 'disclosure:none', None, None, inclusion='MISSING', reason='S05 상태 조회 계약 미합의'); chk('누락은 이유와 함께 MISSING(0·빈 값으로 대체 없음)', ms['byteHash'] is None and ms['byteSize'] == 0 and ms['inclusionReason'])
bi = copy.deepcopy(items); bi[0]['factRef'][0]['value'] = 5.0
try: c.build_manifest(CTX, bi, lin); chk('수치는 decimal 문자열만(부동소수 거절)', False)
except ValueError as e: chk('수치는 decimal 문자열만(부동소수 거절)', 'FACT_FORMAT' in str(e))
cyc = lin + [dict(edgeId='e3', fromRef='run:r-1', toRef='event:KR01-MOCK-E0001', method='bad')]
try: c.build_manifest(CTX, items, cyc); chk('계보 순환 차단', False)
except ValueError as e: chk('계보 순환 차단', 'CYCLE' in str(e))
chk('T11 상태 분기: 키 미구성→미서명 초안, 검증됨→PACKAGE_READY, 불일치/불명→BLOCKED, 누락→PARTIAL', [c.final_state('NOT_CONFIGURED', False), c.final_state('VERIFIED', False), c.final_state('MISMATCH', False), c.final_state('NOT_CONFIGURED', True)] == ['LOCAL_UNSIGNED_DRAFT_READY', 'PACKAGE_READY', 'BLOCKED', 'PARTIAL'])
chk('상태 전이 규칙(REQUESTED→PACKAGE_READY 직행 불가)', c.can('REQUESTED', 'ASSEMBLING') and not c.can('REQUESTED', 'PACKAGE_READY') and not c.can('PACKAGE_READY', 'ASSEMBLING'))
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
