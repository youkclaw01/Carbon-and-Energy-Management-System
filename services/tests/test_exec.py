import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execapi'))
import exec_app as EX
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE ExecutionIntentRef(executionId TEXT PRIMARY KEY, country, orgId, plantId, permitId, sourceService, businessOperationId, intentId, intentVersion, intentDigest, canonicalizationVersion, digestAlgorithm, executionState, rowVersion, createdAt);
CREATE TABLE ExecutionAttempt(attemptId TEXT PRIMARY KEY, executionId, attemptNo, executionEpoch, claimId, authorityVersion, sendState, startedAt, deadline, lastCheckedAt);
CREATE TABLE ExternalReceipt(receiptObservationId TEXT PRIMARY KEY, executionId, attemptId, providerId, externalReceiptId, receiptVersion, payloadDigest, verified, observedAt, ownerEffectId, effectVersion, quantityStatus, quantityValue, quantityUnit);
CREATE TABLE PermitGate(permitId TEXT PRIMARY KEY, blocked, blockVersion, executionEpoch, dispatchStartedCount);
CREATE TABLE ExecutionAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
EX.R = Repo('sqlite', cf); srv = make_server(8852, EX.route, EX.health, EX.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8852'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
OK = dict(schemaVersion='1', sourceService='S04', businessOperationId='op-1', intentId='i-1', intentVersion=1, intentDigest='a' * 64, canonicalizationVersion=EX.CANON, digestAlgorithm='sha256', sourceProjectionRef=dict(projectionId='p1', projectionVersion='1', contentHash='b' * 64), signedPermit='x.y.z', fencingEpoch=1)
H = {'Idempotency-Key': 'k1', 'X-Actor': 'permit-ingress'}
c, d = call('POST', '/v1/executions', OK); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = call('POST', '/v1/executions', {k: v for k, v in OK.items() if k != 'signedPermit'}, H); chk('signedPermit 없으면 400', c == 400 and 'signedPermit' in d['message'], d)
c, d = call('POST', '/v1/executions', dict(OK, sourceService='S09'), H); chk('sourceService 검증 422', c == 422 and d['code'] == 'BINDING_MISMATCH', d)
c, d = call('POST', '/v1/executions', dict(OK, canonicalizationVersion='x'), H); chk('미등록 정규화 규약 422', c == 422, d)
c, d = call('POST', '/v1/executions', dict(OK, sourceProjectionRef={}), H); chk('sourceProjectionRef 검증 422', c == 422, d)
c, d = call('POST', '/v1/executions', OK, H); chk('형식이 맞아도 permit 검증 불가 → 503 PERMIT_VERIFICATION_UNAVAILABLE(성공 ack·접수 없음)', c == 503 and d['code'] == 'PERMIT_VERIFICATION_UNAVAILABLE' and d['retryable'] is False, (c, d))
c, d = call('GET', '/v1/executions/' + str(uuid.uuid4())); chk('조회 404(존재·미전송·해제 증거 아님 안내)', c == 404 and '증거가 아닙니다' in d['message'], d)
c, d = call('GET', '/v1/executions/zzz'); chk('형식 오류 400', c == 400, d)
n = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT COUNT(*) FROM dbo.ExecutionIntentRef'), cur.fetchall())[1])[0][0]; chk('실행 행 0건(실행 닫힘)', n == 0)
rows = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT prevHash, hash, reason FROM dbo.ExecutionAudit ORDER BY auditId'), cur.fetchall())[1]); chk('거절 시도 감사 기록(체인 연속)', len(rows) == 1 and rows[0][2] == 'PERMIT_VERIFICATION_UNAVAILABLE')
c, d = call('GET', '/health'); chk('health(실행 닫힘)', c == 200 and '닫힘' in d['mode'], d)
# ---- v0.2: permit 검증 + 모의 실행 ----
import datetime as dt
class FakeVerifier:   # S07 검증을 대신하는 가짜: 서명이 'sig:'+digest이고 keyRef가 신뢰 경로일 때만 유효
    def verify_permit(self, pm):
        if pm['signature'] == 'boom': raise RuntimeError('approval down')
        if not pm['keyRef'].startswith('https://kv.test/keys/permit/'): return False, 'KEY_UNTRUSTED'
        return pm['signature'] == 'sig:' + EX.permit_digest(pm), 'BAD_SIGNATURE'
    claims = {}; boom = set(); log = []
    def claim_permit(self, pid, who):
        self.log.append((pid, who))
        if pid in self.boom: raise RuntimeError('approval down')
        if self.claims.get(pid, who) != who: return False, 'ALREADY_CLAIMED'
        self.claims[pid] = who; return True, 'CLAIMED'
EX.VERIFIER = FakeVerifier()
def mk(op='op-2', dgst='b' * 64, exp=None, sig=None, **kw):
    p = dict(permitId=str(uuid.uuid4()), requestId=str(uuid.uuid4()), operationKey=op, intentDigest=dgst, approvalVersion=1, authorityVersion=1, reservationId=str(uuid.uuid4()), amountMinor=1000, currency='KRW', expiresAt=exp or (dt.datetime.utcnow() + dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'))
    p.update(kw); p['signature'] = sig or 'sig:' + EX.permit_digest(p); p['keyRef'] = 'https://kv.test/keys/permit/v1'; return p
def body(p, op='op-2', dgst='b' * 64): return dict(OK, businessOperationId=op, intentDigest=dgst, signedPermit=p)
P1 = mk(); c, d = call('POST', '/v1/executions', body(P1), dict(H, **{'Idempotency-Key': 'k2'})); chk('유효 permit → 201 executed·모의 영수증', c == 201 and d['executionState'] == 'executed' and d['simulated'] and d['externalReceiptId'].startswith('SIM-'), d)
EID = d.get('executionId')
c, d2 = call('POST', '/v1/executions', body(P1), H); chk('같은 작업·같은 permit 재요청 → 200 replay(중복 실행 없음)', c == 200 and d2['replay'] and d2['executionId'] == EID, d2)
c, d = call('POST', '/v1/executions', body(mk(), op='op-2'), H); chk('같은 작업에 다른 permit → 409 OPERATION_CONFLICT', c == 409 and d['code'] == 'OPERATION_CONFLICT', d)
c, d = call('POST', '/v1/executions', body(dict(P1), op='op-3'), H); chk('같은 permit을 다른 작업에 재사용 → 422 BINDING_MISMATCH(operationKey 결속)', c == 422, d)
P2 = mk(op='op-4'); c, d = call('POST', '/v1/executions', body(P2, op='op-4'), H); chk('다른 유효 permit·작업 → 201', c == 201, d)
Pu = dict(P2); c, d = call('POST', '/v1/executions', body(Pu, op='op-4'), H); chk('같은 permit·같은 작업 재요청 → 200 replay', c == 200 and d.get('replay'), d)
# permit 1회 사용: 같은 permitId로 operationKey만 다르게 서명한 permit은 서명 규칙상 별개이므로, permitId 재사용을 직접 시험
P3 = mk(op='op-5', permitId=P2['permitId']); c, d = call('POST', '/v1/executions', body(P3, op='op-5'), H); chk('이미 사용된 permitId → 409 PERMIT_ALREADY_USED', c == 409 and d['code'] == 'PERMIT_ALREADY_USED', d)
c, d = call('POST', '/v1/executions', body(mk(sig='sig:bad', op='op-i1'), op='op-i1'), H); chk('서명 불일치 → 422 PERMIT_INVALID', c == 422 and d['code'] == 'PERMIT_INVALID', d)
c, d = call('POST', '/v1/executions', body(mk(sig='boom', op='op-6'), op='op-6'), H); chk('검증 서비스 오류 → 503 재시도 가능·접수 없음', c == 503 and d['retryable'], d)
c, d = call('POST', '/v1/executions', body(mk(exp='2020-01-01T00:00:00.000Z', op='op-7'), op='op-7'), H); chk('만료 permit → 422 PERMIT_EXPIRED', c == 422 and d['code'] == 'PERMIT_EXPIRED', d)
c, d = call('POST', '/v1/executions', body(mk(op='op-8', dgst='c' * 64), op='op-8', dgst='d' * 64), H); chk('permit·요청 intentDigest 불일치 → 422', c == 422, d)
pk = mk(op='op-9'); pk['keyRef'] = 'https://evil.test/keys/x/v1'; c, d = call('POST', '/v1/executions', body(pk, op='op-9'), H); chk('신뢰하지 않는 keyRef → 422 PERMIT_INVALID(검증은 S07이 판정)', c == 422 and d['code'] == 'PERMIT_INVALID' and 'KEY_UNTRUSTED' in d['message'], d)
c, d = call('GET', '/v1/executions/' + EID); chk('조회: 실행·시도 1·영수증 1(verified)', c == 200 and d['executionState'] == 'executed' and len(d['attempts']) == 1 and len(d['receipts']) == 1 and d['receipts'][0]['verified'], d)
c, d = call('POST', '/v1/executions/%s/reconcile' % EID, {}, H); chk('대사: 영수증 일치 → executed 유지', c == 200 and d['matched'] and d['executionState'] == 'executed', d)
EX.R.tx(lambda cur: EX.R.ex(cur, "UPDATE ExternalReceipt SET payloadDigest='0' WHERE executionId=?", (EID,)))
c, d = call('POST', '/v1/executions/%s/reconcile' % EID, {}, H); chk('대사: 영수증 변조 → review-required(자동 재송신 없음)', c == 200 and not d['matched'] and d['executionState'] == 'review-required', d)
n = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT COUNT(*) FROM dbo.ExecutionIntentRef'), cur.fetchall())[1])[0][0]; chk('실행 행은 성공한 2건만(거절·충돌·만료는 행 없음)', n == 2, n)
na = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT COUNT(*) FROM dbo.ExecutionAttempt'), cur.fetchall())[1])[0][0]; chk('시도도 2건(재송신 없음)', na == 2, na)
rows = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT prevHash, hash FROM dbo.ExecutionAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 체인 연속', all(rows[i][0] == rows[i-1][1] for i in range(1, len(rows))), len(rows))
c, d = call('GET', '/health'); chk('health 모의 실행 표시', c == 200 and '모의 실행' in d['mode'], d)
# ---- S07 claim(1회 사용의 권위) ----
FV = EX.VERIFIER
n0 = len(FV.log); Pc = mk(op='op-c1'); c, d = call('POST', '/v1/executions', body(Pc, op='op-c1'), H)
chk('성공 실행은 S07 claim을 먼저 호출(claimant=executionId)·claimedBy=S07', c == 201 and d['claimedBy'] == 'S07' and FV.log[-1] == (Pc['permitId'], d['executionId']) and len(FV.log) == n0 + 1, (d, FV.log[-1:]))
n1 = len(FV.log); c, d = call('POST', '/v1/executions', body(Pc, op='op-c1'), H); chk('같은 작업 재요청은 검증·claim 없이 replay(claim 재호출 없음)', c == 200 and d['replay'] and len(FV.log) == n1, (d, FV.log[n1:]))
Px = mk(op='op-c2'); FV.claims[Px['permitId']] = 'other-exec'; c, d = call('POST', '/v1/executions', body(Px, op='op-c2'), H); chk('S07이 다른 실행에 이미 claim한 permit → 409 PERMIT_ALREADY_USED·실행 행 없음', c == 409 and d['code'] == 'PERMIT_ALREADY_USED', d)
Pb = mk(op='op-c3'); FV.boom.add(Pb['permitId']); c, d = call('POST', '/v1/executions', body(Pb, op='op-c3'), H); chk('claim 호출 실패 → 503 재시도 가능·실행 행 없음(실행 전 확정 못 하면 보내지 않음)', c == 503 and d['code'] == 'PERMIT_CLAIM_UNAVAILABLE' and d['retryable'], d)
rows = EX.R.tx(lambda cur: (EX.R.ex(cur, "SELECT COUNT(*) FROM dbo.ExecutionIntentRef WHERE businessOperationId IN ('op-c2','op-c3')"), cur.fetchall()[0])[1]); chk('거절된 두 작업은 실행 기록이 없음', rows[0] == 0, rows)
# ---- permitIds 조회(열거 없음) ----
c, d = call('GET', '/v1/executions?permitIds=' + Pc['permitId']); chk('permitIds 조회: 실행 상태·모의 영수증 반환', c == 200 and len(d['items']) == 1 and d['items'][0]['executionState'] == 'executed' and d['items'][0]['simulated'] and d['items'][0]['receipts'], d)
c, d = call('GET', '/v1/executions'); chk('permitIds 없으면 빈 목록(전체 열거 불가)', c == 200 and d['items'] == [], d)
c, d = call('GET', '/v1/executions?permitIds=not-a-uuid'); chk('형식 오류 permitId는 400', c == 400, d)
c, d = call('GET', '/v1/executions?permitIds=' + str(uuid.uuid4())); chk('없는 permitId는 빈 목록', c == 200 and d['items'] == [], d)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
