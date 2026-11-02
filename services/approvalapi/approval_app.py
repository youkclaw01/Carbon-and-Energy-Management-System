#!/usr/bin/env python3
"""approval-api — S07 API07·승인 신청(P1)·승인 결정(API08)·한도·permit (체크리스트 2-4-2~2-4-4). 설계: design/services/S07 §3~7.
상태(설계 정합): D12 미결 → propose-only. 평가는 항상 needs-approval, 승인 결정(API08)은 MFA 인증 문맥이 없어 503(AUTH_CONTEXT_UNAVAILABLE), permit 발급(P2)은 D12·정규화 합의·권한·S08 계약 미비로 차단(422), 예약 해제·정산 API14는 S08 증거 계약 전이라 열지 않는다. 한도 계정은 읽기 전용.
사용자 인가·MFA·위임 권한 원장은 없으므로 내부 전용·호출자는 X-Actor(미검증 라벨). 감사는 상태 변경과 같은 트랜잭션(해시 체인)이다."""
import re, urllib.error, os, sys, base64, json, time, uuid, threading, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import approval_core as K
import auth_core as U
import webauthn_core as W
VERSION = 'approval-api/0.14'; COUNTRY, ORG = 'KR', 'AMA-KR'; STATS = {}; R = None; TTL = dt.timedelta(hours=72)
def A(cur, actor, action, target, before=None, after=None, reason='', cid=None):
    R.chain(cur, 'ApprovalAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def need_idem(h):
    k = h.get('Idempotency-Key')
    if not k: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    return k[:100]
def policy_eval(body, h, cid):
    idem = need_idem(h); actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    try: r = K.evaluate(body)
    except K.Reject as e: raise ApiError(e.status, e.code, e.msg)
    rd = sha(canon(body)); eid = str(uuid.uuid4()); t0 = now()
    def f(cur):
        R.ex(cur, 'SELECT evaluationId, requestDigest FROM dbo.PolicyEvaluation WHERE country=%s AND orgId=%s AND principal=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem)); x = cur.fetchall()
        if x:
            if x[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, x[0][0]
        R.ex(cur, 'INSERT INTO dbo.PolicyEvaluation(evaluationId, country, orgId, principal, idemKey, requestDigest, action, resource, purpose, operationKey, intentDigest, canonicalizationVersion, digestAlgorithmId, amountMinor, currency, decision, reasonCode, policyVersion, proposeOnly, createdAt, expiresAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
             (eid, COUNTRY, ORG, actor, idem, rd, body['action'][:60], str(body['resource'])[:120], body['purpose'][:40], body['operationKey'][:160], body['intentDigest'], body['canonicalizationVersion'], body['digestAlgorithmId'], r['amountMinor'], r['currency'], r['decision'], r['reasonCode'], r['policyVersion'], 1, ts(t0), ts(t0 + dt.timedelta(minutes=15))))
        A(cur, actor, 'POLICY_EVALUATE', eid, reason=r['reasonCode'], cid=cid); return 201, eid
    c, eid = R.tx(f)
    return c, dict(evaluationId=eid, decision=r['decision'], reasonCode=r['reasonCode'], policyVersion=r['policyVersion'], proposeOnly=True, expiresAt=iso(ts(t0 + dt.timedelta(minutes=15))), note='제안 전용 평가입니다. 실행 허가·예약·서명·permit이 아닙니다(D12 미결).')
def req_view(r): return dict(requestId=r[0], state=r[1], rev=r[2], approvalVersion=r[3], operationKey=r[4], intentRevision=r[5], intentDigest=r[6], digestVerified=bool(r[7]), action=r[8], purpose=r[9], amountMinor=r[10], currency=r[11], requester=r[12], expiresAt=iso(r[13]), createdAt=iso(r[14]), updatedAt=iso(r[15]), evaluationId=r[16], proposeOnly=True, executable=False)
RC = 'requestId, state, rev, approvalVersion, operationKey, intentRevision, intentDigest, digestVerified, action, purpose, amountMinor, currency, requester, expiresAt, createdAt, updatedAt, evaluationId'
REASON_MIN, REASON_MAX = 10, 500
def clean_reason(v):
    """신청 사유(신청자 직접 입력): 문자열 10~500자, 제어문자 제거·공백 정리. 비어 있거나 짧으면 400(필수)."""
    if not isinstance(v, str): raise ApiError(400, 'REASON_REQUIRED', '신청 사유는 필수입니다(문자열).')
    t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v).replace('\r\n', '\n').strip()
    t = re.sub(r'[ \t]+', ' ', t); t = re.sub(r'\n{3,}', '\n\n', t)
    if len(t) < REASON_MIN or len(t) > REASON_MAX: raise ApiError(400, 'REASON_LENGTH', '신청 사유는 %d~%d자로 입력해 주세요(현재 %d자).' % (REASON_MIN, REASON_MAX, len(t)))
    return t
def create_request(body, h, cid):
    idem = need_idem(h); sess = session(h)   # 신청자는 로그인한 사용자(X-Actor 라벨로 위장 불가). 'request' 권한이 있어야 한다
    if not R.tx(lambda cur: has_grant(cur, sess['userId'], 'request')): raise ApiError(403, 'FORBIDDEN', '승인 신청 권한(request)이 없습니다.')
    actor = sess['username']; eid = str(body.get('evaluationId') or ''); rev = body.get('intentRevision', 1); reason = clean_reason(body.get('reason'))
    if not eid or not isinstance(rev, int) or rev < 1: raise ApiError(400, 'BAD_REQUEST', 'evaluationId, intentRevision(양의 정수)이 필요합니다.')
    rd = sha(canon(dict(e=eid, r=rev, d=body.get('intentDigest'), i=body.get('intentRef'), why=reason))); rid = str(uuid.uuid4()); t0 = now()
    iref = body.get('intentRef'); iv = VERIFY(iref, body.get('intentDigest')) if iref else False
    if iref and (not isinstance(iref, dict) or not isinstance(iref.get('intentId'), str)): raise ApiError(400, 'BAD_REQUEST', 'intentRef는 {intentId, intentVersion}입니다.')
    def f(cur):
        R.ex(cur, 'SELECT ' + RC + ' FROM dbo.ApprovalRequest WHERE country=%s AND orgId=%s AND requester=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem)); x = cur.fetchall()
        if x:
            R.ex(cur, 'SELECT requestDigest FROM dbo.ApprovalRequest WHERE requestId=%s', (x[0][0],))
            if cur.fetchall()[0][0] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, req_view(x[0])
        R.ex(cur, 'SELECT evaluationId, intentDigest, operationKey, action, purpose, amountMinor, currency, decision, expiresAt FROM dbo.PolicyEvaluation WHERE evaluationId=%s', (eid,)); e = cur.fetchall()
        if not e: raise ApiError(404, 'NOT_FOUND', '해당 평가가 없습니다.')
        if body.get('intentDigest') != e[0][1]: raise ApiError(409, 'DIGEST_MISMATCH', '평가에 고정된 intentDigest와 다릅니다. 조건 변경은 새 평가·새 revision입니다.')
        R.ex(cur, 'INSERT INTO dbo.ApprovalRequest(requestId, country, orgId, evaluationId, requester, idemKey, requestDigest, operationKey, intentRevision, intentDigest, digestVerified, action, purpose, amountMinor, currency, state, rev, approvalVersion, expiresAt, createdAt, updatedAt, intentRef, requestReason, reasonUpdatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,0,%s,%s,%s,%s,%s,%s)',
             (rid, COUNTRY, ORG, eid, actor, idem, rd, e[0][2], rev, e[0][1], 1 if iv else 0, e[0][3], e[0][4], e[0][5], e[0][6], 'pending', ts(t0 + K_TTL), ts(t0), ts(t0), json.dumps(iref, sort_keys=True) if iref else None, reason, ts(t0)))
        A(cur, actor, 'APPROVAL_REQUEST', rid, after='1', reason='pending(digest 재검증 %s)' % ('통과' if iv else '미통과·미제출'), cid=cid)
        A(cur, actor, 'REQUEST_REASON', rid, after='1', reason=reason[:280], cid=cid)   # 신청자가 직접 입력한 사유(감사 기록은 앞 280자, 전문은 신청 건에 보관)
        R.ex(cur, 'SELECT ' + RC + ' FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)); return 201, req_view(cur.fetchall()[0])
    return R.tx(f)

def verify_intent(ref, digest):
    """S04 소유 API로 intent를 재조회해 digest·규약·상태·최신 버전을 확인한다(S07이 digest를 스스로 만들지 않는다). 조회 실패·불일치는 모두 False(닫힘)."""
    try:
        base = os.environ.get('PROC_API_URL')
        if not base or not isinstance(ref, dict) or not ref.get('intentId') or not isinstance(ref.get('intentVersion'), int): return False
        r = json.loads(urllib.request.urlopen(urllib.request.Request('%s/v1/procurement-intents/%s?version=%d' % (base.rstrip('/'), urllib.parse.quote(str(ref['intentId'])), ref['intentVersion'])), timeout=10).read())
        return r.get('bindingState') == 'BOUND' and r.get('mode') == 'SIMULATED' and r.get('intentDigest') == digest and r.get('canonicalizationVersion') == K.CANON and r.get('digestAlgorithmId') == K.ALG and r.get('latestVersion') == ref['intentVersion']
    except Exception: return False
VERIFY = verify_intent
K_TTL = TTL
def get_request(rid):
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'requestId 형식이 올바르지 않습니다.')
    x = R.tx(lambda cur: (R.ex(cur, 'SELECT ' + RC + ' FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 신청이 없습니다.')
    d = req_view(x[0]); d.update(reason_view(rid)); return d
def reason_view(rid):
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT requestReason, reasonUpdatedAt FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)), cur.fetchall())[1])
    return dict(reason=r[0][0] if r else None, reasonUpdatedAt=iso(r[0][1]) if r and r[0][1] else None)
def update_reason(rid, body, h, cid):
    """신청자 본인만, 승인 대기(pending) 중에만 사유를 수정한다. 수정 시각이 바뀌면 승인자의 결정은 409(REASON_CHANGED)로 막혀 다시 확인하게 한다."""
    s = session(h)
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'requestId 형식이 올바르지 않습니다.')
    new = clean_reason(body.get('reason'))
    def f(cur):
        R.ex(cur, 'SELECT requester, state, requestReason FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)); x = cur.fetchall()
        if not x: return 404, 'NOT_FOUND', '해당 신청이 없습니다.'
        if x[0][0] != s['username']: A(cur, s['username'], 'REQUEST_REASON_DENY', rid, reason='NOT_REQUESTER', cid=cid); return 403, 'FORBIDDEN', '신청자 본인만 사유를 수정할 수 있습니다.'
        if x[0][1] != 'pending': A(cur, s['username'], 'REQUEST_REASON_DENY', rid, reason='NOT_PENDING:' + str(x[0][1]), cid=cid); return 409, 'NOT_PENDING', '승인 대기 중인 신청만 사유를 수정할 수 있습니다.'
        if x[0][2] == new: return 200, 'unchanged', None
        t = ts(); R.ex(cur, 'UPDATE dbo.ApprovalRequest SET requestReason=%s, reasonUpdatedAt=%s, updatedAt=%s WHERE requestId=%s AND state=%s', (new, t, t, rid, 'pending'))
        A(cur, s['username'], 'REQUEST_REASON_UPDATE', rid, reason=new[:280], cid=cid); return 200, 'updated', None
    c, code, msg = R.tx(f)
    if c != 200: raise ApiError(c, code, msg)
    return 200, dict(requestId=rid, result=code, **reason_view(rid))

# ---------------- 자체 로그인·MFA·권한 원장 (사용자 결정: Entra 아님) ----------------
KEY = lambda: os.environ.get('AUTH_DATA_KEY')
def u_err(e): return ApiError(e.status, e.code, e.msg)
def bearer(h):
    v = h.get('Authorization') or ''
    return v[7:] if v.lower().startswith('bearer ') else None
def session(h, need_mfa=False):
    """유효 세션 → dict(userId, username, isAdmin, mfa). 세션 없음·만료·폐기는 401. need_mfa면 MFA 검증 세션만."""
    t = bearer(h)
    if not t: raise ApiError(401, 'UNAUTHENTICATED', '로그인이 필요합니다.')
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT s.userId, u.username, u.isAdmin, s.mfaVerified, s.expiresAt, s.revokedAt, u.status FROM dbo.AppSession s JOIN dbo.AppUser u ON u.userId=s.userId WHERE s.tokenHash=%s', (U.token_hash(t),)), cur.fetchall())[1])
    if not r or r[0][5] is not None or r[0][6] != 'active' or str(r[0][4])[:23] < ts(): raise ApiError(401, 'UNAUTHENTICATED', '세션이 없거나 만료되었습니다. 다시 로그인하세요.')
    s = dict(userId=r[0][0], username=r[0][1], isAdmin=bool(r[0][2]), mfa=bool(r[0][3]), token=t)
    if need_mfa and not s['mfa']: raise ApiError(403, 'MFA_REQUIRED', 'MFA 인증이 완료된 세션이 필요합니다.')
    return s
def has_grant(cur, uid, action):
    R.ex(cur, 'SELECT COUNT(*) FROM dbo.UserGrant WHERE userId=%s AND action=%s AND revokedAt IS NULL AND validFrom<=%s AND (validTo IS NULL OR validTo>%s)', (uid, action, ts(), ts())); return cur.fetchall()[0][0] > 0
def register(body, h, cid, by_admin=False):
    try: un = U.check_username(body.get('username')); U.check_password(body.get('password'))
    except U.AuthError as e: raise u_err(e)
    if not by_admin and un != os.environ.get('BOOTSTRAP_ADMIN_USERNAME'): raise ApiError(403, 'REGISTRATION_CLOSED', '공개 가입은 닫혀 있습니다. 관리자가 계정을 만들어 줍니다.')
    ph, salt = U.hash_password(body['password']); uid = str(uuid.uuid4())
    def f(cur):
        R.ex(cur, 'SELECT COUNT(*) FROM dbo.AppUser WHERE username=%s', (un,))
        if cur.fetchall()[0][0]: raise ApiError(409, 'USERNAME_TAKEN', '이미 사용 중인 아이디입니다.')
        adm = 1 if (not by_admin and os.environ.get('BOOTSTRAP_ADMIN_USERNAME') == un) else 0   # 관리자 부트스트랩은 환경에 지정한 아이디 한 개만(아이디는 유일), 그 외 계정은 권한 없음
        R.ex(cur, 'INSERT INTO dbo.AppUser(userId, username, pwHash, pwSalt, status, isAdmin, mfaEnrolled, mfaLastStep, failCount, createdAt, grade) VALUES (%s,%s,%s,%s,%s,%s,0,0,0,%s,%s)', (uid, un, ph, salt, 'active', adm, ts(), 'admin' if adm else 'viewer'))
        if body.get('email'):
            try: R.ex(cur, 'UPDATE dbo.AppUser SET email=%s WHERE userId=%s', (U.check_email(body['email']), uid))
            except U.AuthError as e: raise u_err(e)
        if adm: R.ex(cur, 'INSERT INTO dbo.UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES (%s,%s,%s,%s,%s)', (str(uuid.uuid4()), uid, 'admin', 'bootstrap', ts()))
        A(cur, un, 'USER_REGISTER', uid, reason='admin' if adm else 'no-privilege', cid=cid); return adm
    adm = R.tx(f); return 201, dict(userId=uid, username=un, isAdmin=bool(adm), mfaEnrolled=False, note='계정이 만들어졌습니다. 로그인 후 MFA를 등록하세요. 권한은 관리자가 부여해야 생깁니다.')
def admin_create_user(body, h, cid):
    s = session(h, need_mfa=True)
    if not R.tx(lambda cur: has_grant(cur, s['userId'], 'admin')): raise ApiError(403, 'FORBIDDEN', '관리자 권한이 필요합니다.')
    return register(body, h, cid, by_admin=True)
def change_password(body, h, cid):
    s = session(h); cur_pw = str(body.get('currentPassword') or '')
    try: U.check_password(body.get('newPassword'))
    except U.AuthError as e: raise u_err(e)
    nh, ns = U.hash_password(body['newPassword'])
    def f(cur):
        R.ex(cur, 'SELECT pwHash, pwSalt FROM dbo.AppUser WHERE userId=%s', (s['userId'],)); x = cur.fetchall()[0]
        if not U.verify_password(cur_pw, x[0], x[1]): A(cur, s['username'], 'PASSWORD_CHANGE_FAIL', s['userId'], cid=cid); return False
        R.ex(cur, 'UPDATE dbo.AppUser SET pwHash=%s, pwSalt=%s WHERE userId=%s', (nh, ns, s['userId']))
        R.ex(cur, 'UPDATE dbo.AppSession SET revokedAt=%s WHERE userId=%s AND tokenHash<>%s AND revokedAt IS NULL', (ts(), s['userId'], U.token_hash(s['token']))); A(cur, s['username'], 'PASSWORD_CHANGE', s['userId'], cid=cid); return True
    if not R.tx(f): raise ApiError(401, 'INVALID_CREDENTIALS', '현재 비밀번호가 올바르지 않습니다.')
    return 200, dict(ok=True, note='다른 세션은 모두 로그아웃되었습니다.')
def login(body, h, cid):
    un = str(body.get('username') or ''); pw = str(body.get('password') or ''); code = body.get('totp'); t0 = now()
    def f(cur):
        R.ex(cur, 'SELECT userId, pwHash, pwSalt, status, mfaSecretEnc, mfaEnrolled, mfaLastStep, failCount, lockedUntil, isAdmin FROM dbo.AppUser WHERE username=%s', (un,)); r = cur.fetchall()
        def fail(c, code_, msg, uid=None, cnt=None):
            if uid: R.ex(cur, 'UPDATE dbo.AppUser SET failCount=%s, lockedUntil=%s WHERE userId=%s', (cnt, ts(t0 + dt.timedelta(seconds=U.LOCK_S)) if cnt >= U.MAX_FAIL else None, uid))
            A(cur, un[:40] or '-', 'LOGIN_FAIL', uid or '-', reason=code_, cid=cid); return (c, code_, msg)
        if not r:
            U.hash_password(pw or 'x')    # 계정 존재 여부를 응답 시간으로 드러내지 않기 위한 더미 해시
            return fail(401, 'INVALID_CREDENTIALS', '아이디 또는 비밀번호가 올바르지 않습니다.')
        x = r[0]
        if x[8] is not None and str(x[8])[:23] > ts(t0): return fail(423, 'ACCOUNT_LOCKED', '로그인 실패가 반복되어 잠시 잠겼습니다. 15분 뒤 다시 시도하세요.')
        if not U.verify_password(pw, x[1], x[2]) or x[3] in ('disabled',): return fail(401, 'INVALID_CREDENTIALS', '아이디 또는 비밀번호가 올바르지 않습니다.', x[0], (x[7] or 0) + 1)
        if x[3] == 'pending': return fail(403, 'ACCOUNT_PENDING', '가입 승인 대기 중입니다. 관리자가 승인하면 로그인할 수 있습니다.')
        if x[3] == 'rejected': return fail(403, 'ACCOUNT_REJECTED', '가입이 승인되지 않았습니다. 관리자에게 문의하세요.')
        mfa = False
        if x[5]:
            if not code: return fail(401, 'MFA_REQUIRED', '인증 앱의 6자리 코드를 입력하세요.')
            try: step = U.totp_verify(U.unseal(KEY(), x[4], x[0]), str(code), x[6] or 0, t=t0.replace(tzinfo=dt.timezone.utc).timestamp())
            except U.AuthError as e: raise u_err(e)
            if step is None: return fail(401, 'INVALID_MFA', '인증 코드가 올바르지 않거나 이미 사용되었습니다.', x[0], (x[7] or 0) + 1)
            R.ex(cur, 'UPDATE dbo.AppUser SET mfaLastStep=%s WHERE userId=%s', (step, x[0])); mfa = True
        R.ex(cur, 'UPDATE dbo.AppUser SET failCount=0, lockedUntil=NULL WHERE userId=%s', (x[0],))
        tok, th = U.new_token(); R.ex(cur, 'INSERT INTO dbo.AppSession(tokenHash, userId, mfaVerified, createdAt, expiresAt) VALUES (%s,%s,%s,%s,%s)', (th, x[0], 1 if mfa else 0, ts(t0), ts(t0 + dt.timedelta(seconds=U.SESSION_S))))
        A(cur, un, 'LOGIN_OK', x[0], reason='mfa' if mfa else 'no-mfa', cid=cid); return (200, dict(token=tok, username=un, mfaVerified=mfa, mfaEnrolled=bool(x[5]), isAdmin=bool(x[9]), expiresAt=iso(t0 + dt.timedelta(seconds=U.SESSION_S))), None)
    r = R.tx(f)
    if r[0] != 200: raise ApiError(r[0], r[1], r[2])
    return 200, r[1]
def me(h):
    s = session(h); r = R.tx(lambda cur: (R.ex(cur, 'SELECT mfaEnrolled, email, displayName, grade FROM dbo.AppUser WHERE userId=%s', (s['userId'],)), cur.fetchall()[0], [x[0] for x in (R.ex(cur, 'SELECT action FROM dbo.UserGrant WHERE userId=%s AND revokedAt IS NULL AND validFrom<=%s AND (validTo IS NULL OR validTo>%s)', (s['userId'], ts(), ts())), cur.fetchall())[1]])[1:])
    return 200, dict(username=s['username'], isAdmin=s['isAdmin'], mfaVerified=s['mfa'], mfaEnrolled=bool(r[0][0]), email=r[0][1], displayName=r[0][2], grade=r[0][3], grants=r[1])
def mfa_enroll(h, cid):
    s = session(h)
    if not KEY(): raise ApiError(503, 'AUTH_KEY_UNAVAILABLE', 'MFA 비밀 암호화 키가 구성되지 않았습니다.')
    sec = U.totp_secret()
    def f(cur):
        R.ex(cur, 'SELECT mfaEnrolled FROM dbo.AppUser WHERE userId=%s', (s['userId'],))
        if cur.fetchall()[0][0]: raise ApiError(409, 'MFA_ALREADY_ENROLLED', '이미 MFA가 등록되어 있습니다.')
        R.ex(cur, 'UPDATE dbo.AppUser SET mfaSecretEnc=%s, mfaLastStep=0 WHERE userId=%s', (U.seal(KEY(), sec, s['userId']), s['userId'])); A(cur, s['username'], 'MFA_ENROLL_START', s['userId'], cid=cid)
    R.tx(f); return 200, dict(secret=sec, otpauthUri=U.otpauth(s['username'], sec), note='인증 앱(Microsoft Authenticator·Google Authenticator 등)에 등록한 뒤 현재 6자리 코드를 /v1/auth/mfa/confirm에 보내세요. 이 비밀은 다시 보여 주지 않습니다.')
def mfa_confirm(body, h, cid):
    s = session(h); code = str(body.get('code') or '')
    def f(cur):
        R.ex(cur, 'SELECT mfaSecretEnc, mfaEnrolled FROM dbo.AppUser WHERE userId=%s', (s['userId'],)); x = cur.fetchall()[0]
        if x[1]: raise ApiError(409, 'MFA_ALREADY_ENROLLED', '이미 MFA가 등록되어 있습니다.')
        if not x[0]: raise ApiError(409, 'MFA_NOT_STARTED', '먼저 /v1/auth/mfa/enroll을 호출하세요.')
        step = U.totp_verify(U.unseal(KEY(), x[0], s['userId']), code, 0, t=now().replace(tzinfo=dt.timezone.utc).timestamp())
        if step is None: raise ApiError(400, 'INVALID_MFA', '인증 코드가 올바르지 않습니다.')
        R.ex(cur, 'UPDATE dbo.AppUser SET mfaEnrolled=1, mfaLastStep=%s WHERE userId=%s', (step, s['userId'])); R.ex(cur, 'UPDATE dbo.AppSession SET mfaVerified=1 WHERE tokenHash=%s', (U.token_hash(s['token']),)); A(cur, s['username'], 'MFA_ENROLLED', s['userId'], cid=cid)
    R.tx(f); return 200, dict(mfaEnrolled=True, mfaVerified=True)
def logout(h, cid):
    s = session(h); R.tx(lambda cur: (R.ex(cur, 'UPDATE dbo.AppSession SET revokedAt=%s WHERE tokenHash=%s', (ts(), U.token_hash(s['token']))), A(cur, s['username'], 'LOGOUT', s['userId'], cid=cid))); return 200, dict(ok=True)
def grant(body, h, cid):
    """관리자(admin 권한 + MFA 세션)만 다른 사용자에게 권한 부여/회수. 자기 자신에게 approve 부여는 직무 분리로 거절."""
    s = session(h, need_mfa=True); un = str(body.get('username') or ''); act = body.get('action'); rev = bool(body.get('revoke'))
    if act not in ('request', 'approve', 'permit.issue', 'admin'): raise ApiError(400, 'BAD_ACTION', 'action은 request/approve/permit.issue/admin입니다.')
    def f(cur):
        if not has_grant(cur, s['userId'], 'admin'): raise ApiError(403, 'FORBIDDEN', '관리자 권한이 필요합니다.')
        R.ex(cur, 'SELECT userId FROM dbo.AppUser WHERE username=%s', (un,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 사용자가 없습니다.')
        if x[0][0] == s['userId'] and act in ('approve', 'permit.issue') and not rev: raise ApiError(403, 'SEPARATION_OF_DUTY', '자기 자신에게 승인·permit 권한을 줄 수 없습니다.')
        if rev: R.ex(cur, 'UPDATE dbo.UserGrant SET revokedAt=%s WHERE userId=%s AND action=%s AND revokedAt IS NULL', (ts(), x[0][0], act))
        else: R.ex(cur, 'INSERT INTO dbo.UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES (%s,%s,%s,%s,%s)', (str(uuid.uuid4()), x[0][0], act, s['username'], ts()))
        A(cur, s['username'], 'GRANT_REVOKE' if rev else 'GRANT_ADD', x[0][0], reason=act, cid=cid)
    R.tx(f); return 200, dict(username=un, action=act, revoked=rev)

# ---------------- 가입 신청·관리자 결정·등급·승인 요청 메일 ----------------
def admin_session(h):
    s = session(h, need_mfa=True)
    if not R.tx(lambda cur: has_grant(cur, s['userId'], 'admin')): raise ApiError(403, 'FORBIDDEN', '관리자 권한이 필요합니다.')
    return s
def notify_emails(cur):
    """가입 승인 요청 수신자: 활성 관리자(isAdmin 또는 admin 권한)의 '내 정보' 이메일(최대 5명). 별도 알림 이메일 입력 없음 — 이전 설정값은 관리자 이메일이 하나도 없을 때만 대체로 쓴다."""
    R.ex(cur, "SELECT DISTINCT LOWER(u.email) FROM dbo.AppUser u WHERE u.status='active' AND u.email IS NOT NULL AND u.email<>'' AND (u.isAdmin=1 OR EXISTS (SELECT 1 FROM dbo.UserGrant g WHERE g.userId=u.userId AND g.action='admin' AND g.revokedAt IS NULL))")
    ems = [x[0] for x in cur.fetchall()][:5]
    if ems: return ems
    R.ex(cur, "SELECT settingValue FROM dbo.AppSetting WHERE settingKey='signup.notify.emails'"); r = cur.fetchall(); return [x for x in (r[0][0].split(',') if r else []) if x]
def enqueue(cur, kind, to, subject, body):
    R.ex(cur, 'INSERT INTO dbo.MailOutbox(mailId, kind, toEmail, subject, body, state, attempts, createdAt) VALUES (%s,%s,%s,%s,%s,%s,0,%s)', (str(uuid.uuid4()), kind, to, subject[:160], body[:1000], 'pending', ts()))
def signup(body, h, cid):
    """공개 가입 신청: 계정은 pending이라 로그인·권한 없음. 관리자가 등급을 정해 승인해야 active. 등록된 관리자 이메일로 승인 요청 메일을 큐에 넣는다."""
    try: un = U.check_username(body.get('username')); U.check_password(body.get('password')); em = U.check_email(body.get('email'))
    except U.AuthError as e: raise u_err(e)
    dn = (str(body.get('displayName') or '')[:60]).strip() or None; ph, salt = U.hash_password(body['password']); uid = str(uuid.uuid4())
    def f(cur):
        R.ex(cur, 'SELECT COUNT(*) FROM dbo.AppUser WHERE username=%s', (un,))
        if cur.fetchall()[0][0]: raise ApiError(409, 'USERNAME_TAKEN', '이미 사용 중인 아이디입니다.')
        R.ex(cur, 'SELECT COUNT(*) FROM dbo.AppUser WHERE LOWER(email)=%s', (em,))
        if cur.fetchall()[0][0]: raise ApiError(409, 'EMAIL_TAKEN', '이미 가입에 사용된 이메일입니다.')
        R.ex(cur, "SELECT COUNT(*) FROM dbo.AppUser WHERE status='pending'"); 
        if cur.fetchall()[0][0] >= 50: raise ApiError(429, 'SIGNUP_QUEUE_FULL', '대기 중인 가입 신청이 너무 많습니다. 나중에 다시 시도하세요.', True)
        R.ex(cur, 'INSERT INTO dbo.AppUser(userId, username, pwHash, pwSalt, status, isAdmin, mfaEnrolled, mfaLastStep, failCount, createdAt, email, displayName, grade) VALUES (%s,%s,%s,%s,%s,0,0,0,0,%s,%s,%s,NULL)', (uid, un, ph, salt, 'pending', ts(), em, dn))
        tos = notify_emails(cur)
        for t in tos: enqueue(cur, 'SIGNUP_REQUEST', t, '[AMA] 회원 가입 승인 요청: ' + un, '가입 신청이 접수되었습니다.\n아이디: %s\n이름: %s\n이메일: %s\n신청 시각(UTC): %s\n\n관리자 화면(https://ama.example.com/account.html)에서 등급을 지정해 승인 또는 거절하세요.' % (un, dn or '-', em, ts()))
        A(cur, un, 'SIGNUP_REQUEST', uid, reason='notify=%d' % len(tos), cid=cid); return len(tos)
    n = R.tx(f); return 202, dict(username=un, state='pending', note='가입 신청이 접수되었습니다. 관리자가 등급을 정해 승인하면 로그인할 수 있습니다.', adminNotified=n > 0)
def list_signups(h, qs):
    admin_session(h); st = (qs.get('state') or ['pending'])[0]
    if st not in ('pending', 'active', 'rejected', 'disabled'): raise ApiError(400, 'BAD_REQUEST', 'state가 올바르지 않습니다.')
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT username, displayName, email, status, grade, createdAt, decidedBy FROM dbo.AppUser WHERE status=%s ORDER BY createdAt', (st,)), cur.fetchall())[1])
    return 200, dict(items=[dict(username=x[0], displayName=x[1], email=x[2], state=x[3], grade=x[4], createdAt=str(x[5]), decidedBy=x[6]) for x in r], grades=U.GRADE_LABEL)
def apply_grade(cur, uid, grade, by):
    R.ex(cur, 'UPDATE dbo.UserGrant SET revokedAt=%s WHERE userId=%s AND revokedAt IS NULL', (ts(), uid))
    for act in U.GRADES[grade]: R.ex(cur, 'INSERT INTO dbo.UserGrant(grantId, userId, action, grantedBy, validFrom) VALUES (%s,%s,%s,%s,%s)', (str(uuid.uuid4()), uid, act, by, ts()))
    R.ex(cur, 'UPDATE dbo.AppUser SET grade=%s, isAdmin=%s WHERE userId=%s', (grade, 1 if grade == 'admin' else 0, uid))
def signup_decision(body, h, cid):
    s = admin_session(h); un = str(body.get('username') or ''); d = body.get('decision')
    if d not in ('approve', 'reject'): raise ApiError(400, 'BAD_REQUEST', 'decision은 approve/reject입니다.')
    try: grade = U.check_grade(body.get('grade')) if d == 'approve' else None
    except U.AuthError as e: raise u_err(e)
    def f(cur):
        R.ex(cur, 'SELECT userId, status, email FROM dbo.AppUser WHERE username=%s', (un,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 신청이 없습니다.')
        if x[0][1] != 'pending': raise ApiError(409, 'NOT_PENDING', '대기 중인 신청이 아닙니다.')
        if x[0][0] == s['userId']: raise ApiError(403, 'SEPARATION_OF_DUTY', '자기 자신의 신청은 결정할 수 없습니다.')
        if d == 'approve':
            R.ex(cur, "UPDATE dbo.AppUser SET status='active', decidedBy=%s, decidedAt=%s WHERE userId=%s", (s['username'], ts(), x[0][0])); apply_grade(cur, x[0][0], grade, s['username'])
        else: R.ex(cur, "UPDATE dbo.AppUser SET status='rejected', decidedBy=%s, decidedAt=%s WHERE userId=%s", (s['username'], ts(), x[0][0]))
        if x[0][2]: enqueue(cur, 'SIGNUP_RESULT', x[0][2], '[AMA] 가입 신청 결과', ('가입이 승인되었습니다. 등급: %s. 로그인 후 MFA를 등록하세요.' % U.GRADE_LABEL[grade]) if d == 'approve' else '가입 신청이 승인되지 않았습니다.')
        A(cur, s['username'], 'SIGNUP_APPROVE' if d == 'approve' else 'SIGNUP_REJECT', x[0][0], reason=(grade or ''), cid=cid)
    R.tx(f); return 200, dict(username=un, state='active' if d == 'approve' else 'rejected', grade=grade)
def set_grade(body, h, cid):
    s = admin_session(h); un = str(body.get('username') or '')
    try: grade = U.check_grade(body.get('grade'))
    except U.AuthError as e: raise u_err(e)
    def f(cur):
        R.ex(cur, "SELECT userId FROM dbo.AppUser WHERE username=%s AND status='active'", (un,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '활성 사용자가 없습니다.')
        if x[0][0] == s['userId']: raise ApiError(403, 'SEPARATION_OF_DUTY', '자기 자신의 등급은 바꿀 수 없습니다.')
        apply_grade(cur, x[0][0], grade, s['username']); A(cur, s['username'], 'GRADE_SET', x[0][0], reason=grade, cid=cid)
    R.tx(f); return 200, dict(username=un, grade=grade)
def notify_setting(body, h, cid, write):
    s = admin_session(h)
    if not write: return 200, dict(emails=R.tx(lambda cur: notify_emails(cur)))
    try: ems = sorted({U.check_email(e) for e in (body.get('emails') or [])})
    except U.AuthError as e: raise u_err(e)
    if not ems or len(ems) > 5: raise ApiError(400, 'BAD_REQUEST', '이메일은 1~5개여야 합니다.')
    def f(cur):
        R.ex(cur, "SELECT COUNT(*) FROM dbo.AppSetting WHERE settingKey='signup.notify.emails'")
        if cur.fetchall()[0][0]: R.ex(cur, "UPDATE dbo.AppSetting SET settingValue=%s, updatedBy=%s, updatedAt=%s WHERE settingKey='signup.notify.emails'", (','.join(ems), s['username'], ts()))
        else: R.ex(cur, "INSERT INTO dbo.AppSetting(settingKey, settingValue, updatedBy, updatedAt) VALUES ('signup.notify.emails',%s,%s,%s)", (','.join(ems), s['username'], ts()))
        A(cur, s['username'], 'NOTIFY_EMAIL_SET', 'signup.notify.emails', reason='n=%d' % len(ems), cid=cid)
    R.tx(f); return 200, dict(emails=ems)
def mail_status(h):
    admin_session(h); r = R.tx(lambda cur: (R.ex(cur, 'SELECT state, COUNT(*) FROM dbo.MailOutbox GROUP BY state'), cur.fetchall())[1]); return 200, dict(counts={x[0]: x[1] for x in r}, sender='configured' if mailer_ready() else 'not-configured')
def send_acs(to, subject, body):
    """Azure Communication Services Email REST(관리 ID 토큰). ACS_ENDPOINT·ACS_SENDER가 설정된 경우에만 사용한다."""
    ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']
    u = ep + '?resource=https://communication.azure.com/&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
    tok = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
    rq = urllib.request.Request(os.environ['ACS_ENDPOINT'].rstrip('/') + '/emails:send?api-version=2023-03-31', method='POST', data=json.dumps({'senderAddress': os.environ['ACS_SENDER'], 'content': {'subject': subject, 'plainText': body}, 'recipients': {'to': [{'address': to}]}}).encode(), headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    # 컨테이너 앱에는 IPv6 경로가 없다 → IPv4만 사용(실패 원인이 IPv6 오류에 가려지지 않게 한다)
    import http.client, socket, ssl as _ssl, urllib.parse as _up
    u = _up.urlparse(rq.full_url)
    ips = sorted({a[4][0] for a in socket.getaddrinfo(u.hostname, u.port or 443, socket.AF_INET, socket.SOCK_STREAM)})
    last = None; r = None
    for ip in ips:  # 한 주소가 끊겨도 다른 IPv4 주소로 재시도하고, 실패 단계·주소를 오류에 남긴다
        stage = 'connect'
        class V4(http.client.HTTPSConnection):
            def connect(self, _ip=ip):
                sk = socket.create_connection((_ip, u.port or 443), self.timeout); self.sock = _ssl.create_default_context().wrap_socket(sk, server_hostname=u.hostname)
        cn = V4(u.hostname, u.port or 443, timeout=30)
        try:
            stage = 'request'; cn.request('POST', u.path + ('?' + u.query if u.query else ''), body=rq.data, headers=dict(rq.header_items()))
            stage = 'response'; r = cn.getresponse(); b = r.read(); last = None; break
        except Exception as e: last = '%s@%s ip=%s %s' % (stage, u.hostname.split('.')[0], ip, type(e).__name__)
        finally: cn.close()
    if last: raise urllib.error.URLError(last)
    if r.status >= 300: raise urllib.error.HTTPError(rq.full_url, r.status, b[:120].decode('utf-8', 'replace'), r.headers, None)
def send_smtp(to, subject, body):
    """SMTP 제출(STARTTLS 587 또는 SMTPS 465, 사용자·비밀번호 인증). 발신 도메인(SMTP_FROM, 예: noreply@example.com)의 SPF/DKIM은 해당 메일 서버가 처리한다. 비밀번호는 환경 비밀(SMTP_PASSWORD)에서만 읽는다."""
    import smtplib, ssl
    from email.message import EmailMessage
    m = EmailMessage(); m['From'] = os.environ['SMTP_FROM']; m['To'] = to; m['Subject'] = subject; m.set_content(body)
    host, port = os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '587')); ctx = ssl.create_default_context()
    if os.environ.get('SMTP_SSL_NO_VERIFY') == '1': ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with cls(host, port, timeout=20, **({'context': ctx} if port == 465 else {})) as s:
        if port != 465 and os.environ.get('SMTP_STARTTLS', '1') == '1': s.starttls(context=ctx)
        if os.environ.get('SMTP_USER'): s.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        s.send_message(m)
def mailer_ready(): return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_FROM')) or bool(os.environ.get('ACS_ENDPOINT') and os.environ.get('ACS_SENDER'))
def default_mailer(to, subject, body): return send_smtp(to, subject, body) if os.environ.get('SMTP_HOST') else send_acs(to, subject, body)
MAILER = default_mailer
def deliver_mail(limit=20):
    """대기 메일을 보낸다. 실패는 attempts 증가 후 5회에서 failed. 발송기가 없으면 건드리지 않는다(pending 유지)."""
    if MAILER is default_mailer and not mailer_ready(): return 0
    rows = R.tx(lambda cur: (R.ex(cur, "SELECT mailId, toEmail, subject, body, attempts FROM dbo.MailOutbox WHERE state='pending' ORDER BY createdAt"), cur.fetchall()[:limit])[1]); n = 0
    for m in rows:
        try: MAILER(m[1], m[2], m[3]); R.tx(lambda cur: R.ex(cur, "UPDATE dbo.MailOutbox SET state='sent', attempts=attempts+1, sentAt=%s WHERE mailId=%s", (ts(), m[0]))); n += 1
        except Exception as e: R.tx(lambda cur: R.ex(cur, 'UPDATE dbo.MailOutbox SET attempts=attempts+1, lastError=%s, state=%s WHERE mailId=%s', ((type(e).__name__ + (' ' + str(e.code) if hasattr(e, 'code') else '') + (' ' + str(getattr(e, 'reason', ''))[:60] if not hasattr(e, 'code') else ''))[:100], 'failed' if m[4] + 1 >= 5 else 'pending', m[0])))
    return n
def mail_loop():
    while True:
        time.sleep(30)
        try: deliver_mail()
        except Exception: pass

# ---------------- 패스키(지문) ----------------
RP_ID = lambda: os.environ.get('WEBAUTHN_RP_ID', 'ama.example.com')
ORIGINS = lambda: [o for o in os.environ.get('WEBAUTHN_ORIGINS', 'https://ama.example.com').split(',') if o]
def wa_err(e): return ApiError(e.status, e.code, e.msg)
def new_challenge(cur, purpose, uid):
    ch = W.b64u(os.urandom(32)); R.ex(cur, 'INSERT INTO dbo.PasskeyChallenge(challengeHash, purpose, userId, createdAt, expiresAt) VALUES (%s,%s,%s,%s,%s)', (U.token_hash(ch), purpose, uid, ts(), ts(now() + dt.timedelta(minutes=5)))); return ch
def use_challenge(cur, ch, purpose, uid=None):
    R.ex(cur, 'SELECT purpose, userId, expiresAt, usedAt FROM dbo.PasskeyChallenge WHERE challengeHash=%s', (U.token_hash(ch),)); x = cur.fetchall()
    if not x or x[0][0] != purpose or x[0][3] is not None or str(x[0][2])[:23] < ts() or (uid and x[0][1] != uid): raise ApiError(400, 'BAD_CHALLENGE', '챌린지가 없거나 만료·사용되었습니다. 다시 시도하세요.')
    R.ex(cur, 'UPDATE dbo.PasskeyChallenge SET usedAt=%s WHERE challengeHash=%s AND usedAt IS NULL', (ts(), U.token_hash(ch)))
def client_challenge(cd_b64):
    try: return json.loads(W.unb64u(cd_b64)).get('challenge') or ''
    except Exception: raise ApiError(400, 'BAD_CLIENT_DATA', 'clientDataJSON이 올바르지 않습니다.')
def passkey_reg_options(h, cid):
    s = session(h, need_mfa=True)   # 비밀번호만 아는 공격자가 자기 패스키를 붙이지 못하도록 MFA 세션에서만 등록
    def f(cur):
        ch = new_challenge(cur, 'register', s['userId']); R.ex(cur, 'SELECT credId FROM dbo.PasskeyCredential WHERE userId=%s AND revokedAt IS NULL', (s['userId'],)); ex = [dict(type='public-key', id=x[0]) for x in cur.fetchall()]; return ch, ex
    ch, ex = R.tx(f)
    return 200, dict(publicKey=dict(challenge=ch, rp=dict(id=RP_ID(), name='AMA'), user=dict(id=W.b64u(s['userId'].encode()), name=s['username'], displayName=s['username']), pubKeyCredParams=[dict(type='public-key', alg=-7)], timeout=60000, attestation='none', excludeCredentials=ex, authenticatorSelection=dict(authenticatorAttachment='platform', residentKey='required', requireResidentKey=True, userVerification='required')))
def passkey_reg_verify(body, h, cid):
    s = session(h, need_mfa=True); r = body.get('response') or {}
    try:
        cdj = W.unb64u(r.get('clientDataJSON') or ''); ch = client_challenge(r.get('clientDataJSON') or ''); att = W.unb64u(r.get('attestationObject') or '')
        cred_id, point, sc = W.verify_registration(cdj, att, ch, RP_ID(), ORIGINS())
    except W.WaError as e: raise wa_err(e)
    label = (str(body.get('label') or '')[:60]).strip() or '내 기기'
    def f(cur):
        use_challenge(cur, ch, 'register', s['userId']); cid_s = W.b64u(cred_id)
        R.ex(cur, 'SELECT COUNT(*) FROM dbo.PasskeyCredential WHERE credId=%s', (cid_s,))
        if cur.fetchall()[0][0]: raise ApiError(409, 'PASSKEY_EXISTS', '이미 등록된 패스키입니다.')
        R.ex(cur, 'INSERT INTO dbo.PasskeyCredential(credId, userId, publicKey, signCount, label, createdAt) VALUES (%s,%s,%s,%s,%s,%s)', (cid_s, s['userId'], base64.b64encode(point).decode(), sc, label, ts())); A(cur, s['username'], 'PASSKEY_REGISTER', s['userId'], reason=label, cid=cid)
    R.tx(f); return 200, dict(registered=True, label=label)
def passkey_login_options(body, h, cid):
    ch = R.tx(lambda cur: new_challenge(cur, 'login', None)); return 200, dict(publicKey=dict(challenge=ch, rpId=RP_ID(), timeout=60000, userVerification='required', allowCredentials=[]))
def passkey_login_verify(body, h, cid):
    r = body.get('response') or {}; t0 = now()
    try:
        cdj = W.unb64u(r.get('clientDataJSON') or ''); ch = client_challenge(r.get('clientDataJSON') or ''); ad = W.unb64u(r.get('authenticatorData') or ''); sig = W.unb64u(r.get('signature') or ''); cred = str(body.get('id') or '')
    except W.WaError as e: raise wa_err(e)
    def f(cur):
        use_challenge(cur, ch, 'login')
        R.ex(cur, 'SELECT c.userId, c.publicKey, c.signCount, u.username, u.status, u.isAdmin, u.lockedUntil FROM dbo.PasskeyCredential c JOIN dbo.AppUser u ON u.userId=c.userId WHERE c.credId=%s AND c.revokedAt IS NULL', (cred,)); x = cur.fetchall()
        if not x or x[0][4] != 'active': A(cur, '-', 'PASSKEY_LOGIN_FAIL', cred[:40], reason='UNKNOWN_CREDENTIAL', cid=cid); return (401, 'INVALID_CREDENTIALS', '등록된 패스키가 아니거나 사용할 수 없는 계정입니다.')
        if x[0][6] is not None and str(x[0][6])[:23] > ts(t0): return (423, 'ACCOUNT_LOCKED', '로그인이 잠시 잠겨 있습니다.')
        try: sc = W.verify_assertion(cdj, ad, sig, base64.b64decode(x[0][1]), ch, RP_ID(), ORIGINS(), x[0][2] or 0)
        except W.WaError as e: A(cur, x[0][3], 'PASSKEY_LOGIN_FAIL', x[0][0], reason=e.code, cid=cid); return (e.status, e.code, e.msg)
        R.ex(cur, 'UPDATE dbo.PasskeyCredential SET signCount=%s, lastUsedAt=%s WHERE credId=%s', (sc, ts(t0), cred))
        tok, th = U.new_token(); R.ex(cur, 'INSERT INTO dbo.AppSession(tokenHash, userId, mfaVerified, createdAt, expiresAt) VALUES (%s,%s,1,%s,%s)', (th, x[0][0], ts(t0), ts(t0 + dt.timedelta(seconds=U.SESSION_S))))   # UV(지문)+소유 = 다중 요소
        A(cur, x[0][3], 'LOGIN_OK', x[0][0], reason='passkey', cid=cid); return (200, dict(token=tok, username=x[0][3], mfaVerified=True, mfaEnrolled=True, isAdmin=bool(x[0][5]), expiresAt=iso(t0 + dt.timedelta(seconds=U.SESSION_S))), None)
    r2 = R.tx(f)
    if r2[0] != 200: raise ApiError(r2[0], r2[1], r2[2])
    return 200, r2[1]
def passkey_list(h):
    s = session(h); r = R.tx(lambda cur: (R.ex(cur, 'SELECT credId, label, createdAt, lastUsedAt FROM dbo.PasskeyCredential WHERE userId=%s AND revokedAt IS NULL ORDER BY createdAt', (s['userId'],)), cur.fetchall())[1])
    return 200, dict(items=[dict(id=x[0], label=x[1], createdAt=str(x[2]), lastUsedAt=str(x[3]) if x[3] else None) for x in r])
def passkey_delete(body, h, cid):
    s = session(h, need_mfa=True); i = str(body.get('id') or '')
    def f(cur):
        R.ex(cur, 'UPDATE dbo.PasskeyCredential SET revokedAt=%s WHERE credId=%s AND userId=%s AND revokedAt IS NULL', (ts(), i, s['userId'])); A(cur, s['username'], 'PASSKEY_REVOKE', s['userId'], reason=i[:40], cid=cid)
    R.tx(f); return 200, dict(revoked=True)

# ---------------- 계정 관리(관리자) · 내 정보 ----------------
def list_users(h, qs):
    admin_session(h); st = (qs.get('state') or ['all'])[0]
    if st not in ('all', 'pending', 'active', 'rejected', 'disabled'): raise ApiError(400, 'BAD_REQUEST', 'state가 올바르지 않습니다.')
    sql = 'SELECT username, displayName, email, status, grade, mfaEnrolled, createdAt, decidedBy, (SELECT COUNT(*) FROM dbo.PasskeyCredential p WHERE p.userId=u.userId AND p.revokedAt IS NULL) FROM dbo.AppUser u' + ('' if st == 'all' else ' WHERE status=%s') + ' ORDER BY createdAt'
    r = R.tx(lambda cur: (R.ex(cur, sql, () if st == 'all' else (st,)), cur.fetchall())[1])
    return 200, dict(items=[dict(username=x[0], displayName=x[1], email=x[2], state=x[3], grade=x[4], mfaEnrolled=bool(x[5]), createdAt=str(x[6]), decidedBy=x[7], passkeys=x[8]) for x in r], grades=U.GRADE_LABEL)
def user_op(body, h, cid, op):
    """status/reset-mfa/reset-password: 관리자(MFA 세션)만, 자기 자신 대상 불가. 대상의 기존 세션은 모두 폐기한다."""
    s = admin_session(h); un = str(body.get('username') or ''); new_pw = None
    if op == 'status' and body.get('status') not in ('active', 'disabled'): raise ApiError(400, 'BAD_REQUEST', 'status는 active/disabled입니다.')
    if op == 'reset-password': new_pw = secrets_pw()
    def f(cur):
        R.ex(cur, 'SELECT userId, status FROM dbo.AppUser WHERE username=%s', (un,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 사용자가 없습니다.')
        if x[0][0] == s['userId']: raise ApiError(403, 'SEPARATION_OF_DUTY', '자기 자신의 계정은 이 화면에서 바꿀 수 없습니다.')
        if x[0][1] in ('pending', 'rejected'): raise ApiError(409, 'NOT_ACTIVE_ACCOUNT', '가입 승인 전·거절된 계정입니다. 가입 승인 화면에서 처리하세요.')
        uid = x[0][0]
        if op == 'status': R.ex(cur, 'UPDATE dbo.AppUser SET status=%s WHERE userId=%s', (body['status'], uid))
        elif op == 'reset-mfa': R.ex(cur, 'UPDATE dbo.AppUser SET mfaEnrolled=0, mfaSecretEnc=NULL, mfaLastStep=0, failCount=0, lockedUntil=NULL WHERE userId=%s', (uid,)); R.ex(cur, 'UPDATE dbo.PasskeyCredential SET revokedAt=%s WHERE userId=%s AND revokedAt IS NULL', (ts(), uid))
        else:
            ph, salt = U.hash_password(new_pw); R.ex(cur, 'UPDATE dbo.AppUser SET pwHash=%s, pwSalt=%s, failCount=0, lockedUntil=NULL WHERE userId=%s', (ph, salt, uid))
        R.ex(cur, 'UPDATE dbo.AppSession SET revokedAt=%s WHERE userId=%s AND revokedAt IS NULL', (ts(), uid)); A(cur, s['username'], 'USER_' + op.upper().replace('-', '_'), uid, reason=str(body.get('status') or ''), cid=cid)
    R.tx(f); out = dict(username=un, op=op)
    if op == 'status': out['status'] = body['status']
    if new_pw: out['temporaryPassword'] = new_pw; out['note'] = '이 임시 비밀번호는 한 번만 표시됩니다. 사용자가 로그인 후 바로 변경하도록 안내하세요.'
    return 200, out
def secrets_pw():
    import secrets as sc, string
    al = string.ascii_letters.replace('l', '').replace('I', '').replace('O', '') + '23456789'   # 혼동되는 글자 제외
    return ''.join(sc.choice(al) for _ in range(14))
def profile_update(body, h, cid):
    s = session(h); sets, vals = [], []
    try:
        if body.get('email') is not None: sets.append('email=%s'); vals.append(U.check_email(body['email']))
    except U.AuthError as e: raise u_err(e)
    if body.get('displayName') is not None: sets.append('displayName=%s'); vals.append((str(body['displayName'])[:60]).strip() or None)
    if not sets: raise ApiError(400, 'BAD_REQUEST', '바꿀 값이 없습니다.')
    def f(cur):
        if body.get('email') is not None:
            R.ex(cur, 'SELECT COUNT(*) FROM dbo.AppUser WHERE LOWER(email)=%s AND userId<>%s', (U.check_email(body['email']), s['userId']))
            if cur.fetchall()[0][0]: raise ApiError(409, 'EMAIL_TAKEN', '이미 다른 계정에서 사용 중인 이메일입니다.')
        R.ex(cur, 'UPDATE dbo.AppUser SET ' + ', '.join(sets) + ' WHERE userId=%s', tuple(vals) + (s['userId'],)); A(cur, s['username'], 'PROFILE_UPDATE', s['userId'], cid=cid)
    R.tx(f); return me(h)
def decide(body, h, cid):
    """API08: 로그인한 MFA 세션 + approve 권한이 있어야 한다. 신청자≠승인자·expectedVersion CAS·digest 재검증은 K.decide 규칙(미충족은 거절·감사)."""
    s = session(h, need_mfa=True); rid = str(body.get('requestId') or ''); d = body.get('decision'); ev = body.get('expectedVersion')
    if d not in ('approve', 'reject', 'cancel') or not isinstance(ev, int): raise ApiError(400, 'BAD_REQUEST', 'requestId, decision(approve/reject/cancel), expectedVersion(정수)이 필요합니다.')
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'requestId 형식이 올바르지 않습니다.')
    pre = R.tx(lambda cur: (R.ex(cur, 'SELECT intentRef, intentDigest FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)), cur.fetchall())[1])
    fresh = VERIFY(json.loads(pre[0][0]), pre[0][1]) if pre and pre[0][0] and d == 'approve' else None   # 승인 직전 S04 재조회(그 사이 intent가 바뀌었거나 조회 실패면 승인 불가)
    def f(cur):
        if not has_grant(cur, s['userId'], 'approve'):
            A(cur, s['username'], 'APPROVAL_DECIDE_DENY', rid, reason='NO_GRANT', cid=cid); return 403, 'FORBIDDEN', '승인 권한이 없습니다.'
        R.ex(cur, 'SELECT state, requester, rev, digestVerified, approvalVersion, reasonUpdatedAt FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)); x = cur.fetchall()
        if not x: return 404, 'NOT_FOUND', '해당 신청이 없습니다.'
        if 'reasonSeen' in body and (body.get('reasonSeen') or None) != (iso(x[0][5]) if x[0][5] else None):   # 승인자가 본 사유가 그 사이 수정되었으면 결정하지 않고 다시 확인하게 한다
            A(cur, s['username'], 'APPROVAL_DECIDE_DENY', rid, reason='REASON_CHANGED', cid=cid); return 409, 'REASON_CHANGED', '신청 사유가 수정되었습니다. 화면을 새로 고쳐 사유를 다시 확인한 뒤 결정해 주세요.'
        dv = bool(x[0][3]) if fresh is None else fresh
        if fresh is not None: R.ex(cur, 'UPDATE dbo.ApprovalRequest SET digestVerified=%s WHERE requestId=%s', (1 if fresh else 0, rid))
        self_ok = x[0][1] == s['username'] and has_grant(cur, s['userId'], 'admin')   # 관리자는 본인 신청도 결정할 수 있다(2026-11-01 사용자 결정). 나머지 검증(MFA·digest·버전)은 그대로.
        try: to = K.decide(x[0][0], None if self_ok else x[0][1], s['username'], d, True, dv, ev, x[0][2])
        except K.Reject as e:
            A(cur, s['username'], 'APPROVAL_DECIDE_DENY', rid, reason=e.code, cid=cid); return e.status, e.code, e.msg
        av = x[0][4] + (1 if to == 'approved' else 0)
        R.ex(cur, 'UPDATE dbo.ApprovalRequest SET state=%s, rev=rev+1, approvalVersion=%s, updatedAt=%s WHERE requestId=%s AND rev=%s', (to, av, ts(), rid, x[0][2]))
        R.ex(cur, 'INSERT INTO dbo.ApprovalDecision(decisionId, requestId, actor, mfaEvidenceRef, decision, reasonCode, approvalVersion, decidedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', (str(uuid.uuid4()), rid, s['username'], 'session-mfa:' + U.token_hash(s['token'])[:16], d, (body.get('reasonCode') or '')[:60] or None, av, ts()))
        A(cur, s['username'], 'APPROVAL_DECIDE', rid, before=str(x[0][2]), after=str(x[0][2] + 1), reason=d + (':ADMIN_SELF' if self_ok else ''), cid=cid); return 200, to, av
    r = R.tx(f)
    if r[0] != 200: raise ApiError(r[0], r[1], r[2])
    return 200, dict(requestId=rid, state=r[1], approvalVersion=r[2], note='승인은 permit·예약·실행이 아닙니다.')
def decide_closed(body, h, cid):
    """API08: MFA를 검증할 인증 문맥이 없다 → 승인·반려 모두 처리하지 않고 시도를 감사에 남긴다(신청 상태 불변)."""
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]; rid = str(body.get('requestId') or '')
    def f(cur):
        A(cur, actor, 'APPROVAL_DECIDE_ATTEMPT', rid or '-', reason='AUTH_CONTEXT_UNAVAILABLE'); return None
    R.tx(f); raise ApiError(503, 'AUTH_CONTEXT_UNAVAILABLE', '승인자 신원·MFA 증거를 검증할 인증 문맥이 없어 승인/반려를 처리하지 않습니다. 신청은 pending으로 유지됩니다.', True)
class KvSigner:
    """Key Vault EC P-256 키로 digest 서명·검증(키 원문 미취득). KEY_URL은 PERMIT_SIGN_KEY_URL. 응답의 kid(버전 포함)를 keyRef로 기록한다."""
    alg = 'ES256'
    def __init__(self, key_url): self.key = key_url.rstrip('/')
    def _tok(self):
        ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=https://vault.azure.net&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
    def _post(self, url, body):
        return json.loads(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(body).encode(), method='POST', headers={'Authorization': 'Bearer ' + self._tok(), 'Content-Type': 'application/json'}), timeout=20).read())
    @staticmethod
    def b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    def sign(self, dg): r = self._post(self.key + '/sign?api-version=7.4', dict(alg=self.alg, value=self.b64(bytes.fromhex(dg)))); return r['value'], r['kid']
    def verify(self, dg, sig, kid): return self._post(kid + '/verify?api-version=7.4', dict(alg=self.alg, digest=self.b64(bytes.fromhex(dg)), value=sig)).get('value') is True
def get_signer():
    u = os.environ.get('PERMIT_SIGN_KEY_URL'); return KvSigner(u) if u else None
SIGNER_FACTORY = get_signer
PERMIT_TTL = dt.timedelta(minutes=15)
def permit_payload(p):
    """permit 서명 대상: 실행 결속에 필요한 값만 정규 JSON으로 묶어 SHA-256(S08이 같은 규칙으로 재계산해 검증)."""
    doc = dict(profile='permit-sign-v1', permitId=p['permitId'], requestId=p['requestId'], operationKey=p['operationKey'], intentDigest=p['intentDigest'], approvalVersion=p['approvalVersion'], authorityVersion=p['authorityVersion'], reservationId=p['reservationId'], amountMinor=p['amountMinor'], currency=p['currency'], expiresAt=p['expiresAt'])
    return sha(canon(doc))
def create_limit_account(body, h, cid):
    s = admin_session(h)
    try: amt = int(body.get('capMinor')); ps = dt.datetime.strptime(str(body.get('periodStart'))[:19], '%Y-%m-%dT%H:%M:%S'); pe = dt.datetime.strptime(str(body.get('periodEnd'))[:19], '%Y-%m-%dT%H:%M:%S')
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'capMinor(정수), periodStart/periodEnd(YYYY-MM-DDTHH:MM:SS)가 필요합니다.')
    cur_ = str(body.get('currency') or ''); scope = str(body.get('principalScope') or '')[:120]; act = str(body.get('action') or '')[:60]
    if cur_ not in K.EXP or not scope or not act or amt < 0 or not ps < pe: raise ApiError(400, 'BAD_REQUEST', '통화·범위·action·기간·한도가 올바르지 않습니다.')
    aid = str(uuid.uuid4())
    R.tx(lambda cur: (R.ex(cur, 'INSERT INTO dbo.LimitAccount(accountId, country, orgId, principalScope, action, currency, periodStart, periodEnd, capMinor, heldMinor, settledMinor, rev) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,1)', (aid, COUNTRY, ORG, scope, act, cur_, ts(ps), ts(pe), amt)), A(cur, s['username'], 'LIMIT_ACCOUNT_CREATE', aid, reason='%s %s' % (cur_, amt), cid=cid)))
    return 201, dict(accountId=aid, principalScope=scope, action=act, currency=cur_, capMinor=amt)
def permit(body, h, cid):
    """API: POST /v1/permits (S07-P2). 건별 사람 승인(D12 결정)된 신청에 한해 한도 예약 + 서명된 permit을 만든다. 실행은 S08 몫이며 현재 실거래 없음(모의)."""
    s = session(h, need_mfa=True); rid = str(body.get('requestId') or ''); aid = str(body.get('accountId') or ''); eav = body.get('expectedApprovalVersion')
    if not isinstance(eav, int): raise ApiError(400, 'BAD_REQUEST', 'requestId, accountId, expectedApprovalVersion(정수)이 필요합니다.')
    try: uuid.UUID(rid); uuid.UUID(aid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'requestId/accountId 형식이 올바르지 않습니다.')
    signer = SIGNER_FACTORY()
    if signer is None: R.tx(lambda cur: A(cur, s['username'], 'PERMIT_ISSUE_DENY', rid, reason='SIGNER_NOT_CONFIGURED', cid=cid)); raise ApiError(422, 'PERMIT_ISSUANCE_BLOCKED', 'permit 서명 키가 구성되지 않아 발급하지 않습니다(한도 예약도 만들지 않음).')
    pre = R.tx(lambda cur: (R.ex(cur, 'SELECT intentRef, intentDigest FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)), cur.fetchall())[1])
    fresh = VERIFY(json.loads(pre[0][0]), pre[0][1]) if pre and pre[0][0] else False   # 발급 직전 S04 재조회
    t0 = now(); pid = str(uuid.uuid4()); resid = str(uuid.uuid4()); exp = t0 + PERMIT_TTL
    def f(cur):
        def deny(code, msg, st=409): A(cur, s['username'], 'PERMIT_ISSUE_DENY', rid, reason=code, cid=cid); return (st, code, msg)
        if not has_grant(cur, s['userId'], 'permit.issue'): return deny('FORBIDDEN', 'permit 발급 권한이 없습니다.', 403)
        R.ex(cur, 'SELECT state, requester, approvalVersion, operationKey, intentDigest, amountMinor, currency, expiresAt, action, rev FROM dbo.ApprovalRequest WHERE requestId=%s', (rid,)); x = cur.fetchall()
        if not x: return deny('NOT_FOUND', '해당 신청이 없습니다.', 404)
        st, requester, av, opk, idg, amt, ccy, rexp, action, rrev = x[0]
        if requester == s['username'] and not has_grant(cur, s['userId'], 'admin'): return deny('SEPARATION_OF_DUTY', '신청자는 자기 신청의 permit을 발급할 수 없습니다.', 403)   # 관리자 예외(2026-11-01 사용자 결정)
        if st != 'approved' or av != eav: return deny('NOT_APPROVED', '승인된 최신 승인 버전이 아닙니다.')
        if str(rexp)[:23] < ts(t0): return deny('REQUEST_EXPIRED', '신청의 유효기간이 지났습니다.')
        if not fresh: return deny('BLOCKED_DEPENDENCY', '발급 직전 S04 intent 재검증에 실패했습니다.', 503)
        R.ex(cur, 'SELECT COUNT(*) FROM dbo.ExecutionPermit WHERE requestId=%s', (rid,))
        if cur.fetchall()[0][0]: return deny('PERMIT_EXISTS', '이 신청에는 이미 permit이 있습니다(재발급 없음).')
        if amt is None: return deny('AMOUNT_REQUIRED', '금액이 없는 신청에는 한도를 예약할 수 없습니다.', 422)
        R.ex(cur, 'SELECT principalScope, action, currency, periodStart, periodEnd, capMinor, heldMinor, settledMinor, rev FROM dbo.LimitAccount WHERE accountId=%s', (aid,)); y = cur.fetchall()
        if not y: return deny('NOT_FOUND', '한도 계정이 없습니다.', 404)
        sc, ac, cu, ps, pe, cap, held, sett, arev = y[0]
        if ac != action or cu != ccy or not (str(ps)[:23] <= ts(t0) < str(pe)[:23]): return deny('LIMIT_ACCOUNT_MISMATCH', '한도 계정의 action·통화·기간이 신청과 맞지 않습니다.', 422)
        try: new = K.reserve(dict(cap=cap, held=held, settled=sett, rev=arev), amt)
        except K.Reject as e: return deny(e.code, e.msg, e.status)
        R.ex(cur, 'UPDATE dbo.LimitAccount SET heldMinor=%s, rev=%s WHERE accountId=%s AND rev=%s', (new['held'], new['rev'], aid, arev))
        R.ex(cur, 'SELECT heldMinor, rev FROM dbo.LimitAccount WHERE accountId=%s', (aid,)); z = cur.fetchall()[0]
        if z[1] != new['rev']: raise ApiError(409, 'VERSION_CONFLICT', '한도 계정이 동시에 바뀌었습니다. 다시 시도하세요.', True)
        R.ex(cur, 'INSERT INTO dbo.LimitReservation(reservationId, requestId, permitId, accountId, intentDigest, reservedMinor, state, expiresAt, reconciliationVersion, rev) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,1)', (resid, rid, pid, aid, idg, amt, 'held', ts(exp)))
        R.ex(cur, "INSERT INTO dbo.ExecutionPermit(permitId, operationKey, requestId, reservationId, intentDigest, state, useProhibited, operationHold, authorityVersion, createdAt, expiresAt) VALUES (%s,%s,%s,%s,%s,'signing',1,0,1,%s,%s)", (pid, opk, rid, resid, idg, ts(t0), ts(exp)))
        A(cur, s['username'], 'PERMIT_RESERVED', pid, reason='account=%s amount=%d' % (aid[:8], amt), cid=cid); return (200, dict(opk=opk, idg=idg, amt=amt, ccy=ccy, av=av), None)
    r = R.tx(f)
    if r[0] != 200: raise ApiError(r[0], r[1], r[2])
    info = r[1]; p = dict(permitId=pid, requestId=rid, operationKey=info['opk'], intentDigest=info['idg'], approvalVersion=info['av'], authorityVersion=1, reservationId=resid, amountMinor=info['amt'], currency=info['ccy'], expiresAt=iso(exp)); dg = permit_payload(p)
    try:
        sig, kid = signer.sign(dg); ok = signer.verify(dg, sig, kid)
    except Exception:   # 서명 응답 유실·오류: 자동 재서명 없음. permit은 signing(사용 불가)·한도는 held 유지, 조회·대사로 처리
        R.tx(lambda cur: A(cur, s['username'], 'PERMIT_SIGN_UNKNOWN', pid, reason='sign-error', cid=cid)); return 202, dict(permitId=pid, state='signing', reservationId=resid, note='서명 결과를 확인하지 못했습니다. 자동 재서명은 하지 않으며 permit은 사용할 수 없습니다.')
    def g(cur):
        if ok: R.ex(cur, "UPDATE dbo.ExecutionPermit SET state='active', useProhibited=0, signature=%s, keyRef=%s, signedDigest=%s WHERE permitId=%s AND state='signing'", (sig, kid[:200], dg, pid)); A(cur, s['username'], 'PERMIT_ISSUED', pid, reason='active', cid=cid)
        else: R.ex(cur, "UPDATE dbo.ExecutionPermit SET state='blocked' WHERE permitId=%s AND state='signing'", (pid,)); A(cur, s['username'], 'PERMIT_SIGN_BAD', pid, reason='verify-failed', cid=cid)
    R.tx(g)
    if not ok: raise ApiError(409, 'SIGNATURE_INVALID', '서명 검증에 실패해 permit을 사용할 수 없습니다(blocked). 한도는 held로 남습니다.')
    return 201, dict(permitId=pid, state='active', reservationId=resid, expiresAt=p['expiresAt'], intentDigest=p['intentDigest'], algorithm=signer.alg, keyRef=kid, signature=sig, note='permit은 실행 허가가 아니라 S08 실행 전 확인용 증표입니다. 현재 실거래 경로는 없습니다.')
def verify_permit(body, cid):
    """POST /v1/permits/verify (S08 내부 호출). 로그인 없이 호출되지만 읽기 전용 불리언 판정만 한다: permit이 DB에서 active·사용 금지 아님·서명 일치이고 Key Vault 서명 검증을 통과해야 valid."""
    signer = SIGNER_FACTORY()
    if signer is None: raise ApiError(503, 'SIGNER_NOT_CONFIGURED', 'permit 서명 키가 구성되지 않았습니다.')
    F = ('permitId', 'requestId', 'operationKey', 'intentDigest', 'approvalVersion', 'authorityVersion', 'reservationId', 'amountMinor', 'currency', 'expiresAt', 'signature', 'keyRef')
    if not isinstance(body, dict) or any(body.get(k) in (None, '') for k in F): return 200, dict(valid=False, reason='MALFORMED')
    if not str(body['keyRef']).startswith(signer.key + '/'): return 200, dict(valid=False, reason='KEY_UNTRUSTED')
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT state, useProhibited, signature, intentDigest, operationKey, requestId, reservationId FROM dbo.ExecutionPermit WHERE permitId=%s', (str(body['permitId']),)), cur.fetchall())[1])
    if not r: return 200, dict(valid=False, reason='UNKNOWN_PERMIT')
    x = r[0]
    if x[0] != 'active' or x[1]: return 200, dict(valid=False, reason='NOT_ACTIVE')
    if x[2] != body['signature'] or x[3] != body['intentDigest'] or x[4] != body['operationKey'] or x[5] != body['requestId'] or x[6] != body['reservationId']: return 200, dict(valid=False, reason='RECORD_MISMATCH')
    dg = permit_payload(body)
    try: good = signer.verify(dg, body['signature'], body['keyRef'])
    except Exception: raise ApiError(503, 'VERIFY_UNAVAILABLE', '서명 검증을 완료하지 못했습니다.', True)
    return 200, dict(valid=bool(good), reason='' if good else 'BAD_SIGNATURE')
def claim_permit(body, cid):
    """POST /v1/permits/claim (S08 내부 호출): permit 1회 사용 확정. active → claimed(claimedBy=executionId). 같은 claimant 재호출은 replay 성공, 다른 claimant·비활성·만료·사용 금지는 409.
    한도 정산은 별도 단계이며 이 호출은 한도를 확정·해제하지 않는다."""
    pid = str((body or {}).get('permitId') or ''); who = str((body or {}).get('claimant') or '')
    try: uuid.UUID(pid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'permitId 형식이 올바르지 않습니다.')
    if not who or len(who) > 60: raise ApiError(400, 'BAD_REQUEST', 'claimant(1~60자)가 필요합니다.')
    def f(cur):
        R.ex(cur, 'SELECT state, useProhibited, claimedBy, expiresAt FROM dbo.ExecutionPermit WHERE permitId=%s', (pid,)); r = cur.fetchall()
        if not r: A(cur, 'S08', 'PERMIT_CLAIM_DENIED', pid, reason='UNKNOWN_PERMIT', cid=cid); return 409, 'UNKNOWN_PERMIT'
        st, up, by, ex = r[0]
        if st == 'claimed': 
            if by == who: A(cur, 'S08', 'PERMIT_CLAIM_REPLAY', pid, reason=who, cid=cid); return 200, 'REPLAY'
            A(cur, 'S08', 'PERMIT_CLAIM_DENIED', pid, reason='ALREADY_CLAIMED', cid=cid); return 409, 'ALREADY_CLAIMED'
        if st != 'active' or up: A(cur, 'S08', 'PERMIT_CLAIM_DENIED', pid, reason='NOT_ACTIVE', cid=cid); return 409, 'NOT_ACTIVE'
        if ex is not None and str(ex)[:19].replace('T', ' ') <= ts()[:19]: A(cur, 'S08', 'PERMIT_CLAIM_DENIED', pid, reason='EXPIRED', cid=cid); return 409, 'EXPIRED'
        R.ex(cur, "UPDATE dbo.ExecutionPermit SET state='claimed', claimedBy=%s, claimedAt=%s WHERE permitId=%s AND state='active' AND useProhibited=0", (who, ts(), pid))
        if cur.rowcount != 1: return 409, 'RACE'
        A(cur, 'S08', 'PERMIT_CLAIMED', pid, reason=who, cid=cid); return 200, 'CLAIMED'
    c, why = R.tx(f)
    if c != 200: raise ApiError(409, why, 'permit 사용을 확정할 수 없습니다(%s).' % why)
    return 200, dict(claimed=True, replay=(why == 'REPLAY'), permitId=pid, claimedBy=who)
def get_permit(pid, h):
    session(h)
    try: uuid.UUID(pid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'permitId 형식이 올바르지 않습니다.')
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT permitId, requestId, operationKey, reservationId, intentDigest, state, useProhibited, authorityVersion, createdAt, expiresAt, signature, keyRef, signedDigest FROM dbo.ExecutionPermit WHERE permitId=%s', (pid,)), cur.fetchall())[1])
    if not r: raise ApiError(404, 'NOT_FOUND', '해당 permit이 없습니다.')
    x = r[0]; return 200, dict(permitId=x[0], requestId=x[1], operationKey=x[2], reservationId=x[3], intentDigest=x[4], state=x[5], useProhibited=bool(x[6]), authorityVersion=x[7], createdAt=str(x[8]), expiresAt=str(x[9])[:23].replace(' ', 'T') + 'Z', signature=x[10], keyRef=x[11], signedDigest=x[12])
def cases(h, qs):
    """거래 건별 진행 현황(읽기 전용): 정책 평가 → 승인 신청 → 승인 결정 → 한도 예약 → permit → (exec-api) 실행·영수증. 로그인한 사용자만. 최신 50건."""
    session(h)
    def f(cur):
        R.ex(cur, 'SELECT r.requestId, r.state, r.operationKey, r.action, r.purpose, r.amountMinor, r.currency, r.requester, r.createdAt, r.expiresAt, e.decision, e.reasonCode, e.policyVersion, e.proposeOnly FROM dbo.ApprovalRequest r JOIN dbo.PolicyEvaluation e ON e.evaluationId=r.evaluationId ORDER BY r.createdAt DESC'); rq = cur.fetchall()[:50]
        if not rq: return rq, [], [], [], []
        ids = [x[0] for x in rq]; ph = ','.join(['%s'] * len(ids))
        R.ex(cur, 'SELECT requestId, actor, decision, reasonCode, decidedAt FROM dbo.ApprovalDecision WHERE requestId IN (' + ph + ') ORDER BY decidedAt', tuple(ids)); dc = cur.fetchall()
        R.ex(cur, 'SELECT requestId, permitId, state, createdAt FROM dbo.ExecutionPermit WHERE requestId IN (' + ph + ')', tuple(ids)); pm = cur.fetchall()
        R.ex(cur, 'SELECT requestId, state, reservedMinor FROM dbo.LimitReservation WHERE requestId IN (' + ph + ')', tuple(ids)); rs = cur.fetchall()
        R.ex(cur, 'SELECT requestId, requestReason, reasonUpdatedAt FROM dbo.ApprovalRequest WHERE requestId IN (' + ph + ')', tuple(ids)); rr = {m[0]: (m[1], iso(m[2]) if m[2] else None) for m in cur.fetchall()}
        return rq, dc, pm, rs, rr
    rq, dc, pm, rs, rr = R.tx(f); ex = {}
    base = os.environ.get('EXEC_API_URL')
    if base and pm:
        try:
            q = urllib.parse.quote(','.join(p[1] for p in pm[:50]), safe=',')
            for e in json.loads(urllib.request.urlopen('%s/v1/executions?permitIds=%s' % (base.rstrip('/'), q), timeout=8).read()).get('items', []): ex[e['permitId']] = e
        except Exception: ex = None   # 실행 서비스 조회 실패는 '실행 없음'이 아니라 '알 수 없음'으로 표시한다
    intents = {}
    pb = os.environ.get('PROC_API_URL')
    if pb and rq:
        try:
            def _isuuid(v):
                try: uuid.UUID(v); return True
                except Exception: return False
            opids = ','.join(sorted({x[2].split('|')[-1] for x in rq if x[2] and _isuuid(x[2].split('|')[-1])}))   # 시험 건의 비UUID 키는 건너뜀(전체 실패 방지)
            for it in json.loads(urllib.request.urlopen('%s/v1/intent-summaries?ops=%s' % (pb.rstrip('/'), urllib.parse.quote(opids, safe=',')), timeout=8).read()).get('items', []): intents[it['businessOperationId']] = it
        except Exception: intents = {}   # 요약을 못 읽어도 건 목록은 그대로(요약만 비움)
    items = []
    for x in rq:
        p = next((dict(permitId=m[1], state=m[2], createdAt=iso(m[3])) for m in pm if m[0] == x[0]), None); r_ = next((dict(state=m[1], reservedMinor=m[2]) for m in rs if m[0] == x[0]), None)
        items.append(dict(intent=intents.get((x[2] or '').split('|')[-1]), reason=(rr.get(x[0]) or (None, None))[0], reasonUpdatedAt=(rr.get(x[0]) or (None, None))[1], requestId=x[0], state=x[1], operationKey=x[2], action=x[3], purpose=x[4], amountMinor=x[5], currency=x[6], requester=x[7], createdAt=iso(x[8]), expiresAt=iso(x[9]),
                          policy=dict(decision=x[10], reasonCode=x[11], version=x[12], proposeOnly=bool(x[13])), decisions=[dict(actor=d[1], decision=d[2], reasonCode=d[3], decidedAt=iso(d[4])) for d in dc if d[0] == x[0]], reservation=r_, permit=p,
                          execution=(None if ex is None else (ex.get(p['permitId']) if p else None)), executionKnown=ex is not None))
    return 200, dict(items=items, simulated=True)
def accounts():
    rows = R.tx(lambda cur: (R.ex(cur, 'SELECT accountId, principalScope, action, currency, periodStart, periodEnd, capMinor, heldMinor, settledMinor, rev FROM dbo.LimitAccount ORDER BY periodStart'), cur.fetchall())[1])
    return dict(items=[dict(accountId=r[0], principalScope=r[1], action=r[2], currency=r[3], periodStart=iso(r[4]), periodEnd=iso(r[5]), capMinor=r[6], heldMinor=r[7], settledMinor=r[8], rev=r[9]) for r in rows])
def route(m, p, qs, body, h, cid):
    if m == 'POST' and p == '/v1/policy-evaluations': return policy_eval(body, h, cid)
    if m == 'POST' and p == '/v1/approval-requests': return create_request(body, h, cid)
    if m == 'POST' and re.fullmatch(r'/v1/approval-requests/[^/]+/reason', p): return update_reason(p.split('/')[-2], body, h, cid)
    if m == 'GET' and p.startswith('/v1/approval-requests/'): return 200, get_request(p.split('/')[-1])
    if m == 'POST' and p == '/v1/approval-decisions': return decide(body, h, cid)
    if m == 'POST' and p == '/v1/auth/register': return register(body, h, cid)
    if m == 'POST' and p == '/v1/auth/signup': return signup(body, h, cid)
    if m == 'GET' and p == '/v1/admin/signups': return list_signups(h, qs)
    if m == 'POST' and p == '/v1/admin/signups/decision': return signup_decision(body, h, cid)
    if m == 'POST' and p == '/v1/admin/users/grade': return set_grade(body, h, cid)
    if p == '/v1/admin/settings/notify-email' and m in ('GET', 'POST'): return notify_setting(body, h, cid, m == 'POST')
    if m == 'GET' and p == '/v1/admin/mail-status': return mail_status(h)
    if m == 'GET' and p == '/v1/admin/users': return list_users(h, qs)
    if m == 'POST' and p == '/v1/admin/users/status': return user_op(body, h, cid, 'status')
    if m == 'POST' and p == '/v1/admin/users/reset-mfa': return user_op(body, h, cid, 'reset-mfa')
    if m == 'POST' and p == '/v1/admin/users/reset-password': return user_op(body, h, cid, 'reset-password')
    if m == 'POST' and p == '/v1/auth/profile': return profile_update(body, h, cid)
    if m == 'POST' and p == '/v1/auth/passkey/register/options': return passkey_reg_options(h, cid)
    if m == 'POST' and p == '/v1/auth/passkey/register/verify': return passkey_reg_verify(body, h, cid)
    if m == 'POST' and p == '/v1/auth/passkey/login/options': return passkey_login_options(body, h, cid)
    if m == 'POST' and p == '/v1/auth/passkey/login/verify': return passkey_login_verify(body, h, cid)
    if m == 'GET' and p == '/v1/auth/passkeys': return passkey_list(h)
    if m == 'POST' and p == '/v1/auth/passkey/delete': return passkey_delete(body, h, cid)
    if m == 'POST' and p == '/v1/auth/password': return change_password(body, h, cid)
    if m == 'POST' and p == '/v1/admin/users': return admin_create_user(body, h, cid)
    if m == 'POST' and p == '/v1/auth/login': return login(body, h, cid)
    if m == 'GET' and p == '/v1/auth/me': return me(h)
    if m == 'POST' and p == '/v1/auth/mfa/enroll': return mfa_enroll(h, cid)
    if m == 'POST' and p == '/v1/auth/mfa/confirm': return mfa_confirm(body, h, cid)
    if m == 'POST' and p == '/v1/auth/logout': return logout(h, cid)
    if m == 'POST' and p == '/v1/admin/grants': return grant(body, h, cid)
    if m == 'POST' and p == '/v1/permits/verify': return verify_permit(body, cid)
    if m == 'POST' and p == '/v1/permits/claim': return claim_permit(body, cid)
    if m == 'POST' and p == '/v1/permits': return permit(body, h, cid)
    if m == 'GET' and p == '/v1/limit-accounts': return 200, accounts()
    if m == 'GET' and p == '/v1/cases': return cases(h, qs)
    if m == 'POST' and p == '/v1/admin/limit-accounts': return create_limit_account(body, h, cid)
    if m == 'GET' and p.startswith('/v1/permits/') and len(p.split('/')) == 4: return get_permit(p.split('/')[3], h)
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.ApprovalRequest), (SELECT COUNT(*) FROM dbo.PolicyEvaluation), (SELECT COUNT(*) FROM dbo.ApprovalAudit)'), cur.fetchall()[0])[1])
    ml = R.tx(lambda cur: (R.ex(cur, 'SELECT state, COUNT(*) FROM dbo.MailOutbox GROUP BY state'), cur.fetchall())[1])
    le = R.tx(lambda cur: (R.ex(cur, "SELECT TOP 1 lastError, attempts FROM dbo.MailOutbox WHERE lastError IS NOT NULL ORDER BY createdAt DESC") if R.kind != 'sqlite' else R.ex(cur, 'SELECT lastError, attempts FROM dbo.MailOutbox WHERE lastError IS NOT NULL ORDER BY createdAt DESC LIMIT 1'), cur.fetchall())[1])
    return dict(version=VERSION, db=dict(kind=R.kind, requests=s[0], evaluations=s[1], audits=s[2], errors=R.err, last_err=R.last_err), mail=dict(sender='configured' if mailer_ready() else 'not-configured', lastError=(le[0][0] if le else None), lastAttempts=(le[0][1] if le else None), **{x[0]: x[1] for x in ml}), mode='propose-only(건별 사람 승인 · permit 닫힘)', **STATS)
def main():
    global R
    R = sql_repo(); threading.Thread(target=mail_loop, daemon=True).start(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
