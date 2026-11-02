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
srv = A.TS(('127.0.0.1', 8846), A.H); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8846'
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
c, d, _ = call('POST', '/v1/evidence-requests', REQ); chk('Idempotency-Key 없으면 400', c == 400 and d['code'] == 'IDEMPOTENCY_KEY_REQUIRED', d)
c, d, _ = call('POST', '/v1/evidence-requests', dict(REQ, sourceBinding=dict(kind='release', releaseId='x')), {'Idempotency-Key': 'a1'}); chk('release 연계는 차단(422)', c == 422 and d['code'] == 'RELEASE_BINDING_BLOCKED', d)
c, d, _ = call('POST', '/v1/evidence-requests', dict(REQ, plantId='JP-01'), {'Idempotency-Key': 'a2'}); chk('다른 국가 공장 → 422', c == 422 and d['code'] == 'PLANT_NOT_IN_SCOPE', d)
c, d, _ = call('POST', '/v1/evidence-requests', dict(REQ, recipientScope='EXTERNAL'), {'Idempotency-Key': 'a3'}); chk('외부 제공 목적 → 422(닫힘)', c == 422 and d['code'] == 'PURPOSE_NOT_ALLOWED', d)
c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); mid = d.get('manifestId'); chk('접수 202(완성·서명 아님)', c == 202 and d['generationState'] == 'REQUESTED' and d['stateVersion'] == 1, (c, d))
m = wait(mid)
chk('봉인·패키지: 미서명 국내 초안(LOCAL_UNSIGNED_DRAFT_READY)·localOnly·SIMULATED·외부 검증 NOT_VERIFIED·서명 NOT_CONFIGURED', m['generationState'] == 'LOCAL_UNSIGNED_DRAFT_READY' and m['localOnly'] is True and m['mode'] == 'SIMULATED' and m['externalVerificationState'] == 'NOT_VERIFIED' and m['signingState'] == 'NOT_CONFIGURED' and m['label'].startswith('미서명'), m)
core = m['manifestCore']; its = {i['itemId']: i for i in core['items']}
chk('항목: S02 run(수치·단위 decimal 문자열)·S01 접수 이력 포함, S05는 제외 사유 명시(누락 아님)', its['S02-RUN']['inclusionStatus'] == 'INCLUDED' and its['S02-RUN']['factRef'][0]['value'] == '459.400' and its['S01-INGESTIONS']['inclusionStatus'] == 'INCLUDED' and its['S05-DISCLOSURE']['inclusionStatus'] == 'EXCLUDED' and its['S05-DISCLOSURE']['inclusionReason'], its)
chk('manifestHash == sha256(정규 본체) 이고 본체에 자기 hash 없음', m['manifestHash'] == C.sha(C.canon(core)) and 'manifestHash' not in core)
c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); chk('같은 키·같은 내용 → 원래 ID/현재 상태(200)', c == 200 and d['manifestId'] == mid, (c, d))
c, d, _ = call('POST', '/v1/evidence-requests', dict(REQ, sourceBinding=dict(kind='run', runId=str(uuid.uuid4()))), {'Idempotency-Key': 'k1', 'X-Actor': 'tester'}); chk('같은 키·다른 snapshot → 409 KEY_DIGEST_CONFLICT', c == 409 and d['code'] == 'KEY_DIGEST_CONFLICT', (c, d))
c, d, _ = call('GET', '/v1/manifests/' + mid + '/verify'); chk('재개봉 검증 PASS(ZIP·manifest·항목 hash)', c == 200 and d['verdict'] == 'PASS' and 'ITEM:S02-RUN' in [x['check'] for x in d['checks']], d)
c, z, h = call('GET', '/v1/manifests/' + mid + '/download', raw=True); chk('다운로드: zip 바이트·artifactHash 헤더 일치·no-store', c == 200 and C.sha(z) == h['X-Artifact-Hash'] == m['artifactHash'] and 'no-store' in h['Cache-Control'], (c, h))
# T12 사전 감사 실패 → 첫 바이트 전 503, 데이터 미반환
orig = A.Repo.audit
def bad_audit(self, cur, actor, action, *a, **k):
    if action == 'DOWNLOAD': raise A.ApiError(503, 'AUDIT_UNAVAILABLE', 'x', True)
    return orig(self, cur, actor, action, *a, **k)
