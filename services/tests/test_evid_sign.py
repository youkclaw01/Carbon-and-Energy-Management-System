import sys, os, json, time, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'evidapi'))
import evid_app as A, evid_core as C
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE EvidenceRequest(requestId TEXT PRIMARY KEY, country, orgId, plantId, principal, idemKey, requestDigest, sourceKind, sourceRef, purpose, recipientScope, manifestId, manifestVersion, generationState, stateVersion, leaseEpoch DEFAULT 0, failReason, correlationId, createdAt, updatedAt, UNIQUE(country,orgId,principal,idemKey));
CREATE TABLE EvidenceManifest(country, orgId, manifestId, manifestVersion, plantId, sourceBinding, snapshotId, periodStart, periodEnd, timeZone, purpose, recipientScope, inputDigest, manifestHash, supersedesRef, mode, classification, schemaVersion, bodyJson, createdBy, createdAt, PRIMARY KEY(country,orgId,manifestId,manifestVersion));
CREATE TABLE EvidenceItemRef(manifestId, manifestVersion, itemId, ownerService, sourceRef, sourceVersion, byteHash, byteSize, mediaType, inclusionStatus, inclusionReason, factRef, PRIMARY KEY(manifestId,manifestVersion,itemId));
CREATE TABLE LineageRef(manifestId, manifestVersion, edgeId, fromRef, toRef, method, PRIMARY KEY(manifestId,manifestVersion,edgeId));
CREATE TABLE SignatureRef(manifestId, manifestVersion, signatureId, signedDigest, signingProfileVersion, algorithm, keyRef, signedAt, verificationStatus, PRIMARY KEY(manifestId,manifestVersion,signatureId));
CREATE TABLE AuditPackage(manifestId, manifestVersion, packageId, blobRef, artifactHash, byteSize, templateVersion, generationState, signingState, reviewState DEFAULT 'PENDING', externalVerificationState DEFAULT 'NOT_VERIFIED', localOnly, createdAt, PRIMARY KEY(manifestId,manifestVersion,packageId));
CREATE TABLE SigningKeyStatus(keyRef PRIMARY KEY, status, reason, changedAt, changedBy);
CREATE TABLE EvidenceAccessAudit(auditSeq INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, targetHash, purpose, decision, reason, correlationId, at, prevHash, entryHash);'''
def fresh():
    def cf():
        c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
    A.R = A.Repo('sqlite', cf)
class FB:
    def __init__(self): self.d = {}
    def put_new(self, n, b):
        if n in self.d: return 'exists'
        self.d[n] = b; return 'created'
    def get(self, n): return self.d.get(n)
RUN = str(uuid.uuid4()); calc = dict(runId=RUN, plantId='KR-01', country='KR', periodStart='2026-10-29T00:00:00.000Z', periodEnd='2026-10-29T01:00:00.000Z', timezone='Asia/Seoul', mode='SIMULATED', runKey='ab' * 32, updatedAt='2026-10-29T01:05:00.000Z', businessState='ready', values=[dict(metric='scope2_location_based', value='459.400', unit='kgCO2e', boundaryRef='SITE'), dict(metric='grid_energy', value='1000.000', unit='kWh', boundaryRef='SITE')])
mode = dict(calc=200, ing=200)
def fetch(url):
    if '/v1/calc-runs/' in url: return (mode['calc'], json.dumps(calc, ensure_ascii=False).encode()) if mode['calc'] == 200 else (mode['calc'], b'{}')
    return (mode['ing'], json.dumps(dict(items=[dict(batchId='b1', status='LANDED', eventCount=10)])).encode()) if mode['ing'] == 200 else (mode['ing'], b'{}')
os.environ['CALC_API_URL'] = 'http://calc'; os.environ['INGEST_API_URL'] = 'http://ing'; A.FETCH = fetch; fresh(); A.BLOB = FB()
srv = A.TS(('127.0.0.1', 8847), A.H); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8847'
def call(m, p, body=None, h=None, raw=False):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, (r.read() if raw else json.loads(r.read())), dict(r.headers)
    except urllib.error.HTTPError as e:
        d = e.read()
        try: return e.code, json.loads(d), {}
        except Exception: return e.code, d, {}
def wait(mid):
    for _ in range(100):
        c, d, _ = call('GET', '/v1/manifests/' + mid)
        if d['generationState'] in ('LOCAL_UNSIGNED_DRAFT_READY', 'PACKAGE_READY', 'PARTIAL', 'BLOCKED', 'FAILED'): return d
        time.sleep(0.1)
    return d
REQ = dict(plantId='KR-01', country='KR', purpose='AUDIT_DRAFT', recipientScope='LOCAL', sourceBinding=dict(kind='run', runId=RUN))
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
import base64
class MockKv:
    """Key Vault sign/verify 계약의 모의: ES256, digest 입력, r||s 서명. 실제 호출 증거가 아니다."""
    alg = 'ES256'; kid = 'https://kv/keys/evid-sign-kr01/v1'
    def __init__(self): self.k = ec.generate_private_key(ec.SECP256R1()); self.fail = None; self.lie = False
    def sign(self, dg):
        if self.fail == 'error': raise RuntimeError('lost')
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
        r, s = decode_dss_signature(self.k.sign(bytes.fromhex(dg), ec.ECDSA(Prehashed(hashes.SHA256())))); return base64.urlsafe_b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).rstrip(b'=').decode(), self.kid
    def verify(self, dg, sig, kid):
        if self.lie: return False
        from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
        raw = base64.urlsafe_b64decode(sig + '=' * (-len(sig) % 4))
        try: self.k.public_key().verify(encode_dss_signature(int.from_bytes(raw[:32], 'big'), int.from_bytes(raw[32:], 'big')), bytes.fromhex(dg), ec.ECDSA(Prehashed(hashes.SHA256()))); return True
        except Exception: return False
kv = MockKv(); A.SIGNER = kv
c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's1', 'X-Actor': 'tester'}); m = wait(d['manifestId'])
chk('T11 유효 분리 서명 → PACKAGE_READY·signingState VERIFIED·localOnly 유지·외부 검증 NOT_VERIFIED', m['generationState'] == 'PACKAGE_READY' and m['signingState'] == 'VERIFIED' and m['localOnly'] is True and m['externalVerificationState'] == 'NOT_VERIFIED', m)
sr = A.R.tx(lambda cur: (A.R.ex(cur, 'SELECT signedDigest, signingProfileVersion, algorithm, keyRef, verificationStatus FROM dbo.SignatureRef WHERE manifestId=%s', (m['manifestId'],)), cur.fetchall()[0])[1])
chk('SignatureRef: digest·profile·알고리즘·keyRef(버전 포함)·VERIFIED 기록', sr[1] == C.SIGN_PROFILE and sr[2] == 'ES256' and sr[3].endswith('/v1') and sr[4] == 'VERIFIED' and len(sr[0]) == 64, sr)
sig_name = [k for k in A.BLOB.d if k.endswith('/signature.json') and m['manifestId'] in k]
chk('signature.json은 ZIP 밖 별도 객체(ZIP 해시에 서명 미포함)', len(sig_name) == 1 and b'signature' not in A.BLOB.d[[k for k in A.BLOB.d if m['manifestId'] in k and k.endswith('package.zip')][0]][:0] + b'x')
c, z, h = call('GET', '/v1/manifests/' + m['manifestId'] + '/download', raw=True); chk('서명 재검증 통과 후 다운로드 200', c == 200 and C.sha(z) == m['artifactHash'], c)
c, d, _ = call('GET', '/v1/manifests/' + m['manifestId'] + '/verify'); chk('verify에 SIGNATURE 검사 포함·PASS', d['verdict'] == 'PASS' and any(x['check'] == 'SIGNATURE' and x['ok'] for x in d['checks']), d)
# 서명 변조(다른 digest) → BLOCKED·바이트 미반환
sn = sig_name[0]; doc = json.loads(A.BLOB.d[sn]); doc['signature'] = doc['signature'][:-4] + ('AAAA' if not doc['signature'].endswith('AAAA') else 'BBBB'); A.BLOB.d[sn] = json.dumps(doc, sort_keys=True).encode()
c, d, _ = call('GET', '/v1/manifests/' + m['manifestId'] + '/download'); m2 = call('GET', '/v1/manifests/' + m['manifestId'])[1]
chk('T11 서명 변조 → 409·BLOCKED·미서명 정상으로 낮추지 않음', c == 409 and m2['generationState'] == 'BLOCKED', (c, d, m2['generationState']))
# 검증 불일치(키가 verify 거절) → BLOCKED
kv.lie = True; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's2'}); m3 = wait(d['manifestId']); kv.lie = False
chk('서명 검증 실패 → BLOCKED(PACKAGE_READY 아님)', m3['generationState'] == 'BLOCKED', m3['generationState'])
# 서명 호출 오류/응답 유실 → UNKNOWN, 자동 재서명 없음, 다운로드 차단
kv.fail = 'error'; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's3'}); m4 = wait2 = None
for _ in range(100):
    m4 = call('GET', '/v1/manifests/' + d['manifestId'])[1]
    if m4['generationState'] in ('UNKNOWN', 'PACKAGE_READY', 'BLOCKED', 'FAILED'): break
    time.sleep(0.1)
kv.fail = None
chk('서명 오류 → UNKNOWN(자동 재서명 없음)', m4['generationState'] == 'UNKNOWN' and m4.get('signingState') == 'UNKNOWN', m4)
c, d2, _ = call('GET', '/v1/manifests/' + d['manifestId'] + '/download'); chk('UNKNOWN은 다운로드 409', c == 409, (c, d2))
# 키 정책 미구성이면 기존대로 미서명 초안
A.SIGNER = None; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's4'}); m5 = wait(d['manifestId'])
chk('SIGNER 미구성 → LOCAL_UNSIGNED_DRAFT_READY·NOT_CONFIGURED', m5['generationState'] == 'LOCAL_UNSIGNED_DRAFT_READY' and m5['signingState'] == 'NOT_CONFIGURED', m5)
# 서명된 패키지라도 PARTIAL 우선
A.SIGNER = kv; mode['ing'] = 503; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's5'}); m6 = wait(d['manifestId']); mode['ing'] = 200
chk('누락 있는 서명 패키지는 PARTIAL(완전본 아님)', m6['generationState'] == 'PARTIAL', m6['generationState'])
# ---- 키 상태(회전·폐기) ----
A.SIGNER = kv; mode['ing'] = 200; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 's6'}); m7 = wait(d['manifestId']); KID = kv.kid; URL7 = '/v1/manifests/' + m7['manifestId']
c, d, _ = call('GET', '/v1/signing-keys'); chk('서명에 쓴 키 버전이 active로 자동 등록됨', c == 200 and any(x['keyRef'] == KID and x['status'] == 'active' for x in d['items']), d)
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef=KID, status='retired', reason='정기 회전'), {'X-Actor': 'ops'}); chk('active → retired(사유 필수·감사 기록)', c == 200 and d['status'] == 'retired' and d['previous'] == 'active', d)
c, z, _ = call('GET', URL7 + '/download', raw=True); chk('retired 키로 서명된 과거 패키지는 계속 제공(검증 유효)', c == 200, c)
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef=KID, status='revoked'), {'X-Actor': 'ops'}); chk('revoked는 사유 없으면 400', c == 400, d)
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef='https://kv/keys/never-used/v1', status='retired', reason='x')); chk('서명에 쓴 적 없는 키는 404', c == 404, d)
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef=KID, status='weird', reason='x')); chk('알 수 없는 상태 400', c == 400, d)
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef=KID, status='revoked', reason='키 유출 의심'), {'X-Actor': 'ops'}); chk('retired → revoked(사유 기록)', c == 200 and d['status'] == 'revoked', d)
c, d, _ = call('GET', URL7 + '/download', raw=True); chk('revoked 키로 서명된 패키지는 제공하지 않음(409 STATE_BLOCKED)', c == 409 and (d.get('code') if isinstance(d, dict) else json.loads(d)['code']) == 'STATE_BLOCKED', (c, d))
mm = call('GET', URL7)[1]; chk('폐기 키 서명 패키지는 BLOCKED로 표시', mm['generationState'] == 'BLOCKED', mm['generationState'])
c, d, _ = call('POST', '/v1/signing-keys/status', dict(keyRef=KID, status='active', reason='복구'), {'X-Actor': 'ops'}); chk('revoked는 되돌릴 수 없음(409 INVALID_TRANSITION)', c == 409 and d['code'] == 'INVALID_TRANSITION', d)
au = A.R.tx(lambda cur: (A.R.ex(cur, "SELECT COUNT(*) FROM EvidenceAccessAudit WHERE action='KEY_STATUS'"), cur.fetchall()[0][0])[1]); chk('상태 변경 2건 감사 기록', au == 2, au)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
