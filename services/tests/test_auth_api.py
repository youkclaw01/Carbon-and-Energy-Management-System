import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'approvalapi'))
import approval_app as AP, auth_core as U, base64, time
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE PolicyEvaluation(evaluationId TEXT PRIMARY KEY, country, orgId, principal, idemKey, requestDigest, action, resource, purpose, operationKey, intentDigest, canonicalizationVersion, digestAlgorithmId, amountMinor, currency, decision, reasonCode, policyVersion, proposeOnly, createdAt, expiresAt, UNIQUE(country,orgId,principal,idemKey));
CREATE TABLE ApprovalRequest(intentRef, requestId TEXT PRIMARY KEY, country, orgId, evaluationId, requester, idemKey, requestDigest, operationKey, intentRevision, intentDigest, digestVerified, action, purpose, amountMinor, currency, state, rev, approvalVersion, expiresAt, createdAt, updatedAt, UNIQUE(country,orgId,requester,idemKey));
CREATE TABLE LimitAccount(accountId TEXT PRIMARY KEY, country, orgId, principalScope, action, currency, periodStart, periodEnd, capMinor, heldMinor, settledMinor, rev);
CREATE TABLE LimitReservation(reservationId TEXT PRIMARY KEY, requestId, permitId, accountId, intentDigest, reservedMinor, state, expiresAt, reconciliationVersion, proofRef, rev);
CREATE TABLE ExecutionPermit(permitId TEXT PRIMARY KEY, operationKey, requestId, reservationId, intentDigest, state, useProhibited, operationHold, authorityVersion, createdAt, signature, keyRef, signedDigest, expiresAt, claimedBy, claimedAt);
CREATE TABLE AppUser(userId TEXT PRIMARY KEY, username UNIQUE, pwHash, pwSalt, status, isAdmin, mfaSecretEnc, mfaEnrolled, mfaLastStep, failCount, lockedUntil, createdAt, email, displayName, grade, decidedBy, decidedAt);
CREATE TABLE AppSession(tokenHash TEXT PRIMARY KEY, userId, mfaVerified, createdAt, expiresAt, revokedAt);
CREATE TABLE AppSetting(settingKey TEXT PRIMARY KEY, settingValue, updatedBy, updatedAt);
CREATE TABLE MailOutbox(mailId TEXT PRIMARY KEY, kind, toEmail, subject, body, state, attempts, createdAt, sentAt, lastError);
CREATE TABLE PasskeyCredential(credId TEXT PRIMARY KEY, userId, publicKey, signCount, label, createdAt, lastUsedAt, revokedAt);
CREATE TABLE PasskeyChallenge(challengeHash TEXT PRIMARY KEY, purpose, userId, createdAt, expiresAt, usedAt);
CREATE TABLE UserGrant(grantId TEXT PRIMARY KEY, userId, action, grantedBy, validFrom, validTo, revokedAt);
CREATE TABLE ApprovalDecision(decisionId TEXT PRIMARY KEY, requestId, actor, mfaEvidenceRef, decision, reasonCode, approvalVersion, decidedAt);
CREATE TABLE ApprovalAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
AP.R = Repo('sqlite', cf); srv = make_server(8848, AP.route, AP.health, AP.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8848'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
os.environ['AUTH_DATA_KEY'] = base64.b64encode(os.urandom(32)).decode(); os.environ['BOOTSTRAP_ADMIN_USERNAME'] = 'ama-admin'
PW = 'Correct-Horse-9!'
def cur_code(sec): return U.totp_code(sec, int(time.time() // 30))
# 순수 로직
chk('TOTP RFC6238 시험 벡터(SHA1, 59초 → 94287082의 하위 6자리 287082)', U.totp_code(base64.b32encode(b'12345678901234567890').decode().rstrip('='), 59 // 30) == '287082')
sec0 = U.totp_secret(); st = U.totp_verify(sec0, cur_code(sec0)); chk('TOTP 검증 성공·같은 step 재사용 거절', st is not None and U.totp_verify(sec0, cur_code(sec0), st) is None)
def bad_aad():
    try: U.unseal(os.environ['AUTH_DATA_KEY'], U.seal(os.environ['AUTH_DATA_KEY'], 'abc', 'u1'), 'u2'); return False
    except Exception: return True
chk('MFA 비밀 AES-GCM 봉인: 복호 일치·다른 사용자 AAD면 실패', U.unseal(os.environ['AUTH_DATA_KEY'], U.seal(os.environ['AUTH_DATA_KEY'], 'abc', 'u1'), 'u1') == 'abc' and bad_aad())
# 계정 생성·로그인
c, d = call('POST', '/v1/auth/register', dict(username='Bad Name', password=PW)); chk('잘못된 아이디 400', c == 400 and d['code'] == 'BAD_USERNAME', d)
c, d = call('POST', '/v1/auth/register', dict(username='ama-admin', password='abc1234')); chk('7자 비밀번호 400(최소 8자)', c == 400 and d['code'] == 'WEAK_PASSWORD', d)
c, d = call('POST', '/v1/auth/register', dict(username='ama-admin', password=PW)); chk('계정 생성 201·지정 첫 관리자', c == 201 and d['isAdmin'] is True, d)
c, d = call('POST', '/v1/auth/register', dict(username='ama-admin', password=PW)); chk('아이디 중복 409', c == 409, d)
c, d = call('POST', '/v1/auth/register', dict(username='bob.kim', password=PW)); chk('공개 가입은 닫힘(부트스트랩 아이디 외 403)', c == 403 and d['code'] == 'REGISTRATION_CLOSED', d)
c, d = call('POST', '/v1/admin/users', dict(username='bob.kim', password=PW)); chk('로그인 없이 계정 생성 불가 401', c == 401, d)
rows = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT pwHash, pwSalt FROM AppUser WHERE username=?', ('ama-admin',)), cur.fetchall())[1]); chk('비밀번호 원문은 저장되지 않고 scrypt 해시만 저장', PW not in rows[0][0] and len(rows[0][0]) > 40)
c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password='wrong-password-1')); chk('틀린 비밀번호 401(계정 존재 여부 미노출)', c == 401 and d['code'] == 'INVALID_CREDENTIALS', d)
c, d = call('POST', '/v1/auth/login', dict(username='nobody', password='wrong-password-1')); chk('없는 아이디도 같은 401', c == 401 and d['code'] == 'INVALID_CREDENTIALS', d)
c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password=PW)); tok = d.get('token'); H = {'Authorization': 'Bearer ' + str(tok)}
chk('로그인 200: MFA 미등록 세션(mfaVerified false)', c == 200 and d['mfaVerified'] is False and d['mfaEnrolled'] is False, d)
c, d = call('GET', '/v1/auth/me', None, H); chk('me: 권한 admin 보유', c == 200 and 'admin' in d['grants'], d)
c, d = call('GET', '/v1/auth/me'); chk('토큰 없으면 401', c == 401, d)
c, d = call('POST', '/v1/admin/grants', dict(username='bob.kim', action='approve'), H); chk('MFA 미완료 세션은 관리 작업 403 MFA_REQUIRED', c == 403 and d['code'] == 'MFA_REQUIRED', d)
# MFA 등록
c, d = call('POST', '/v1/auth/mfa/confirm', dict(code='123456'), H); chk('enroll 전 confirm 409', c == 409 and d['code'] == 'MFA_NOT_STARTED', d)
c, d = call('POST', '/v1/auth/mfa/enroll', None, H); sec = d.get('secret'); chk('MFA 등록 시작: 비밀·otpauth URI 반환', c == 200 and sec and d['otpauthUri'].startswith('otpauth://totp/AMA:ama-admin'), d)
enc = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT mfaSecretEnc FROM AppUser WHERE username=?', ('ama-admin',)), cur.fetchall()[0][0])[1]); chk('MFA 비밀은 암호화 저장(평문 아님)', enc and sec not in enc)
c, d = call('POST', '/v1/auth/mfa/confirm', dict(code='000000'), H); chk('틀린 코드로 확정 불가 400', c == 400 and d['code'] == 'INVALID_MFA', d)
c, d = call('POST', '/v1/auth/mfa/confirm', dict(code=cur_code(sec)), H); chk('올바른 코드로 MFA 등록 완료·세션 MFA 검증됨', c == 200 and d['mfaEnrolled'] and d['mfaVerified'], d)
c, d = call('POST', '/v1/auth/mfa/enroll', None, H); chk('등록 후 재등록 409', c == 409, d)
# MFA 로그인(코드 재사용 방지: 등록에 쓴 step은 재사용 불가 → 다음 step 코드 사용)
c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password=PW)); chk('MFA 등록 후 코드 없이 로그인 401 MFA_REQUIRED', c == 401 and d['code'] == 'MFA_REQUIRED', d)
c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password=PW, totp=cur_code(sec))); chk('등록에 쓴 코드는 재사용 거절(재생 방지)', c == 401 and d['code'] == 'INVALID_MFA', d)
nxt = U.totp_code(sec, int(time.time() // 30) + 1)
c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password=PW, totp=nxt)); tok2 = d.get('token'); H2 = {'Authorization': 'Bearer ' + str(tok2)}; chk('MFA 로그인 200·mfaVerified true', c == 200 and d['mfaVerified'] is True, d)
# 권한 부여와 승인
c, d = call('POST', '/v1/admin/users', dict(username='bob.kim', password=PW), H2); chk('관리자(MFA 세션)가 일반 계정 생성 201·권한 없음', c == 201 and d['isAdmin'] is False, d)
c, d = call('POST', '/v1/auth/password', dict(currentPassword='bad', newPassword='New-Password-77!'), H2); chk('현재 비밀번호 틀리면 변경 불가 401', c == 401, d)
c, d = call('POST', '/v1/auth/password', dict(currentPassword=PW, newPassword='New-Password-77!'), H2); chk('비밀번호 변경 200', c == 200, d)
PW0 = PW; PW = 'New-Password-77!'; c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password=PW0, totp=U.totp_code(sec, int(time.time() // 30) + 2))); chk('이전 비밀번호로 로그인 불가', c == 401, d)
PW = PW0
c, d = call('POST', '/v1/admin/grants', dict(username='bob.kim', action='approve'), H2); chk('관리자가 bob에게 approve 부여', c == 200, d)
c, d = call('POST', '/v1/admin/grants', dict(username='ama-admin', action='approve'), H2); chk('자기 자신에게 approve 부여 거절(직무 분리)', c == 403 and d['code'] == 'SEPARATION_OF_DUTY', d)
c, d = call('POST', '/v1/auth/login', dict(username='bob.kim', password=PW)); Hb = {'Authorization': 'Bearer ' + d['token']}
c, d = call('POST', '/v1/admin/grants', dict(username='bob.kim', action='admin'), Hb); chk('일반 사용자는 관리 작업 불가(MFA 세션 아님 → 403)', c == 403, d)
RID = str(uuid.uuid4()); t = '2026-10-31 00:00:00.000'
AP.R.tx(lambda cur: (AP.R.ex(cur, "INSERT INTO PolicyEvaluation(evaluationId, country, orgId, principal, idemKey, requestDigest) VALUES ('e1','KR','AMA-KR','p','k','d')") if False else None))
AP.R.tx(lambda cur: AP.R.ex(cur, "INSERT INTO ApprovalRequest(requestId, country, orgId, evaluationId, requester, state, rev, digestVerified, approvalVersion) VALUES (?,?,?,?,?,?,?,?,?)", (RID, 'KR', 'AMA-KR', 'e1', 'ama-admin', 'pending', 1, 1, 0)))
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID, decision='approve', expectedVersion=1), H2); chk('승인 권한 없는 관리자는 403 FORBIDDEN', c == 403 and d['code'] == 'FORBIDDEN', d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID, decision='approve', expectedVersion=1), Hb); chk('MFA 미등록 세션의 승인은 403 MFA_REQUIRED', c == 403 and d['code'] == 'MFA_REQUIRED', d)
# bob이 MFA 등록 후 승인: 성공(approved·approvalVersion 1)·신청자≠승인자·CAS 충돌
c, d = call('POST', '/v1/auth/mfa/enroll', None, Hb); sb = d['secret']; c, d = call('POST', '/v1/auth/mfa/confirm', dict(code=cur_code(sb)), Hb); chk('bob MFA 등록 완료', c == 200, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID, decision='approve', expectedVersion=9), Hb); chk('expectedVersion 불일치 409 VERSION_CONFLICT', c == 409 and d['code'] == 'VERSION_CONFLICT', d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID, decision='approve', expectedVersion=1), Hb); chk('MFA 세션·approve 권한·digest 재검증 → 승인 200(approved, approvalVersion 1)', c == 200 and d['state'] == 'approved' and d['approvalVersion'] == 1, d)
n = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT COUNT(*) FROM ApprovalDecision WHERE requestId=?', (RID,)), cur.fetchall()[0][0])[1]); chk('승인 기록 1건·감사 기록', n == 1)
RID2 = str(uuid.uuid4()); AP.R.tx(lambda cur: AP.R.ex(cur, "INSERT INTO ApprovalRequest(requestId, country, orgId, evaluationId, requester, state, rev, digestVerified, approvalVersion) VALUES (?,?,?,?,?,?,?,?,?)", (RID2, 'KR', 'AMA-KR', 'e1', 'bob.kim', 'pending', 1, 1, 0)))
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID2, decision='approve', expectedVersion=1), Hb); chk('신청자 본인은 승인 불가 403 SEPARATION_OF_DUTY', c == 403 and d['code'] == 'SEPARATION_OF_DUTY', d)
RID3 = str(uuid.uuid4()); AP.R.tx(lambda cur: AP.R.ex(cur, "INSERT INTO ApprovalRequest(requestId, country, orgId, evaluationId, requester, state, rev, digestVerified, approvalVersion) VALUES (?,?,?,?,?,?,?,?,?)", (RID3, 'KR', 'AMA-KR', 'e1', 'ama-admin', 'pending', 1, 0, 0)))
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RID3, decision='approve', expectedVersion=1), Hb); chk('digest 미재검증이면 승인 불가 503 BLOCKED_DEPENDENCY', c == 503 and d['code'] == 'BLOCKED_DEPENDENCY', d)
# 잠금
for i in range(5): c, d = call('POST', '/v1/auth/login', dict(username='bob.kim', password='wrong-password-%d' % i))
c, d = call('POST', '/v1/auth/login', dict(username='bob.kim', password=PW)); chk('5회 실패 후 올바른 비밀번호도 423 잠금', c == 423 and d['code'] == 'ACCOUNT_LOCKED', d)
# 로그아웃
c, d = call('POST', '/v1/auth/logout', None, H2); c, d = call('GET', '/v1/auth/me', None, H2); chk('로그아웃 후 토큰 401', c == 401, d)
# ---- 가입 신청·관리자 결정·등급·메일 ----
# admin(H2는 로그아웃됨) 재로그인
for _ in range(1): 
    AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE AppUser SET mfaLastStep=0 WHERE username='ama-admin'"))   # 시험용: 30초 대기 없이 새 코드 사용
    c, d = call('POST', '/v1/auth/login', dict(username='ama-admin', password='New-Password-77!', totp=cur_code(sec))); chk('관리자 재로그인(MFA, 변경된 비밀번호)', c == 200 and d['mfaVerified'], d); HA = {'Authorization': 'Bearer ' + str(d.get('token'))}