A.Repo.audit = bad_audit; c, d, _ = call('GET', '/v1/manifests/' + mid + '/download'); A.Repo.audit = orig
chk('T12 사전 감사 실패 → 503 AUDIT_UNAVAILABLE·ZIP 미반환', c == 503 and d['code'] == 'AUDIT_UNAVAILABLE' and isinstance(d, dict), (c, d))
# T04 저장소 객체 1바이트 변조 → 제공 거절·BLOCKED
name = [k for k in A.BLOB.d][0]; zb = bytearray(A.BLOB.d[name]); zb[len(zb) // 2] ^= 1; A.BLOB.d[name] = bytes(zb)
c, d, _ = call('GET', '/v1/manifests/' + mid + '/download'); m2 = call('GET', '/v1/manifests/' + mid)[1]; chk('T04 변조된 패키지 → 409 STATE_BLOCKED·상태 BLOCKED·바이트 미반환', c == 409 and d['code'] == 'STATE_BLOCKED' and m2['generationState'] == 'BLOCKED', (c, d, m2['generationState']))
# S01 조회 실패 → MISSING → PARTIAL(완전본 다운로드 거절), 0으로 대체 없음
mode['ing'] = 503; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 'k2'}); m3 = wait(d['manifestId'])
chk('원천 조회 실패 → MISSING(이유 명시)·PARTIAL, 0/빈 값 대체 없음', m3['generationState'] == 'PARTIAL' and any(x['status'] == 'MISSING' and 'S01' in x['reason'] for x in m3['missingItems']), m3.get('missingItems'))
c, d, _ = call('GET', '/v1/manifests/' + m3['manifestId'] + '/download'); chk('PARTIAL은 완전본 다운로드 거절 422', c == 422 and d['code'] == 'INCOMPLETE_EVIDENCE', (c, d)); mode['ing'] = 200
mode['calc'] = 503; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 'k3'}); m4 = wait(d['manifestId']); chk('S02 불명 → FAILED(사용 차단, 철회 확정 아님)·패키지 없음', m4['generationState'] == 'FAILED' and 'package' not in m4 and 'AUTHORITY_UNAVAILABLE' in m4['failReason'], m4)
mode['calc'] = 404; c, d, _ = call('POST', '/v1/evidence-requests', REQ, {'Idempotency-Key': 'k4'}); m5 = wait(d['manifestId']); chk('S02에 없는 run → 실패(수치 생성 없음)', m5['generationState'] in ('FAILED', 'BLOCKED') and 'SOURCE_NOT_FOUND' in m5['failReason'], m5); mode['calc'] = 200
c, d, _ = call('GET', '/v1/manifests/not-a-uuid'); chk('형식 오류 400', c == 400, d)
c, d, _ = call('GET', '/v1/manifests/' + str(uuid.uuid4())); chk('없는 manifest 404', c == 404, d)
c, d, _ = call('GET', '/v1/evidence-requests?plantId=KR-01'); chk('목록 조회', c == 200 and len(d['items']) >= 4, d)
rows = A.R.tx(lambda cur: (A.R.ex(cur, 'SELECT prevHash, entryHash, decision, action FROM dbo.EvidenceAccessAudit ORDER BY auditSeq'), cur.fetchall())[1])
chk('감사 해시 체인 연속 %d행 · DENY 기록 포함' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and any(r[2] == 'DENY' for r in rows) and len(rows) > 15, len(rows))
c, d, _ = call('GET', '/health'); chk('health', c == 200 and d['ok'])
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
