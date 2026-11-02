import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'approvalapi'))
import approval_app as AP
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE PolicyEvaluation(evaluationId TEXT PRIMARY KEY, country, orgId, principal, idemKey, requestDigest, action, resource, purpose, operationKey, intentDigest, canonicalizationVersion, digestAlgorithmId, amountMinor, currency, decision, reasonCode, policyVersion, proposeOnly, createdAt, expiresAt, UNIQUE(country,orgId,principal,idemKey));
CREATE TABLE AppUser(userId TEXT PRIMARY KEY, username UNIQUE, pwHash, pwSalt, status, isAdmin, mfaSecretEnc, mfaEnrolled, mfaLastStep, failCount, lockedUntil, createdAt, email, displayName, grade, decidedBy, decidedAt);
CREATE TABLE AppSession(tokenHash TEXT PRIMARY KEY, userId, mfaVerified, createdAt, expiresAt, revokedAt);
CREATE TABLE UserGrant(grantId TEXT PRIMARY KEY, userId, action, grantedBy, validFrom, validTo, revokedAt);
CREATE TABLE ApprovalRequest(intentRef, requestId TEXT PRIMARY KEY, country, orgId, evaluationId, requester, idemKey, requestDigest, operationKey, intentRevision, intentDigest, digestVerified, action, purpose, amountMinor, currency, state, rev, approvalVersion, expiresAt, createdAt, updatedAt, requestReason, reasonUpdatedAt, UNIQUE(country,orgId,requester,idemKey));
CREATE TABLE LimitAccount(accountId TEXT PRIMARY KEY, country, orgId, principalScope, action, currency, periodStart, periodEnd, capMinor, heldMinor, settledMinor, rev);
CREATE TABLE ApprovalAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
AP.R = Repo('sqlite', cf); srv = make_server(8847, AP.route, AP.health, AP.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8847'
import hashlib as _hl
AP.R.tx(lambda cur: (AP.R.ex(cur, "INSERT INTO AppUser(userId, username, pwHash, pwSalt, status, isAdmin, mfaEnrolled, mfaLastStep, failCount, createdAt) VALUES ('u-req1','req1','x','y','active',0,0,0,0,'2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES ('g1','u-req1','request','t','2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO AppSession(tokenHash, userId, mfaVerified, createdAt, expiresAt) VALUES (?, 'u-req1', 0, '2026-10-31 00:00:00.000', '2099-01-01 00:00:00.000')".replace('?', "'" + _hl.sha256(b'tok-req1').hexdigest() + "'"))))
AP.R.tx(lambda cur: (AP.R.ex(cur, "INSERT INTO AppUser(userId, username, pwHash, pwSalt, status, isAdmin, mfaEnrolled, mfaLastStep, failCount, createdAt) VALUES ('u-oth','oth','x','y','active',0,0,0,0,'2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES ('g2','u-oth','request','t','2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO AppSession(tokenHash, userId, mfaVerified, createdAt, expiresAt) VALUES (?, 'u-oth', 0, '2026-10-31 00:00:00.000', '2099-01-01 00:00:00.000')".replace('?', "'" + _hl.sha256(b'tok-oth').hexdigest() + "'"))))
def call(m, p, body=None, h=None):
    if m == 'POST' and (p == '/v1/approval-requests' or p.endswith('/reason')) and 'no-auth' not in (h or {}) and 'Authorization' not in (h or {}): h = dict(h or {}, Authorization='Bearer tok-req1')
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
EV = dict(action='procurement.rec.purchase', resource='REC', purpose='HEDGE', operationKey='KR|AMA-KR|S04|op-1', intentDigest='a' * 64, canonicalizationVersion='ama.intent.v1/jcs-1', digestAlgorithmId='sha256', amount=dict(value='1000000', currency='KRW'))
c, d = call('POST', '/v1/policy-evaluations', EV); chk('Idempotency-Key 없으면 400', c == 400 and d['code'] == 'IDEMPOTENCY_KEY_REQUIRED', d)
c, d = call('POST', '/v1/policy-evaluations', EV, {'Idempotency-Key': 'e1', 'X-Actor': 'req1'}); eid = d.get('evaluationId')
chk('평가 201: needs-approval·POLICY_UNRESOLVED·proposeOnly(실행 허가 아님)', c == 201 and d['decision'] == 'needs-approval' and d['proposeOnly'] is True and d['reasonCode'] == 'POLICY_UNRESOLVED', (c, d))
c, d2 = call('POST', '/v1/policy-evaluations', EV, {'Idempotency-Key': 'e1', 'X-Actor': 'req1'}); chk('같은 키·같은 내용 → 200 같은 평가', c == 200 and d2['evaluationId'] == eid, (c, d2))
c, d2 = call('POST', '/v1/policy-evaluations', dict(EV, operationKey='other'), {'Idempotency-Key': 'e1', 'X-Actor': 'req1'}); chk('같은 키·다른 내용 → 409', c == 409 and d2['code'] == 'KEY_DIGEST_CONFLICT', (c, d2))
c, d2 = call('POST', '/v1/policy-evaluations', dict(EV, canonicalizationVersion='v0'), {'Idempotency-Key': 'e2'}); chk('미지원 규약 → 422', c == 422 and d2['code'] == 'CANONICALIZATION_UNSUPPORTED', d2)
c, d2 = call('POST', '/v1/policy-evaluations', dict(EV, amount=dict(value='1.5', currency='KRW')), {'Idempotency-Key': 'e3'}); chk('최소단위 미만 금액 → 400', c == 400 and d2['code'] == 'BAD_AMOUNT', d2)
WHY = '일본 사업장 2026년 예상 부족분을 채우기 위한 사전 매입입니다.'
RQ = dict(evaluationId=eid, intentRevision=1, intentDigest='a' * 64, reason=WHY)
c, d = call('POST', '/v1/approval-requests', RQ, {'Idempotency-Key': 'r1', 'X-Actor': 'req1'}); rid = d.get('requestId')
chk('신청 201: pending·rev 1·digest 미재검증·실행 불가(executable=false)', c == 201 and d['state'] == 'pending' and d['rev'] == 1 and d['digestVerified'] is False and d['executable'] is False and d['amountMinor'] == 1000000, (c, d))
c, d2 = call('POST', '/v1/approval-requests', RQ, {'Idempotency-Key': 'r1', 'X-Actor': 'req1'}); chk('신청 멱등 재요청 200 같은 ID', c == 200 and d2['requestId'] == rid, (c, d2))
c, d2 = call('POST', '/v1/approval-requests', dict(RQ, intentDigest='b' * 64), {'Idempotency-Key': 'r2', 'X-Actor': 'req1'}); chk('평가에 고정된 digest와 다르면 409(조건 변경은 새 평가)', c == 409 and d2['code'] == 'DIGEST_MISMATCH', d2)
c, d2 = call('POST', '/v1/approval-requests', dict(RQ, evaluationId=str(uuid.uuid4())), {'Idempotency-Key': 'r3'}); chk('없는 평가 404', c == 404, d2)
chk('신청 사유 저장·조회(직접 입력한 문구 그대로)', call('GET', '/v1/approval-requests/' + rid)[1].get('reason') == WHY and call('GET', '/v1/approval-requests/' + rid)[1].get('reasonUpdatedAt'), (c, d))
c, d3 = call('POST', '/v1/approval-requests', dict(RQ, reason=''), {'Idempotency-Key': 'rr1'}); chk('사유 없음(빈 문자열) → 400 REASON_LENGTH', c == 400 and d3['code'] == 'REASON_LENGTH', d3)
c, d3 = call('POST', '/v1/approval-requests', {k: v for k, v in RQ.items() if k != 'reason'}, {'Idempotency-Key': 'rr2'}); chk('사유 필드 자체가 없으면 400 REASON_REQUIRED', c == 400 and d3['code'] == 'REASON_REQUIRED', d3)
c, d3 = call('POST', '/v1/approval-requests', dict(RQ, reason='짧음'), {'Idempotency-Key': 'rr3'}); chk('9자 이하 → 400', c == 400 and d3['code'] == 'REASON_LENGTH', d3)
c, d3 = call('POST', '/v1/approval-requests', dict(RQ, reason='가' * 501), {'Idempotency-Key': 'rr4'}); chk('501자 → 400', c == 400 and d3['code'] == 'REASON_LENGTH', d3)
c, d3 = call('POST', '/v1/approval-requests', dict(RQ, reason=42), {'Idempotency-Key': 'rr5'}); chk('문자열이 아니면 400', c == 400 and d3['code'] == 'REASON_REQUIRED', d3)
c, d3 = call('POST', '/v1/approval-requests', dict(RQ, reason='다른 사유 문구입니다 열 글자 이상'), {'Idempotency-Key': 'r1', 'X-Actor': 'req1'}); chk('같은 키·다른 사유 → 409(사유도 요청 내용에 포함)', c == 409 and d3['code'] == 'KEY_DIGEST_CONFLICT', d3)
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason='  수량을\x00 조정했고\n\n\n\n근거는 부족분 대비 100%입니다.  ')); chk('신청자 본인은 승인 대기 중 사유 수정 200(제어문자 제거·공백 정리)', c == 200 and d3['result'] == 'updated' and '\x00' not in d3['reason'] and d3['reason'].startswith('수량을 조정했고') and '\n\n\n' not in d3['reason'], (c, d3))
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason=d3['reason'])); chk('같은 내용 재전송은 unchanged(수정 시각 불변)', c == 200 and d3['result'] == 'unchanged', d3)
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason='다른 사람이 바꾸려는 사유입니다 열 글자 이상'), {'Authorization': 'Bearer tok-oth'}); chk('신청자가 아닌 사용자는 수정 403', c == 403 and d3['code'] == 'FORBIDDEN', d3)
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason='짧음')); chk('수정 시에도 길이 검증 400', c == 400, d3)
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason=WHY), {'no-auth': '1'}); chk('인증 없으면 401', c == 401, d3)
c, d3 = call('POST', '/v1/approval-requests/' + str(uuid.uuid4()) + '/reason', dict(reason=WHY)); chk('없는 신청 404', c == 404, d3)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ApprovalRequest SET state='approved' WHERE requestId=?".replace('?', "'" + rid + "'")))
c, d3 = call('POST', '/v1/approval-requests/' + rid + '/reason', dict(reason=WHY)); chk('승인 대기가 아니면 수정 409 NOT_PENDING(결정 후 변경 불가)', c == 409 and d3['code'] == 'NOT_PENDING', d3)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ApprovalRequest SET state='pending' WHERE requestId=?".replace('?', "'" + rid + "'")))
aud = AP.R.tx(lambda cur: (AP.R.ex(cur, "SELECT action FROM ApprovalAudit WHERE target=?".replace('?', "'" + rid + "'")), [x[0] for x in cur.fetchall()])[1])
chk('감사 기록: 사유 입력·수정·거부가 모두 남음', 'REQUEST_REASON' in aud and 'REQUEST_REASON_UPDATE' in aud and aud.count('REQUEST_REASON_DENY') == 2, aud)
c, d = call('GET', '/v1/approval-requests/' + rid); chk('신청 조회', c == 200 and d['state'] == 'pending', d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=rid, decision='approve', expectedVersion=1), {'X-Actor': 'approver1'}); chk('승인 결정: 로그인 세션 없음 → 401 UNAUTHENTICATED(X-Actor 라벨로는 승인 불가)', c == 401 and d['code'] == 'UNAUTHENTICATED', (c, d))
c, d = call('GET', '/v1/approval-requests/' + rid); chk('결정 시도 후에도 신청은 pending·rev 1(상태 불변)', d['state'] == 'pending' and d['rev'] == 1 and d['approvalVersion'] == 0, d)
c, d = call('POST', '/v1/permits', dict(requestId=rid), {'X-Actor': 'x'}); chk('permit 발급: 로그인 없이는 401', c == 401 and d['code'] == 'UNAUTHENTICATED', (c, d))
c, d = call('GET', '/v1/limit-accounts'); chk('한도 계정 읽기 전용(현재 계정 없음, 예약 생성 없음)', c == 200 and d['items'] == [], d)
c, d = call('GET', '/v1/approval-requests/zzz'); chk('형식 오류 400', c == 400, d)
rows = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT prevHash, hash, action FROM dbo.ApprovalAudit ORDER BY auditId'), cur.fetchall())[1])
chk('감사 해시 체인 연속 %d행(permit 무인증 시도는 기록 전 차단)' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and {'POLICY_EVALUATE', 'APPROVAL_REQUEST'} <= {r[2] for r in rows}, [r[2] for r in rows])
c, d = call('GET', '/health'); chk('health(모드 표시)', c == 200 and 'propose-only' in d['mode'], d)
AP.R.tx(lambda cur: (AP.R.ex(cur, "INSERT INTO AppUser(userId, username, pwHash, pwSalt, status, isAdmin, mfaEnrolled, mfaLastStep, failCount, createdAt) VALUES ('u-apr','apr','x','y','active',0,1,0,0,'2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES ('g3','u-apr','approve','t','2026-10-31 00:00:00.000')"), AP.R.ex(cur, "INSERT INTO AppSession(tokenHash, userId, mfaVerified, createdAt, expiresAt) VALUES (?, 'u-apr', 1, '2026-10-31 00:00:00.000', '2099-01-01 00:00:00.000')".replace('?', "'" + _hl.sha256(b'tok-apr').hexdigest() + "'"))))
cur_v = call('GET', '/v1/approval-requests/' + rid)[1]; AH = {'Authorization': 'Bearer tok-apr', 'Idempotency-Key': 'd1'}
c, d3 = call('POST', '/v1/approval-decisions', dict(requestId=rid, decision='reject', expectedVersion=cur_v['rev'], reasonSeen='2020-01-01T00:00:00.000Z'), AH); chk('승인자가 본 사유 시각이 다르면 결정 409 REASON_CHANGED(상태 불변)', c == 409 and d3['code'] == 'REASON_CHANGED' and call('GET', '/v1/approval-requests/' + rid)[1]['state'] == 'pending', (c, d3))
c, d3 = call('POST', '/v1/approval-decisions', dict(requestId=rid, decision='reject', expectedVersion=cur_v['rev'], reasonSeen=None), AH); chk('사유가 있는데 본 적 없다고(null) 보내도 409', c == 409 and d3['code'] == 'REASON_CHANGED', (c, d3))
c, d3 = call('POST', '/v1/approval-decisions', dict(requestId=rid, decision='reject', expectedVersion=cur_v['rev'], reasonSeen=cur_v['reasonUpdatedAt']), AH); chk('본 사유 시각이 맞으면 REASON_CHANGED 가드를 통과(이후 처리는 결정 규칙·저장소 몫; 시험 DB에는 결정 표가 없어 503)', d3.get('code') != 'REASON_CHANGED', (c, d3))
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