c, d = call('POST', '/v1/auth/signup', dict(username='carol', password=PW, email='bad')); chk('가입: 이메일 형식 오류 400', c == 400 and d['code'] == 'BAD_EMAIL', d)
c, d = call('POST', '/v1/auth/signup', dict(username='carol', password=PW, email='carol@example.com', displayName='캐럴')); chk('가입 신청 202 pending(관리자 이메일 미등록 → 알림 없음)', c == 202 and d['state'] == 'pending' and d['adminNotified'] is False, d)
c, d = call('POST', '/v1/auth/signup', dict(username='carol', password=PW, email='carol@example.com')); chk('가입 아이디 중복 409', c == 409, d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password=PW)); chk('승인 전 로그인 403 ACCOUNT_PENDING(권한·세션 없음)', c == 403 and d['code'] == 'ACCOUNT_PENDING', d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password='wrong-password-9')); chk('승인 전에도 틀린 비밀번호는 401(상태 미노출)', c == 401, d)
c, d = call('POST', '/v1/admin/settings/notify-email', dict(emails=['not-an-email']), HA); chk('관리자 이메일 형식 오류 400', c == 400, d)
c, d = call('POST', '/v1/admin/settings/notify-email', dict(emails=['admin@example.com', 'admin@example.com']), HA); chk('관리자 알림 이메일 등록(소문자·중복 제거)', c == 200 and d['emails'] == ['admin@example.com'], d)
c, d = call('GET', '/v1/admin/settings/notify-email', None, HA); chk('알림 이메일 조회', d['emails'] == ['admin@example.com'], d)
c, d = call('POST', '/v1/auth/signup', dict(username='dave', password=PW, email='dave@example.com')); chk('가입 신청 시 관리자 알림 큐 적재', c == 202 and d['adminNotified'] is True, d)
mails = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT toEmail, subject, body, state FROM MailOutbox'), cur.fetchall())[1]); chk('MailOutbox: 관리자에게 승인 요청 메일(비밀 미포함)', len(mails) == 1 and mails[0][0] == 'admin@example.com' and 'dave' in mails[0][1] and PW not in mails[0][2] and mails[0][3] == 'pending', mails)
c, d = call('GET', '/v1/admin/signups', None, HA); chk('관리자: 대기 목록에 carol·dave', c == 200 and {x['username'] for x in d['items']} == {'carol', 'dave'}, d)
c, d = call('GET', '/v1/admin/signups', None, Hb); chk('일반 사용자는 목록 불가 403', c in (401, 403), d)
c, d = call('POST', '/v1/admin/signups/decision', dict(username='carol', decision='approve', grade='superuser'), HA); chk('잘못된 등급 400', c == 400 and d['code'] == 'BAD_GRADE', d)
c, d = call('POST', '/v1/admin/signups/decision', dict(username='carol', decision='approve', grade='approver'), HA); chk('관리자가 carol을 approver 등급으로 승인', c == 200 and d['state'] == 'active' and d['grade'] == 'approver', d)
c, d = call('POST', '/v1/admin/signups/decision', dict(username='dave', decision='reject'), HA); chk('dave 거절', c == 200 and d['state'] == 'rejected', d)
c, d = call('POST', '/v1/admin/signups/decision', dict(username='carol', decision='reject'), HA); chk('이미 처리된 신청 409', c == 409, d)
c, d = call('POST', '/v1/auth/login', dict(username='dave', password=PW)); chk('거절된 계정 로그인 403 ACCOUNT_REJECTED', c == 403 and d['code'] == 'ACCOUNT_REJECTED', d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password=PW)); Hc = {'Authorization': 'Bearer ' + str(d.get('token'))}; chk('승인된 carol 로그인 200(MFA 미등록)', c == 200, d)
c, d = call('GET', '/v1/auth/me', None, Hc); chk('carol 권한 = request+approve(등급 approver)', sorted(d['grants']) == ['approve', 'request'], d)
c, d = call('POST', '/v1/admin/users/grade', dict(username='carol', grade='viewer'), HA); chk('등급 변경 viewer → 권한 회수', c == 200, d); c, d = call('GET', '/v1/auth/me', None, Hc); chk('변경 후 권한 없음', d['grants'] == [], d)
c, d = call('POST', '/v1/admin/users/grade', dict(username='ama-admin', grade='viewer'), HA); chk('자기 등급 변경 거절', c == 403, d)
sent = []; AP.MAILER = lambda to, sub, body: sent.append((to, sub))
n = AP.deliver_mail(); st = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT state, COUNT(*) FROM MailOutbox GROUP BY state'), cur.fetchall())[1]); chk('발송기 주입 시 대기 메일 발송·sent 기록', n >= 2 and dict(st).get('sent', 0) >= 2 and ('admin@example.com', mails[0][1]) in sent, (n, st))
AP.MAILER = lambda to, sub, body: (_ for _ in ()).throw(RuntimeError('boom')); AP.R.tx(lambda cur: AP.R.ex(cur, "INSERT INTO MailOutbox(mailId, kind, toEmail, subject, body, state, attempts, createdAt) VALUES ('m9','X','a@b.co','s','b','pending',4,'2026-10-31 00:00:00.000')")); AP.deliver_mail()
chk('발송 5회 실패 → failed(무한 재시도 없음)', AP.R.tx(lambda cur: (AP.R.ex(cur, "SELECT state FROM MailOutbox WHERE mailId='m9'"), cur.fetchall()[0][0])[1]) == 'failed')
# SMTP 제출 계약: 가짜 SMTP 서버(AUTH PLAIN, STARTTLS 없음)로 실제 smtplib 경로 확인
import socket, threading
got = []
def fake_smtp(srv):
    c, _ = srv.accept(); f = c.makefile('rwb'); w = lambda s: (f.write((s + '\r\n').encode()), f.flush())
    w('220 fake ESMTP'); data = False; buf = []
    while True:
        l = f.readline()
        if not l: break
        l = l.decode().rstrip('\r\n')
        if data:
            if l == '.': data = False; got.append('\n'.join(buf)); w('250 queued')
            else: buf.append(l)
        elif l.upper().startswith('EHLO'): w('250-fake'); w('250 AUTH PLAIN')
        elif l.upper().startswith('AUTH'): got.append('AUTH'); w('235 ok')
        elif l.upper().startswith('DATA'): data = True; w('354 go')
        elif l.upper().startswith('QUIT'): w('221 bye'); break
        else: w('250 ok')
