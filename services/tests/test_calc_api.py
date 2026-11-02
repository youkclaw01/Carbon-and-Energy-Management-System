import sys, os, json, time, threading, urllib.request, urllib.error
os.environ['CALC_FAKE'] = '1'; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'calcapi'))
import calc_app as A
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, info)
A.DB = A.Fake(); srv = A.TS(('127.0.0.1', 8845), A.H); threading.Thread(target=srv.serve_forever, daemon=True).start()
B = 'http://127.0.0.1:8845'
def call(m, p, body=None, hdr=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(hdr or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
import datetime as dt
base = dt.datetime(2026, 10, 29, 0, 0, 0); T0 = A.ms(base)
def samples(n, start=T0): return [dict(ts_ms=start + i * 5000, grid_kw=1000.0, gas_nm3h=100.0) for i in range(n)]
state = dict(n=720, modes=['SIMULATED'])
A.LOADER['samples'] = lambda plant, s, e: (samples(state['n'], A.ms(s)), 'mock')
def modes(plant):
    if state['modes'] is None: raise RuntimeError('down')
    return state['modes']
A.LOADER['modes'] = modes
P = dict(plantId='KR-01', periodStart='2026-10-29T00:00:00Z', periodEnd='2026-10-29T01:00:00Z')
def wait(rid):
    for _ in range(100):
        c, d = call('GET', '/v1/calc-runs/' + rid)
        if d['businessState'] in ('ready', 'dq_failed'): return d
        time.sleep(0.1)
    return d
c, d = call('POST', '/v1/calc-runs', P); chk('Idempotency-Key 없으면 400', c == 400 and d['code'] == 'IDEMPOTENCY_KEY_REQUIRED', d)
c, d = call('POST', '/v1/calc-runs', P, {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); rid = d.get('runId')
chk('접수 202 + 확정 수치 없음(처리 중 표시)', c == 202 and d['publicationEligible'] is False and d['releaseId'] is None and 'values' not in d and d['mode'] == 'SIMULATED', (c, d))
r = wait(rid); v = {x['metric']: x['value'] for x in r.get('values', [])}
chk('후보→독립 검증 PASS→ready, scope2 459.400·scope1 210.000, 잠정(모의)·비발행', r['businessState'] == 'ready' and v.get('scope2_location_based') == '459.400' and v.get('scope1_stationary_fuel') == '210.000' and r['screenLabel'] == '잠정(모의)' and r['resultKind'] == 'SIMULATED' and r['validation']['verdict'] == 'PASS' and r['dq']['coverage'] == '1.000', r)
c, d = call('POST', '/v1/calc-runs', P, {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); chk('같은 키·같은 내용 → 같은 run(재처리 없음)', c == 200 and d['runId'] == rid, (c, d))
c, d = call('POST', '/v1/calc-runs', dict(P, periodEnd='2026-10-29T02:00:00Z'), {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); chk('같은 키·다른 내용 → 409', c == 409 and d['code'] == 'IDEMPOTENCY_CONFLICT', (c, d))
c, d = call('POST', '/v1/calc-runs', P, {'Idempotency-Key': 'k2', 'X-Actor': 'tester'}); chk('다른 키·같은 범위·버전 → 기존 run 반환(새 산정 없음)', c == 200 and d['runId'] == rid and 'note' in d, (c, d))
state['n'] = 600; c, d = call('POST', '/v1/calc-runs', dict(P, periodStart='2026-10-29T03:00:00Z', periodEnd='2026-10-29T04:00:00Z'), {'Idempotency-Key': 'k3'}); r2 = wait(d['runId'])
chk('표본 600/720 → dq_failed·수치 미반환·DQ 검사 노출', r2['businessState'] == 'dq_failed' and 'values' not in r2 and r2['dq']['coverage'] == '0.833' and any(x['checkId'] == 'DQ:coverage' and x['status'] == 'FAIL' for x in r2['validation']['checks']) and r2['screenLabel'] == '검증 실패(수치 사용 불가)', r2)
state['n'] = 720
state['modes'] = None; c, d = call('POST', '/v1/calc-runs', dict(P, periodStart='2026-10-29T05:00:00Z', periodEnd='2026-10-29T06:00:00Z'), {'Idempotency-Key': 'k4'}); chk('S01 mode 확인 불가 → 503(산정 안 함)', c == 503 and d['retryable'] is True, (c, d))
state['modes'] = ['SIMULATED', 'ACTUAL']; c, d = call('POST', '/v1/calc-runs', dict(P, periodStart='2026-10-29T05:00:00Z', periodEnd='2026-10-29T06:00:00Z'), {'Idempotency-Key': 'k5'}); chk('SIMULATED/ACTUAL 혼합 → 422', c == 422 and d['code'] == 'MODE_MIXED_OR_EMPTY', (c, d)); state['modes'] = ['SIMULATED']
for n, body, code in [('JP-01은 KR DB02 범위 밖 → 422', dict(P, plantId='JP-01'), 'PLANT_NOT_IN_SCOPE'), ('WHAT_IF는 S03 합의 전 → 422', dict(P, calculationKind='WHAT_IF'), 'KIND_UNSUPPORTED'), ('미래 기간 → 422', dict(P, periodStart='2030-01-01T00:00:00Z', periodEnd='2030-01-01T01:00:00Z'), 'PERIOD_IN_FUTURE'), ('기간 역전 → 400', dict(P, periodEnd='2026-10-28T00:00:00Z'), 'BAD_PERIOD'), ('8일 초과 → 422', dict(P, periodEnd='2026-11-07T00:00:00Z'), 'PERIOD_TOO_LONG'), ('계수 적용기간 밖(2028) → 오류', dict(P, periodStart='2028-01-01T00:00:00Z', periodEnd='2028-01-01T01:00:00Z'), None)]:
    c, d = call('POST', '/v1/calc-runs', body, {'Idempotency-Key': 'x-%d' % abs(hash(n))})
    chk(n, (d.get('code') == code) if code else c >= 400, (c, d))
# 발행 명령: certified 차단
c, d = call('POST', '/v1/releases', dict(runId=rid, candidateHash=r['candidateHash']), {'X-Actor': 'tester'}); chk('PASS run의 certified 발행 요청 → 422 CERTIFIED_BLOCKED(모의 입력·권한 출처 미결·S07 승인 없음)', c == 422 and d['code'] == 'CERTIFIED_BLOCKED' and 'SIMULATED_INPUT' in d['message'] and 'GRANT_AUTHORITY_UNRESOLVED' in d['message'], (c, d))
cid = d['message'].split('commandId=')[1].rstrip(')'); c, d = call('GET', '/v1/release-commands/' + cid); chk('차단된 명령이 기록·조회됨(blocked)', c == 200 and d['commandState'] == 'blocked' and 'SIMULATED_INPUT' in d['denyReason'], d)
c, d = call('POST', '/v1/releases', dict(runId=r2['runId']), {}); chk('검증 실패 run은 발행 요청 자체 422', c == 422 and d['code'] == 'VALIDATION_NOT_PASSED', d)
c, d = call('GET', '/v1/releases/' + cid); chk('발행본 없음 → 404(존재하지 않는 release)', c == 404, (c, d))
c, d = call('GET', '/v1/calc-runs/not-a-uuid'); chk('형식 오류 400', c == 400, d)
c, d = call('GET', '/v1/calc-runs?plantId=KR-01'); chk('목록 조회', c == 200 and len(d['items']) >= 2, d)
au = A.DB.audits; chain = all(au[i]['previousHash'] == (au[i - 1]['recordHash'] if i else None) for i in range(len(au))); chk('감사 해시 체인 연속 %d행' % len(au), chain and len(au) > 8)
c, d = call('GET', '/health'); chk('health', c == 200 and d['ok'])
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
