import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'wfapi'))
import wf_app as WF, wf_core as K
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
def rej(fn, code):
    try: fn(); return False
    except K.Reject as e: return e.code == code
job = dict(state='PENDING', revision=1)
chk('전이: PENDING→READY ok, PENDING→SUCCEEDED 불가', K.can('PENDING', 'READY') and not K.can('PENDING', 'SUCCEEDED'))
chk('CAS: revision 불일치 412', rej(lambda: K.transition(job, 'READY', 2), 'CAS_MISMATCH'))
chk('종료 상태는 덮어쓰지 않음 409', rej(lambda: K.transition(dict(state='SUCCEEDED', revision=3), 'READY', 3), 'TERMINAL_STATE'))
chk('취소는 CANCEL_REQUESTED(접수)까지, 곧바로 CANCELLED 불가', K.transition(job, 'CANCEL_REQUESTED', 1)['state'] == 'CANCEL_REQUESTED' and not K.can('PENDING', 'CANCELLED'))
chk('재개: 대기 상태가 아니면 409, 의존 권위 미확인이면 422', rej(lambda: K.resume_check(job, 'confirmed'), 'BAD_STATE') and rej(lambda: K.resume_check(dict(state='WAITING_APPROVAL', revision=2), None), 'UNSAFE_RESUME') and K.resume_check(dict(state='WAITING_APPROVAL', revision=2), 'confirmed') == 'READY')
DDL = '''CREATE TABLE Job(jobId TEXT PRIMARY KEY, country, environment, orgId, plantId, principal, jobKey, requestDigest, ownerService, workflowType, definitionVersion, inputRef, inputDigest, runKey, state, waitingReason, revision, leaseEpoch DEFAULT 0, leaseOwner, leaseUntil, deadlineAt, retryPolicyVersion, createdAt, updatedAt, UNIQUE(country,orgId,principal,jobKey));
CREATE TABLE StepAttempt(jobId, stepId, attemptNo, operationKey, targetService, taskType, targetRef, expectedTargetVersion, dispatchState, outcome, epoch, providerJobRef, observedAt);
CREATE TABLE Checkpoint(jobId, checkpointNo, definitionVersion, lastCommittedStep, sourceRefs, digest, revision, epoch);
CREATE TABLE TransitionAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
WF.R = Repo('sqlite', cf); srv = make_server(8851, WF.route, WF.health, WF.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8851'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
DL = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
JB = dict(jobKey='calc-1', workflowType='calc.run', definitionVersion='1', ownerService='S02', inputRef='run:abc', inputDigest='a' * 64, runKey='b' * 64, deadlineAt=DL, retryPolicyVersion='1', plantId='KR-01')
def post(b, k='k1', actor='s02'): return call('POST', '/v1/jobs', b, {'Idempotency-Key': k, 'X-Actor': actor})
c, d = call('POST', '/v1/jobs', JB); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = post(JB); jid = d.get('jobId'); chk('생성 202: PENDING·revision 1·엔진 미기동 안내(진행률 없음)', c == 202 and d['state'] == 'PENDING' and d['revision'] == 1 and d['stage'] is None and d['note'], (c, d))
c, d2 = post(JB); chk('같은 jobKey·같은 내용 → 200 같은 작업', c == 200 and d2['jobId'] == jid, (c, d2))
c, d2 = post(dict(JB, inputDigest='c' * 64)); chk('같은 jobKey·다른 내용 → 409', c == 409, (c, d2))
c, d2 = post(dict(JB, jobKey='calc-2'), 'k2'); chk('같은 runKey를 다른 jobKey로 → 기존 작업(중복 제출 방지)', c == 200 and d2['jobId'] == jid, (c, d2))
for n, b, code in [('미등록 workflowType 422', dict(JB, jobKey='x1', workflowType='ship.it'), 422), ('owner 불일치 422', dict(JB, jobKey='x2', ownerService='S08'), 422), ('calc.run은 runKey 필요 400', {k: v for k, v in dict(JB, jobKey='x3').items() if k != 'runKey'}, 400), ('자격 포함 URL 거절 422', dict(JB, jobKey='x4', workflowType='evidence.assemble', ownerService='S06', inputRef='https://u:p@x/y', runKey=None), 422), ('지난 마감 422', dict(JB, jobKey='x5', runKey='d' * 64, deadlineAt='2020-01-01T00:00:00Z'), 422), ('다른 국가 공장 422', dict(JB, jobKey='x6', runKey='e' * 64, plantId='JP-01'), 422)]:
    c, d = post(b, 'v-' + str(abs(hash(n)))); chk(n, c == code, (c, d))
c, d = call('GET', '/v1/jobs/' + jid); chk('조회', c == 200 and d['state'] == 'PENDING', d)
c, d = call('POST', '/v1/jobs/' + jid + '/resume', dict(commandId='c1', reason='r'), {'If-Match': '1', 'X-Actor': 'u'}); chk('PENDING 작업 재개 409 BAD_STATE(재개는 대기 상태만)', c == 409 and d['code'] == 'BAD_STATE', (c, d))
c, d = call('POST', '/v1/jobs/' + jid + '/cancel', dict(commandId='c2', reason='r'), {'X-Actor': 'u'}); chk('취소: If-Match 없으면 400', c == 400, d)
c, d = call('POST', '/v1/jobs/' + jid + '/cancel', dict(commandId='c2', reason='r'), {'If-Match': '9', 'X-Actor': 'u'}); chk('취소: revision 불일치 412', c == 412, (c, d))
c, d = call('POST', '/v1/jobs/' + jid + '/cancel', dict(commandId='c2', reason='중복 제출 정리'), {'If-Match': '1', 'X-Actor': 'u'}); chk('취소 202: CANCEL_REQUESTED·revision 2(실제 중단 아님)', c == 202 and d['state'] == 'CANCEL_REQUESTED' and d['revision'] == 2, (c, d))
c, d = call('POST', '/v1/jobs/' + jid + '/cancel', dict(commandId='c3', reason='r'), {'If-Match': '2', 'X-Actor': 'u'}); chk('이미 취소 접수된 작업의 재취소 409', c == 409, (c, d))
rows = WF.R.tx(lambda cur: (WF.R.ex(cur, 'SELECT prevHash, hash, action FROM dbo.TransitionAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행 · 거절(DENIED)도 기록' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and any('DENIED' in r[2] for r in rows), [r[2] for r in rows])
c, d = call('GET', '/health'); chk('health(수동 엔진 표시)', c == 200 and '수동 엔진' in d['mode'], d)
# ---- v0.2 수동 엔진 ----
CALC = {}; EV = {}; ING = {}
def fake_fetch(url, timeout=20):
    rid = url.rsplit('/', 1)[-1]; r = (EV if '/v1/manifests/' in url else ING if '/v1/ingestions/' in url else CALC).get(rid)
    if r is None: return 404, b'{}'
    if r == 'down': return 0, b''
    return 200, json.dumps(r).encode()
WF.FETCH = fake_fetch; WF.CALC_URL = 'http://calc.test'; WF.EVID_URL = 'http://evid.test'; WF.INGEST_URL = 'http://ing.test'
def mkjob(key, rk, ref, **kw): c, d = post(dict(JB, jobKey=key, runKey=rk, inputRef=ref, inputDigest='d' * 64, **kw), 'e-' + key); return d['jobId']
def tick(**b): c, d = call('POST', '/v1/engine/tick', b, {'X-Actor': 'operator'}); return c, d
def st(j): return call('GET', '/v1/jobs/' + j)[1]
J_ok, J_fail, J_wait, J_missing, J_mis, J_down, J_ev = (mkjob('e-ok', '1' * 64, 'calc-run:r-ok'), mkjob('e-fail', '2' * 64, 'calc-run:r-fail'), mkjob('e-wait', '3' * 64, 'calc-run:r-wait'), mkjob('e-miss', '4' * 64, 'calc-run:r-miss'), mkjob('e-mis', '5' * 64, 'calc-run:r-mis'), mkjob('e-down', '6' * 64, 'calc-run:r-down'), None)
c, d = post(dict(JB, jobKey='e-ev', workflowType='ingest.followup', ownerService='S01', runKey=None, inputRef='ingestion:x', inputDigest='d' * 64), 'e-ev'); J_ev = d['jobId']; WF.R.tx(lambda cur: WF.R.ex(cur, "UPDATE Job SET workflowType='x.unregistered' WHERE jobId=?", (J_ev,)))
CALC.update({'r-ok': dict(runKey='1' * 64, businessState='ready', candidateHash='f' * 64), 'r-fail': dict(runKey='2' * 64, businessState='dq_failed'), 'r-wait': dict(runKey='3' * 64, businessState='validating'), 'r-mis': dict(runKey='9' * 64, businessState='ready', candidateHash='e' * 64), 'r-down': 'down'})
c, d = tick(limit=20); R_ = {x['jobId']: x for x in d['results']}
chk('틱: 엔진은 호출될 때만 동작(자동 기동 없음) · 처리 결과 반환', c == 200 and d['mode'] == 'manual-tick' and d['processed'] >= 7, d)
chk('calc ready → SUCCEEDED(후보 해시 기록·certified 아님)', st(J_ok)['state'] == 'SUCCEEDED' and R_[J_ok]['candidateHash'] == 'f' * 64, R_.get(J_ok))
chk('calc dq_failed → FAILED(DQ_FAILED)', st(J_fail)['state'] == 'FAILED' and st(J_fail)['waitingReason'] == 'DQ_FAILED', st(J_fail))
chk('S02 진행 중 → WAITING_SOURCE', st(J_wait)['state'] == 'WAITING_SOURCE' and st(J_wait)['waitingReason'] == 'S02_VALIDATING', st(J_wait))
chk('S02에 없음 → WAITING_SOURCE(S02_RUN_NOT_FOUND)', st(J_missing)['state'] == 'WAITING_SOURCE' and st(J_missing)['waitingReason'] == 'S02_RUN_NOT_FOUND', st(J_missing))
chk('runKey 불일치 → FAILED(RUN_KEY_MISMATCH, 다른 산정 결과로 성공 처리 안 함)', st(J_mis)['state'] == 'FAILED' and st(J_mis)['waitingReason'] == 'RUN_KEY_MISMATCH', st(J_mis))
chk('S02 확인 불가 → READY로 되돌림·성공/실패 만들지 않음', st(J_down)['state'] == 'READY' and R_[J_down]['action'] == 'UNCHANGED', (st(J_down), R_.get(J_down)))
chk('핸들러 없는 workflowType은 PENDING 유지(가짜 진행률 없음)', st(J_ev)['state'] == 'PENDING' and R_[J_ev]['reason'] == 'NO_HANDLER', st(J_ev))
n = WF.R.tx(lambda cur: (WF.R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.StepAttempt), (SELECT COUNT(*) FROM dbo.[Checkpoint])'), cur.fetchall()[0])[1]); chk('관찰 시도·체크포인트는 성공 1건만 기록', tuple(n) == (1, 1), n)
CALC['r-wait'] = dict(runKey='3' * 64, businessState='ready', candidateHash='a' * 64); CALC['r-miss'] = dict(runKey='4' * 64, businessState='ready', candidateHash='b' * 64)
c, d = tick(limit=20); chk('재틱: 대기 작업이 S02 준비되면 SUCCEEDED로(WAITING→READY→RUNNING→SUCCEEDED)', st(J_wait)['state'] == 'SUCCEEDED' and st(J_missing)['state'] == 'SUCCEEDED', (st(J_wait), st(J_missing)))
c, d = tick(limit=20); chk('종료된 작업은 다시 처리하지 않음(덮어쓰기 없음)', all(x['jobId'] not in (J_ok, J_fail, J_wait, J_missing, J_mis) for x in d['results']), d)
# 취소 확인·마감·임차 만료
Jc = mkjob('e-cancel', '7' * 64, 'calc-run:r-c'); jc = st(Jc); call('POST', '/v1/jobs/' + Jc + '/cancel', dict(commandId='c9', reason='r'), {'If-Match': str(jc['revision']), 'X-Actor': 'u'})
Jd = mkjob('e-deadline', '8' * 64, 'calc-run:r-d'); WF.R.tx(lambda cur: WF.R.ex(cur, "UPDATE Job SET deadlineAt='2020-01-01 00:00:00' WHERE jobId=?", (Jd,)))
Jl = mkjob('e-lease', 'a' * 64, 'calc-run:r-l'); WF.R.tx(lambda cur: WF.R.ex(cur, "UPDATE Job SET state='RUNNING', leaseOwner='x', leaseUntil='2020-01-01 00:00:00', leaseEpoch=1 WHERE jobId=?", (Jl,)))
Jn = mkjob('e-notexp', 'b' * 64, 'calc-run:r-n'); WF.R.tx(lambda cur: WF.R.ex(cur, "UPDATE Job SET state='RUNNING', leaseOwner='x', leaseUntil='2999-01-01 00:00:00' WHERE jobId=?", (Jn,)))
c, d = tick(limit=30); R2 = {x['jobId']: x for x in d['results']}
chk('취소 접수 → CANCELLED(엔진이 확인)', st(Jc)['state'] == 'CANCELLED', st(Jc))
chk('마감 지난 작업 → FAILED(DEADLINE_EXCEEDED)', st(Jd)['state'] == 'FAILED' and st(Jd)['waitingReason'] == 'DEADLINE_EXCEEDED', st(Jd))
chk('임차 만료된 RUNNING → READY·epoch 유지(재실행 아님)', R2[Jl]['action'] == 'LEASE_RECOVERED' and st(Jl)['state'] == 'READY', (R2.get(Jl), st(Jl)))
chk('임차 유효한 RUNNING은 건드리지 않음', R2[Jn]['action'] == 'SKIPPED' and st(Jn)['state'] == 'RUNNING', (R2.get(Jn), st(Jn)))
c, d = call('POST', '/v1/engine/tick', {'limit': 'x'}, {}); chk('limit 형식 오류 400', c == 400, d)
rows = WF.R.tx(lambda cur: (WF.R.ex(cur, 'SELECT prevHash, hash FROM dbo.TransitionAudit ORDER BY auditId'), cur.fetchall())[1]); chk('엔진 전이도 감사 체인 연속(%d행)' % len(rows), all(rows[i][0] == rows[i - 1][1] for i in range(1, len(rows))), len(rows))
# ---- evidence.assemble 핸들러(S06 관찰) ----
def mkev(key, mid): c, d = post(dict(JB, jobKey=key, workflowType='evidence.assemble', ownerService='S06', runKey=None, inputRef='manifest:' + mid, inputDigest='d' * 64), 'v-' + key); return d['jobId']
E1, E2, E3, E4, E5 = mkev('ev-ok', 'm-ok'), mkev('ev-fail', 'm-fail'), mkev('ev-wait', 'm-wait'), mkev('ev-miss', 'm-miss'), mkev('ev-draft', 'm-draft')
EV.update({'m-ok': dict(generationState='PACKAGE_READY', package=dict(artifactHash='1' * 64), manifestHash='2' * 64), 'm-fail': dict(generationState='FAILED'), 'm-wait': dict(generationState='REQUESTED'), 'm-draft': dict(generationState='LOCAL_UNSIGNED_DRAFT_READY', manifestHash='3' * 64)})
c, d = tick(limit=50); R3 = {x['jobId']: x for x in d['results']}
chk('증빙 패키지 PACKAGE_READY → SUCCEEDED(패키지 해시 기록·외부 인증 아님)', st(E1)['state'] == 'SUCCEEDED' and R3[E1]['candidateHash'] == '1' * 64, (st(E1), R3.get(E1)))
chk('미서명 초안 준비 → SUCCEEDED(매니페스트 해시)', st(E5)['state'] == 'SUCCEEDED' and R3[E5]['candidateHash'] == '3' * 64, st(E5))
chk('증빙 FAILED → FAILED(S06_FAILED)', st(E2)['state'] == 'FAILED' and st(E2)['waitingReason'] == 'S06_FAILED', st(E2))
chk('증빙 REQUESTED → WAITING_SOURCE(S06_REQUESTED)', st(E3)['state'] == 'WAITING_SOURCE' and st(E3)['waitingReason'] == 'S06_REQUESTED', st(E3))
chk('증빙 매니페스트 없음 → WAITING_SOURCE', st(E4)['state'] == 'WAITING_SOURCE' and st(E4)['waitingReason'] == 'S06_MANIFEST_NOT_FOUND', st(E4))
n = WF.R.tx(lambda cur: (WF.R.ex(cur, "SELECT COUNT(*) FROM dbo.StepAttempt WHERE targetService='S06'"), cur.fetchall()[0])[1]); chk('S06 관찰 시도는 성공 2건만 기록', n[0] == 2, n)
# ---- ingest.followup 핸들러(S01 관찰) ----
def mkig(key, bid): c, d = post(dict(JB, jobKey=key, workflowType='ingest.followup', ownerService='S01', runKey=None, inputRef='ingestion:' + bid, inputDigest='d' * 64), 'g-' + key); return d['jobId']
G1, G2, G3, G4, G5 = mkig('ig-ok', 'b-ok'), mkig('ig-quar', 'b-quar'), mkig('ig-recv', 'b-recv'), mkig('ig-miss', 'b-miss'), mkig('ig-unk', 'b-unk')
ING.update({'b-ok': dict(status='LANDED', rawDigest='7' * 64), 'b-quar': dict(status='QUARANTINED'), 'b-recv': dict(status='RECEIVING'), 'b-unk': 'down'})
c, d = tick(limit=50); R4 = {x['jobId']: x for x in d['results']}
chk('수신 LANDED → SUCCEEDED(원본 해시 기록)', st(G1)['state'] == 'SUCCEEDED' and R4[G1]['candidateHash'] == '7' * 64, (st(G1), R4.get(G1)))
chk('수신 QUARANTINED → FAILED(S01_QUARANTINED)', st(G2)['state'] == 'FAILED' and st(G2)['waitingReason'] == 'S01_QUARANTINED', st(G2))
chk('수신 RECEIVING → WAITING_SOURCE(S01_RECEIVING)', st(G3)['state'] == 'WAITING_SOURCE' and st(G3)['waitingReason'] == 'S01_RECEIVING', st(G3))
chk('수신 배치 없음 → WAITING_SOURCE(S01_BATCH_NOT_FOUND)', st(G4)['state'] == 'WAITING_SOURCE' and st(G4)['waitingReason'] == 'S01_BATCH_NOT_FOUND', st(G4))
chk('S01 확인 불가 → READY 유지·성공/실패 없음', st(G5)['state'] == 'READY' and R4[G5]['action'] == 'UNCHANGED', (st(G5), R4.get(G5)))
n = WF.R.tx(lambda cur: (WF.R.ex(cur, "SELECT COUNT(*) FROM dbo.StepAttempt WHERE targetService='S01'"), cur.fetchall()[0])[1]); chk('S01 관찰 시도는 성공 1건만 기록', n[0] == 1, n)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