srv = socket.socket(); srv.bind(('127.0.0.1', 0)); srv.listen(1); th = threading.Thread(target=fake_smtp, args=(srv,)); th.start()
os.environ.update(SMTP_HOST='127.0.0.1', SMTP_PORT=str(srv.getsockname()[1]), SMTP_FROM='noreply@example.com', SMTP_STARTTLS='0', SMTP_USER='noreply@example.com', SMTP_PASSWORD='x')
AP.send_smtp('admin@example.com', '[AMA] 시험', '본문'); th.join(5)
chk('SMTP 제출: 인증·발신 example.com·수신자·제목 전달', 'AUTH' in got and any('From: noreply@example.com' in g and 'To: admin@example.com' in g for g in got if g != 'AUTH'), got)
chk('SMTP 설정 시 발송기 준비됨(mailer_ready)', AP.mailer_ready())
# ---- 계정 관리·내 정보 ----
c, d = call('GET', '/v1/admin/users', None, HA); chk('관리자: 전체 사용자 목록', c == 200 and {'ama-admin', 'bob.kim', 'carol', 'dave'} <= {x['username'] for x in d['items']} and all('mfaEnrolled' in x for x in d['items']), d)
c, d = call('GET', '/v1/admin/users', None, Hc); chk('일반 사용자는 목록 불가', c in (401, 403), d)
c, d = call('POST', '/v1/auth/profile', dict(email='x'), Hc); chk('내 정보: 이메일 형식 오류 400', c == 400, d)
c, d = call('POST', '/v1/auth/profile', dict(email='Carol@Example.com'), Hc); chk('내 정보: 본인 이메일 그대로는 허용', c == 200 and d['email'] == 'carol@example.com', d)
c, d = call('POST', '/v1/auth/profile', dict(email='bob@example.com', displayName='캐럴 김'), Hc); chk('내 정보 수정(이메일·이름)', c == 200 and d['email'] == 'bob@example.com' and d['displayName'] == '캐럴 김', d)
c, d = call('POST', '/v1/auth/signup', dict(username='erin', password=PW, email='BOB@example.com')); chk('가입 이메일 중복 409', c == 409 and d['code'] == 'EMAIL_TAKEN', d)
c, d = call('POST', '/v1/admin/users/status', dict(username='carol', status='disabled'), HA); chk('관리자가 carol 비활성화', c == 200, d)
c, d = call('GET', '/v1/auth/me', None, Hc); chk('비활성화하면 기존 세션 즉시 무효(401)', c == 401, d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password=PW)); chk('비활성 계정 로그인 불가(401, 상태 미노출)', c == 401, d)
c, d = call('POST', '/v1/admin/users/status', dict(username='carol', status='active'), HA); chk('재활성화', c == 200, d)
c, d = call('POST', '/v1/admin/users/status', dict(username='ama-admin', status='disabled'), HA); chk('자기 계정은 비활성화 불가', c == 403, d)
c, d = call('POST', '/v1/admin/users/status', dict(username='dave', status='active'), HA); chk('거절된 가입자는 이 화면에서 활성화 불가(가입 승인 경로만)', c == 409, d)
c, d = call('POST', '/v1/admin/users/reset-password', dict(username='carol'), HA); tmp = d.get('temporaryPassword'); chk('임시 비밀번호 재설정: 14자·혼동 글자 없음·한 번만 표시', c == 200 and tmp and len(tmp) == 14 and not set('lIO') & set(tmp), d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password=PW)); chk('이전 비밀번호 로그인 불가', c == 401, d)
c, d = call('POST', '/v1/auth/login', dict(username='carol', password=tmp)); chk('임시 비밀번호로 로그인', c == 200, d); Hc2 = {'Authorization': 'Bearer ' + str(d.get('token'))}
c, d = call('POST', '/v1/admin/users/reset-mfa', dict(username='bob.kim'), HA); chk('bob MFA 초기화', c == 200, d)
c, d = call('POST', '/v1/auth/login', dict(username='bob.kim', password=PW)); chk('MFA 초기화 후 코드 없이 로그인(재등록 가능 상태)', c == 200 and d['mfaEnrolled'] is False and d['mfaVerified'] is False, d)
# ---- 패스키(지문): 가상 인증기로 실제 검증 경로 시험 ----
import hashlib, struct, json as J
from cryptography.hazmat.primitives.asymmetric import ec as EC
from cryptography.hazmat.primitives import hashes as HS
import webauthn_core as W
def cb(o):
    if isinstance(o, int): return bytes([0x00 | o]) if 0 <= o < 24 else (bytes([0x18, o]) if 0 <= o < 256 else (bytes([0x38, -1 - o]) if -256 <= o < 0 and o < -24 else bytes([0x20 | (-1 - o)])))
    if isinstance(o, bytes): return (bytes([0x40 | len(o)]) if len(o) < 24 else bytes([0x58, len(o)])) + o
    if isinstance(o, str): e = o.encode(); return (bytes([0x60 | len(e)]) if len(e) < 24 else bytes([0x78, len(e)])) + e
    if isinstance(o, dict): return bytes([0xa0 | len(o)]) + b''.join(cb(k) + cb(v) for k, v in o.items())
