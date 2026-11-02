"""S07 자체 사용자 원장 인증(사용자 결정 2026-10-31: Entra 대신 자체 로그인 + MFA 등록). 순수 로직: 비밀번호 해시(scrypt)·TOTP(RFC 6238)·MFA 비밀 암호화(AES-GCM)·세션 토큰 해시.
계정 생성만으로 권한은 생기지 않는다(권한은 UserGrant). 비밀번호·MFA 비밀·세션 토큰 원문은 저장·로그하지 않는다."""
import hashlib, hmac, os, base64, struct, time, secrets, re
class AuthError(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
USER_RE = re.compile(r'^[a-z0-9][a-z0-9._-]{2,39}$'); MAX_FAIL = 5; LOCK_S = 900; SESSION_S = 8 * 3600; PW_MIN = 8
def check_username(u):
    if not isinstance(u, str) or not USER_RE.match(u): raise AuthError(400, 'BAD_USERNAME', '아이디는 소문자·숫자·. _ - 3~40자입니다.')
    return u
def check_password(p):
    if not isinstance(p, str) or len(p) < PW_MIN or len(p) > 200: raise AuthError(400, 'WEAK_PASSWORD', '비밀번호는 %d자 이상이어야 합니다.' % PW_MIN)
    if len({c for c in p}) < 5 or p.lower() in ('passwordpassword', '123456789012'): raise AuthError(400, 'WEAK_PASSWORD', '너무 단순한 비밀번호입니다.')
    return p
def hash_password(p, salt=None):
    salt = salt or os.urandom(16); h = hashlib.scrypt(p.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32); return base64.b64encode(h).decode(), base64.b64encode(salt).decode()
def verify_password(p, h, salt): return hmac.compare_digest(base64.b64decode(h), hashlib.scrypt(p.encode(), salt=base64.b64decode(salt), n=2 ** 14, r=8, p=1, dklen=32))
def totp_secret(): return base64.b32encode(os.urandom(20)).decode().rstrip('=')
def totp_code(secret, step):
    k = base64.b32decode(secret + '=' * (-len(secret) % 8)); d = hmac.new(k, struct.pack('>Q', step), 'sha1').digest(); o = d[-1] & 15
    return '%06d' % ((struct.unpack('>I', d[o:o + 4])[0] & 0x7fffffff) % 1000000)
def totp_verify(secret, code, last_step=0, t=None, window=1):
    """성공 시 사용한 step을 돌려준다. 이미 쓴 step 이하는 재사용으로 거절(재생 방지)."""
    if not isinstance(code, str) or not re.fullmatch(r'\d{6}', code): return None
    cur = int((t if t is not None else time.time()) // 30)
    for s in range(cur - window, cur + window + 1):
        if s > last_step and hmac.compare_digest(totp_code(secret, s), code): return s
    return None
def otpauth(user, secret, issuer='AMA'): return 'otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30' % (issuer, user, secret, issuer)
def _aes(key_b64):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    k = base64.b64decode(key_b64)
    if len(k) != 32: raise AuthError(503, 'AUTH_KEY_UNAVAILABLE', 'MFA 비밀 암호화 키가 올바르지 않습니다.')
    return AESGCM(k)
def seal(key_b64, plain, aad):
    n = os.urandom(12); return base64.b64encode(n + _aes(key_b64).encrypt(n, plain.encode(), aad.encode())).decode()
def unseal(key_b64, blob, aad):
    b = base64.b64decode(blob); return _aes(key_b64).decrypt(b[:12], b[12:], aad.encode()).decode()
def new_token(): t = secrets.token_urlsafe(32); return t, hashlib.sha256(t.encode()).hexdigest()
def token_hash(t): return hashlib.sha256((t or '').encode()).hexdigest()

GRADES = {'viewer': [], 'operator': ['request'], 'approver': ['request', 'approve'], 'admin': ['request', 'approve', 'permit.issue', 'admin']}   # 등급 → 권한(UserGrant). permit 발급은 현재 서비스가 닫아 둠
GRADE_LABEL = {'viewer': '조회', 'operator': '운영(신청)', 'approver': '승인자', 'admin': '관리자'}
EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$')
def check_email(e):
    if not isinstance(e, str) or len(e) > 120 or not EMAIL_RE.match(e): raise AuthError(400, 'BAD_EMAIL', '이메일 형식이 올바르지 않습니다.')
    return e.strip().lower()
def check_grade(g):
    if g not in GRADES: raise AuthError(400, 'BAD_GRADE', '등급은 viewer/operator/approver/admin입니다.')
    return g