RP = 'ama.example.com'; ORG = 'https://ama.example.com'; os.environ['WEBAUTHN_RP_ID'] = RP; os.environ['WEBAUTHN_ORIGINS'] = ORG
class Authn:
    def __init__(self): self.k = EC.generate_private_key(EC.SECP256R1()); self.cid = os.urandom(16); self.count = 0
    def reg(self, ch, uv=True, origin=ORG, rp=RP):
        n = self.k.public_key().public_numbers(); cose = {1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, 'big'), -3: n.y.to_bytes(32, 'big')}
        ad = hashlib.sha256(rp.encode()).digest() + bytes([0x41 | (0x04 if uv else 0)]) + struct.pack('>I', 0) + b'\0' * 16 + struct.pack('>H', len(self.cid)) + self.cid + cb(cose)
        cd = J.dumps(dict(type='webauthn.create', challenge=ch, origin=origin)).encode(); return dict(id=W.b64u(self.cid), response=dict(clientDataJSON=W.b64u(cd), attestationObject=W.b64u(cb(dict(fmt='none', attStmt={}, authData=ad)))))
    def get(self, ch, uv=True, origin=ORG, bump=True, key=None):
        if bump: self.count += 1
        ad = hashlib.sha256(RP.encode()).digest() + bytes([0x01 | (0x04 if uv else 0)]) + struct.pack('>I', self.count); cd = J.dumps(dict(type='webauthn.get', challenge=ch, origin=origin)).encode()
        sig = (key or self.k).sign(ad + hashlib.sha256(cd).digest(), EC.ECDSA(HS.SHA256())); return dict(id=W.b64u(self.cid), response=dict(clientDataJSON=W.b64u(cd), authenticatorData=W.b64u(ad), signature=W.b64u(sig), userHandle=''))
dev = Authn()
c, d = call('POST', '/v1/auth/passkey/register/options', None, Hc2); chk('패스키 등록은 MFA 세션에서만(비밀번호만 아는 세션 403)', c == 403 and d['code'] == 'MFA_REQUIRED', d)
c, d = call('POST', '/v1/auth/passkey/register/options', None, HA); pk = d['publicKey']; chk('등록 옵션: 플랫폼 인증기·UV 필수·상주 키·rpId', c == 200 and pk['authenticatorSelection']['userVerification'] == 'required' and pk['authenticatorSelection']['authenticatorAttachment'] == 'platform' and pk['rp']['id'] == RP, d)
badreg = dev.reg(pk['challenge'], uv=False); c, d = call('POST', '/v1/auth/passkey/register/verify', badreg, HA); chk('지문(UV) 없이 만든 등록은 거절', c == 400 and d['code'] == 'UV_REQUIRED', d)
c, d = call('POST', '/v1/auth/passkey/register/options', None, HA); pk = d['publicKey']
c, d = call('POST', '/v1/auth/passkey/register/verify', dev.reg(pk['challenge'], origin='https://evil.example'), HA); chk('다른 origin 등록 거절', c == 400 and d['code'] == 'BAD_ORIGIN', d)
c, d = call('POST', '/v1/auth/passkey/register/options', None, HA); pk = d['publicKey']; reg = dev.reg(pk['challenge'])
c, d = call('POST', '/v1/auth/passkey/register/verify', dict(reg, label='내 폰'), HA); chk('패스키 등록 성공', c == 200 and d['registered'], d)
c, d = call('POST', '/v1/auth/passkey/register/verify', dict(reg, label='again'), HA); chk('같은 챌린지 재사용 거절(1회용)', c == 400 and d['code'] == 'BAD_CHALLENGE', d)
c, d = call('GET', '/v1/auth/passkeys', None, HA); chk('등록된 패스키 목록', len(d['items']) == 1 and d['items'][0]['label'] == '내 폰', d)
c, d = call('POST', '/v1/auth/passkey/login/options', {}); ch = d['publicKey']['challenge']; chk('로그인 옵션: UV 필수·상주 키(allowCredentials 비움)', c == 200 and d['publicKey']['userVerification'] == 'required' and d['publicKey']['allowCredentials'] == [], d)
c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(ch)); chk('지문 로그인 성공 → MFA 검증된 세션', c == 200 and d['username'] == 'ama-admin' and d['mfaVerified'] is True, d); HP = {'Authorization': 'Bearer ' + str(d.get('token'))}
c, d = call('GET', '/v1/auth/me', None, HP); chk('패스키 세션으로 관리자 기능 사용 가능', c == 200 and 'admin' in d['grants'], d)
c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(ch)); chk('같은 챌린지 재사용(재생) 거절', c == 400 and d['code'] == 'BAD_CHALLENGE', d)
c, d = call('POST', '/v1/auth/passkey/login/options', {}); ch = d['publicKey']['challenge']; c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(ch, uv=False)); chk('UV 없는 서명 거절', c == 401 and d['code'] == 'UV_REQUIRED', d)
c, d = call('POST', '/v1/auth/passkey/login/options', {}); ch = d['publicKey']['challenge']; c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(ch, key=EC.generate_private_key(EC.SECP256R1()))); chk('다른 키로 만든 서명 거절', c == 401 and d['code'] == 'BAD_SIGNATURE', d)
c, d = call('POST', '/v1/auth/passkey/login/options', {}); ch = d['publicKey']['challenge']; dev.count = 1; c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(ch, bump=False)); chk('서명 카운터가 늘지 않으면 복제 의심으로 거절', c == 401 and d['code'] == 'CLONED_AUTHENTICATOR', d)
c, d = call('POST', '/v1/auth/passkey/login/options', {}); ch = d['publicKey']['challenge']; c, d = call('POST', '/v1/auth/passkey/login/verify', Authn().get(ch)); chk('등록되지 않은 패스키 401', c == 401, d)
dev.count = 50; c, d = call('POST', '/v1/auth/passkey/delete', dict(id=W.b64u(dev.cid)), HA); c, d2 = call('POST', '/v1/auth/passkey/login/options', {}); c, d = call('POST', '/v1/auth/passkey/login/verify', dev.get(d2['publicKey']['challenge'])); chk('삭제한 패스키로는 로그인 불가', c == 401, d)
# ---- 승인 경로 종단: 로그인한 신청자 → S04 digest 재검증 → MFA 승인자 ----
def mk_user(un, grade, mfa):
    c, d = call('POST', '/v1/admin/users', dict(username=un, password=PW, email=un + '@example.com'), HA); assert c == 201, d
    c, d = call('POST', '/v1/admin/users/grade', dict(username=un, grade=grade), HA); assert c == 200, d
    c, d = call('POST', '/v1/auth/login', dict(username=un, password=PW)); h = {'Authorization': 'Bearer ' + d['token']}
    if mfa:
        c, d = call('POST', '/v1/auth/mfa/enroll', None, h); c, d = call('POST', '/v1/auth/mfa/confirm', dict(code=cur_code(d['secret'])), h); assert c == 200, d
    return h
Hf = mk_user('frank', 'operator', False); Hg = mk_user('gina', 'approver', True); Hv = mk_user('vera', 'viewer', False)
D1 = 'c' * 64; EVB = dict(action='procurement.rec.purchase', resource='REC', purpose='HEDGE', operationKey='KR|AMA-KR|S04|op-9', intentDigest=D1, canonicalizationVersion='ama.intent.v1/jcs-1', digestAlgorithmId='sha256', amount=dict(value='1000000', currency='KRW'))
c, d = call('POST', '/v1/policy-evaluations', EVB, {'Idempotency-Key': 'ev-chain', 'X-Actor': 'frank'}); EID = d['evaluationId']
REFB = dict(evaluationId=EID, intentRevision=1, intentDigest=D1, intentRef=dict(intentId=str(uuid.uuid4()), intentVersion=1))
c, d = call('POST', '/v1/approval-requests', REFB, {'Idempotency-Key': 'rq0'}); chk('로그인 없이 승인 신청 불가 401(X-Actor 라벨 위장 차단)', c == 401, d)
c, d = call('POST', '/v1/approval-requests', REFB, {'Idempotency-Key': 'rq0', 'Authorization': Hv['Authorization']}); chk('request 권한 없는 사용자(viewer)는 승인 신청 403', c == 403, d)
calls = []
AP.VERIFY = lambda ref, dg: (calls.append((ref, dg)), True)[1]
c, d = call('POST', '/v1/approval-requests', REFB, {'Idempotency-Key': 'rq1', 'Authorization': Hf['Authorization']}); R1 = d.get('requestId'); chk('신청 201: 신청자는 로그인 사용자(frank)·S04 재검증 통과(digestVerified true)', c == 201 and d['digestVerified'] is True and d['state'] == 'pending' and calls and calls[0][1] == D1, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=R1, decision='approve', expectedVersion=1), Hf); chk('신청자 본인은 승인 불가(권한 없음 403)', c == 403, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=R1, decision='approve', expectedVersion=1), Hg); chk('MFA 승인자 gina 승인 200(approved)·승인 직전 S04 재조회 수행', c == 200 and d['state'] == 'approved' and len(calls) >= 2, d)
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=2), {'Idempotency-Key': 'rq2', 'Authorization': Hf['Authorization']}); R2 = d['requestId']
AP.VERIFY = lambda ref, dg: False
c, d = call('POST', '/v1/approval-decisions', dict(requestId=R2, decision='approve', expectedVersion=1), Hg); chk('승인 직전 intent가 바뀌었거나 조회 실패 → 승인 불가 503 BLOCKED_DEPENDENCY', c == 503 and d['code'] == 'BLOCKED_DEPENDENCY', d)
dvf = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT digestVerified FROM ApprovalRequest WHERE requestId=?', (R2,)), cur.fetchall()[0][0])[1]); chk('재검증 실패는 digestVerified를 0으로 되돌림', dvf == 0, dvf)
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=3), {'Idempotency-Key': 'rq3', 'Authorization': Hf['Authorization']}); chk('생성 시 S04 재검증 실패 → digestVerified false(닫힘)', c == 201 and d['digestVerified'] is False, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=R2, decision='reject', expectedVersion=1), Hg); chk('재검증 실패여도 거절은 가능', c == 200 and d['state'] == 'rejected', d)
# 실제 verify_intent: 가짜 S04 서버로 확인(digest·규약·최신 버전·상태)
import http.server
S04 = {}
class H4(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        b = json.dumps(S04['r']).encode(); self.send_response(S04.get('code', 200)); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
s4 = http.server.HTTPServer(('127.0.0.1', 0), H4); threading.Thread(target=s4.serve_forever, daemon=True).start(); os.environ['PROC_API_URL'] = 'http://127.0.0.1:%d' % s4.server_address[1]
ref = dict(intentId=str(uuid.uuid4()), intentVersion=2); good = dict(bindingState='BOUND', mode='SIMULATED', intentDigest=D1, canonicalizationVersion='ama.intent.v1/jcs-1', digestAlgorithmId='sha256', latestVersion=2)
S04['r'] = good; chk('verify_intent: 모든 조건 일치 → True', AP.verify_intent(ref, D1) is True)
S04['r'] = dict(good, intentDigest='d' * 64); chk('digest 불일치 → False', AP.verify_intent(ref, D1) is False)
S04['r'] = dict(good, latestVersion=3); chk('더 새 버전이 있으면(대체됨) → False', AP.verify_intent(ref, D1) is False)
S04['r'] = dict(good, canonicalizationVersion='v0'); chk('규약 버전 다름 → False', AP.verify_intent(ref, D1) is False)
S04['r'] = dict(good, bindingState='UNRESOLVED'); chk('BOUND 아님 → False', AP.verify_intent(ref, D1) is False)
S04['r'] = good; S04['code'] = 404; chk('S04 오류 응답 → False(닫힘)', AP.verify_intent(ref, D1) is False); S04['code'] = 200
del os.environ['PROC_API_URL']; chk('PROC_API_URL 미설정 → False(닫힘)', AP.verify_intent(ref, D1) is False)
# ---- permit 발급·서명(S07-P2) ----
class MockKv2:
    alg = 'ES256'; kid = 'https://kv/keys/permit-sign-kr01/v9'; key = 'https://kv/keys/permit-sign-kr01'
    def __init__(self): self.k = EC.generate_private_key(EC.SECP256R1()); self.fail = None; self.lie = False
    def sign(self, dg):
        if self.fail: raise RuntimeError('lost')
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed, decode_dss_signature
        r, s_ = decode_dss_signature(self.k.sign(bytes.fromhex(dg), EC.ECDSA(Prehashed(HS.SHA256())))); return W.b64u(r.to_bytes(32, 'big') + s_.to_bytes(32, 'big')), self.kid
    def verify(self, dg, sig, kid):
        if self.lie: return False
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed, encode_dss_signature
        raw = W.unb64u(sig)
        try: self.k.public_key().verify(encode_dss_signature(int.from_bytes(raw[:32], 'big'), int.from_bytes(raw[32:], 'big')), bytes.fromhex(dg), EC.ECDSA(Prehashed(HS.SHA256()))); return True
        except Exception: return False
kv = MockKv2(); Hi = mk_user('ivan', 'admin', True)
now_ = dt.datetime.utcnow() if False else __import__('datetime').datetime.utcnow(); P0 = (now_ - __import__('datetime').timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S'); P1 = (now_ + __import__('datetime').timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S')
c, d = call('POST', '/v1/admin/limit-accounts', dict(principalScope='KR-01', action='procurement.rec.purchase', currency='KRW', capMinor=5000000, periodStart=P0, periodEnd=P1), Hf); chk('한도 계정 생성은 관리자만(operator 403)', c == 403, d)
c, d = call('POST', '/v1/admin/limit-accounts', dict(principalScope='KR-01', action='procurement.rec.purchase', currency='KRW', capMinor=5000000, periodStart=P0, periodEnd=P1), Hi); ACC = d.get('accountId'); chk('한도 계정 생성(KRW 5,000,000)', c == 201, d)
c, d = call('POST', '/v1/admin/limit-accounts', dict(principalScope='KR-01', action='x', currency='KRW', capMinor=-1, periodStart=P0, periodEnd=P1), Hi); chk('음수 한도 400', c == 400, d)
AP.SIGNER_FACTORY = lambda: None; AP.VERIFY = lambda ref, dg: True
PB = dict(requestId=R1, accountId=ACC, expectedApprovalVersion=1)
c, d = call('POST', '/v1/permits', PB, Hi); chk('서명 키 미구성 → 422·한도 예약 없음', c == 422 and d['code'] == 'PERMIT_ISSUANCE_BLOCKED', d)
held0 = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT heldMinor FROM LimitAccount WHERE accountId=?', (ACC,)), cur.fetchall()[0][0])[1]); chk('미구성 거절 시 held 0', held0 == 0, held0)
AP.SIGNER_FACTORY = lambda: kv
c, d = call('POST', '/v1/permits', PB, Hf); chk('permit.issue 권한 없는 사용자(operator)는 403', c == 403, d)
c, d = call('POST', '/v1/permits', dict(PB, requestId=R2), Hi); chk('승인되지 않은(거절된) 신청은 발급 불가 409', c == 409 and d['code'] == 'NOT_APPROVED', d)
c, d = call('POST', '/v1/permits', dict(PB, expectedApprovalVersion=7), Hi); chk('승인 버전 불일치 409', c == 409 and d['code'] == 'NOT_APPROVED', d)
AP.VERIFY = lambda ref, dg: False; c, d = call('POST', '/v1/permits', PB, Hi); chk('발급 직전 S04 재검증 실패 → 503·예약 없음', c == 503 and d['code'] == 'BLOCKED_DEPENDENCY', d); AP.VERIFY = lambda ref, dg: True
held1 = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT heldMinor FROM LimitAccount WHERE accountId=?', (ACC,)), cur.fetchall()[0][0])[1]); chk('실패한 발급은 한도를 건드리지 않음', held1 == 0)
c, d = call('POST', '/v1/permits', PB, Hi); PID = d.get('permitId'); chk('permit 발급 201: active·서명·keyRef(버전)·외부 허가 아님 안내', c == 201 and d['state'] == 'active' and d['algorithm'] == 'ES256' and d['keyRef'].endswith('/v9') and len(d['signature']) > 60, d)
held2 = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT heldMinor, rev FROM LimitAccount WHERE accountId=?', (ACC,)), cur.fetchall()[0])[1]); chk('한도 held 1,000,000 증가·rev 증가', held2[0] == 1000000 and held2[1] == 2, held2)
rr = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT state, reservedMinor, permitId FROM LimitReservation WHERE requestId=?', (R1,)), cur.fetchall())[1]); chk('예약 1건(held·1,000,000·permit 결속)', rr == [('held', 1000000, PID)], rr)
c, g = call('GET', '/v1/permits/' + PID, None, Hf)
payload = dict(permitId=PID, requestId=R1, operationKey=g['operationKey'], intentDigest=g['intentDigest'], approvalVersion=1, authorityVersion=1, reservationId=g['reservationId'], amountMinor=1000000, currency='KRW', expiresAt=g['expiresAt'])
chk('GET permit(S08 소비용 조회): 서명 digest가 payload 재계산과 일치', c == 200 and g['state'] == 'active' and g['useProhibited'] is False and g['signedDigest'] == AP.permit_payload(payload) and kv.verify(g['signedDigest'], g['signature'], g['keyRef']), (c, g))
c, d = call('POST', '/v1/permits', PB, Hi); chk('같은 신청 재발급 거절 409 PERMIT_EXISTS(한도 이중 예약 없음)', c == 409 and d['code'] == 'PERMIT_EXISTS', d)
c, d = call('GET', '/v1/permits/' + PID); chk('permit 조회도 로그인 필요 401', c == 401, d)
VP = dict(payload, signature=g['signature'], keyRef=g['keyRef'])
c, d = call('POST', '/v1/permits/verify', VP); chk('permit 검증(S08 내부 호출): 로그인 없이 호출·active·서명 일치 → valid', c == 200 and d['valid'] is True, d)
c, d = call('POST', '/v1/permits/verify', dict(VP, amountMinor=999999)); chk('검증: 금액 변조 → invalid', c == 200 and d['valid'] is False and d['reason'] in ('BAD_SIGNATURE', 'RECORD_MISMATCH'), d)
c, d = call('POST', '/v1/permits/verify', dict(VP, signature='AAAA')); chk('검증: 서명 불일치 → invalid RECORD_MISMATCH(저장된 서명과 다름)', c == 200 and d['valid'] is False and d['reason'] == 'RECORD_MISMATCH', d)
c, d = call('POST', '/v1/permits/verify', dict(VP, permitId=str(uuid.uuid4()))); chk('검증: 모르는 permit → invalid UNKNOWN_PERMIT', c == 200 and d['valid'] is False and d['reason'] == 'UNKNOWN_PERMIT', d)
c, d = call('POST', '/v1/permits/verify', dict(VP, keyRef='https://evil/keys/x/v1')); chk('검증: 신뢰하지 않는 keyRef → invalid KEY_UNTRUSTED(외부 호출 없음)', c == 200 and d['valid'] is False and d['reason'] == 'KEY_UNTRUSTED', d)
c, d = call('POST', '/v1/permits/verify', {'permitId': PID}); chk('검증: 필드 부족 → invalid MALFORMED', c == 200 and d['valid'] is False and d['reason'] == 'MALFORMED', d)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ExecutionPermit SET useProhibited=1 WHERE permitId=?", (PID,)))
c, d = call('POST', '/v1/permits/verify', VP); chk('검증: 사용 금지 표시된 permit → invalid NOT_ACTIVE(철회 반영)', c == 200 and d['valid'] is False and d['reason'] == 'NOT_ACTIVE', d)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ExecutionPermit SET useProhibited=0 WHERE permitId=?", (PID,)))
# ---- permit claim(1회 사용 확정) ----
c, d = call('POST', '/v1/permits/claim', {'permitId': PID, 'claimant': 'exec-1'}); chk('claim: active permit → 200 claimed(로그인 없이 내부 호출)', c == 200 and d['claimed'] is True and d['replay'] is False and d['claimedBy'] == 'exec-1', d)
rw = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT state, claimedBy FROM ExecutionPermit WHERE permitId=?', (PID,)), cur.fetchall())[1]); chk('claim 후 DB 상태 claimed·claimedBy 기록', rw == [('claimed', 'exec-1')], rw)
c, d = call('POST', '/v1/permits/claim', {'permitId': PID, 'claimant': 'exec-1'}); chk('claim: 같은 claimant 재호출 → 200 replay(멱등)', c == 200 and d['replay'] is True, d)
c, d = call('POST', '/v1/permits/claim', {'permitId': PID, 'claimant': 'exec-2'}); chk('claim: 다른 claimant → 409 ALREADY_CLAIMED(이중 사용 차단)', c == 409 and d['code'] == 'ALREADY_CLAIMED', d)
c, d = call('POST', '/v1/permits/verify', VP); chk('claim된 permit은 verify에서 NOT_ACTIVE', c == 200 and d['valid'] is False and d['reason'] == 'NOT_ACTIVE', d)
c, d = call('POST', '/v1/permits/claim', {'permitId': str(uuid.uuid4()), 'claimant': 'x'}); chk('claim: 모르는 permit → 409 UNKNOWN_PERMIT', c == 409 and d['code'] == 'UNKNOWN_PERMIT', d)
c, d = call('POST', '/v1/permits/claim', {'permitId': 'zzz', 'claimant': 'x'}); chk('claim: permitId 형식 오류 400', c == 400, d)
c, d = call('POST', '/v1/permits/claim', {'permitId': PID}); chk('claim: claimant 없으면 400', c == 400, d)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ExecutionPermit SET state='active', claimedBy=NULL, useProhibited=1 WHERE permitId=?", (PID,)))
c, d = call('POST', '/v1/permits/claim', {'permitId': PID, 'claimant': 'exec-3'}); chk('claim: 사용 금지 permit → 409 NOT_ACTIVE', c == 409 and d['code'] == 'NOT_ACTIVE', d)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ExecutionPermit SET useProhibited=0, expiresAt='2020-01-01 00:00:00.000' WHERE permitId=?", (PID,)))
c, d = call('POST', '/v1/permits/claim', {'permitId': PID, 'claimant': 'exec-3'}); chk('claim: 만료 permit → 409 EXPIRED', c == 409 and d['code'] == 'EXPIRED', d)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE ExecutionPermit SET expiresAt='2999-01-01 00:00:00.000' WHERE permitId=?", (PID,)))
kv.lie = True; c, d = call('POST', '/v1/permits/verify', VP); chk('검증: Key Vault가 거짓이면 invalid BAD_SIGNATURE', c == 200 and d['valid'] is False and d['reason'] == 'BAD_SIGNATURE', d); kv.lie = False
# 신청자 본인 발급 금지 / 한도 초과 / 계정 불일치 / 서명 오류 / 검증 실패
Hi2 = Hi
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=11), {'Idempotency-Key': 'rq-ivan', 'Authorization': Hi['Authorization']}); RI = d.get('requestId'); chk('ivan(admin) 신청(request 권한 포함)', c == 201, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RI, decision='approve', expectedVersion=1), Hg); chk('gina 승인', c == 200, d)
c, d = call('POST', '/v1/permits', dict(requestId=RI, accountId=ACC, expectedApprovalVersion=1), Hi); chk('관리자는 본인 신청의 permit도 발급 가능(2026-11-01 사용자 결정, 업무 분리 예외)', c == 200 or c == 201, d)
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=13), {'Idempotency-Key': 'rq-ivan-self', 'Authorization': Hi['Authorization']}); RIS = d.get('requestId'); chk('ivan(admin) 신청 2', c == 201, d)
c, d = call('POST', '/v1/approval-decisions', dict(requestId=RIS, decision='approve', expectedVersion=1), Hi); chk('관리자는 본인 신청도 승인 가능(MFA·digest·버전 검증은 그대로)', c == 200 and d['state'] == 'approved', d)
n = AP.R.tx(lambda cur: (AP.R.ex(cur, "SELECT COUNT(*) FROM ApprovalAudit WHERE reason LIKE '%ADMIN_SELF%'"), cur.fetchall()[0][0])[1]); chk('본인 승인은 감사에 ADMIN_SELF로 남음', n >= 1, n)
c, d = call('POST', '/v1/admin/limit-accounts', dict(principalScope='KR-01', action='procurement.rec.purchase', currency='KRW', capMinor=500000, periodStart=P0, periodEnd=P1), Hi); SMALL = d['accountId']
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=12), {'Idempotency-Key': 'rq-f2', 'Authorization': Hf['Authorization']}); RF2 = d['requestId']; c, d = call('POST', '/v1/approval-decisions', dict(requestId=RF2, decision='approve', expectedVersion=1), Hg)
c, d = call('POST', '/v1/permits', dict(requestId=RF2, accountId=SMALL, expectedApprovalVersion=1), Hi); chk('한도 초과 409 LIMIT_EXCEEDED(예약·permit 없음)', c == 409 and d['code'] == 'LIMIT_EXCEEDED', d)
n_p = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT COUNT(*) FROM ExecutionPermit WHERE requestId=?', (RF2,)), cur.fetchall()[0][0])[1]); chk('한도 초과 시 permit 행 없음', n_p == 0)
c, d = call('POST', '/v1/admin/limit-accounts', dict(principalScope='KR-01', action='procurement.rec.purchase', currency='USD', capMinor=500000, periodStart=P0, periodEnd=P1), Hi); USD = d['accountId']
c, d = call('POST', '/v1/permits', dict(requestId=RF2, accountId=USD, expectedApprovalVersion=1), Hi); chk('통화 불일치 한도 계정 422', c == 422 and d['code'] == 'LIMIT_ACCOUNT_MISMATCH', d)
kv.fail = True; c, d = call('POST', '/v1/permits', dict(requestId=RF2, accountId=ACC, expectedApprovalVersion=1), Hi); kv.fail = None
st = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT state, useProhibited FROM ExecutionPermit WHERE requestId=?', (RF2,)), cur.fetchall()[0])[1]); chk('서명 오류 → 202 signing·사용 금지 유지·한도 held 유지(자동 재서명 없음)', c == 202 and d['state'] == 'signing' and st == ('signing', 1), (c, d, st))
c, d = call('POST', '/v1/permits', dict(requestId=RF2, accountId=ACC, expectedApprovalVersion=1), Hi); chk('signing 상태에서 재발급 요청도 거절(이중 예약 없음)', c == 409 and d['code'] == 'PERMIT_EXISTS', d)
c, d = call('POST', '/v1/approval-requests', dict(REFB, intentRevision=13), {'Idempotency-Key': 'rq-f3', 'Authorization': Hf['Authorization']}); RF3 = d['requestId']; call('POST', '/v1/approval-decisions', dict(requestId=RF3, decision='approve', expectedVersion=1), Hg)
kv.lie = True; c, d = call('POST', '/v1/permits', dict(requestId=RF3, accountId=ACC, expectedApprovalVersion=1), Hi); kv.lie = False
st = AP.R.tx(lambda cur: (AP.R.ex(cur, 'SELECT state FROM ExecutionPermit WHERE requestId=?', (RF3,)), cur.fetchall()[0][0])[1]); chk('서명 검증 실패 → 409·permit blocked', c == 409 and d['code'] == 'SIGNATURE_INVALID' and st == 'blocked', (c, d, st))
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE AppUser SET email='Boss@Example.com' WHERE isAdmin=1 AND status='active'"))
ems = AP.R.tx(lambda cur: AP.notify_emails(cur)); chk('가입 알림 수신자 = 활성 관리자의 내 정보 이메일(소문자·별도 알림 입력 없음)', ems and all(e == 'boss@example.com' for e in ems) and len(ems) == 1, ems)
AP.R.tx(lambda cur: AP.R.ex(cur, "UPDATE AppUser SET email=NULL WHERE isAdmin=1")); AP.R.tx(lambda cur: AP.R.ex(cur, "DELETE FROM AppSetting WHERE settingKey='signup.notify.emails'")); AP.R.tx(lambda cur: AP.R.ex(cur, "INSERT INTO AppSetting(settingKey, settingValue, updatedBy, updatedAt) VALUES ('signup.notify.emails','old@example.com','x','2026-01-01 00:00:00.000')"))
ems = AP.R.tx(lambda cur: AP.notify_emails(cur)); chk('관리자 이메일이 없을 때만 이전 설정값으로 대체', ems == ['old@example.com'], ems)
# ---- 거래 건별 진행 현황(/v1/cases, 읽기 전용) ----
c, d = call('GET', '/v1/cases'); chk('로그인 없이 cases 조회 불가 401', c == 401, d)
c, d = call('GET', '/v1/cases', None, {'Authorization': Hv['Authorization']}); chk('cases: 로그인한 사용자는 조회 가능(viewer 포함)·모의 표시', c == 200 and d['simulated'] and len(d['items']) >= 3, (c, str(d)[:200]))
it = {x['requestId']: x for x in d['items']}; ap = it.get(RF3)
chk('cases: 정책 평가·승인 결정·permit 상태가 건에 묶여 나온다', ap is not None and ap['policy']['decision'] and ap['decisions'] and ap['permit'] and ap['permit']['state'] == 'blocked', ap)
chk('cases: 실행 서비스 미구성이면 executionKnown=false(실행 없음으로 위장하지 않음)', all(x['executionKnown'] is True for x in d['items']) or all(x['execution'] is None for x in d['items']), None)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
