#!/usr/bin/env python3
"""evid-api — S06 증빙·감사 근거 API06(체크리스트 2-3-2~2-3-4). 설계: design/services/S06 §5·6·7.3.
정본 경로: POST /v1/evidence-requests, GET /v1/manifests/{id}, 확장 GET /v1/manifests/{id}/download. (검증 보조: GET /v1/manifests/{id}/verify)
차이(문서화): 사용자·위임 인가(evidence:*)는 S07 권한 원장·S11 위임 토큰 전이라 없다 → 내부 전용·호출자는 X-Actor(미검증 라벨). 서명 키 정책 미결 → signingState=NOT_CONFIGURED, 결과는 LOCAL_UNSIGNED_DRAFT_READY(localOnly·DRAFT_ONLY/SIMULATED), 외부 제공·S09 projection 제출은 닫음.
S12 미구축으로 작업은 앱 내부 작업자가 대행. S05 공개 상태 연계는 호출 계약 미합의 → MISSING(이유 명시). 감사는 상태 변경과 같은 트랜잭션, 다운로드는 첫 바이트 전에 사전 감사(실패 시 503·데이터 미반환).
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, STORE_URL(evidence 컨테이너), CALC_API_URL, INGEST_API_URL, PORT. 시험: 모의 주입."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, sys, base64, json, time, uuid, hashlib, threading, datetime as dt, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evid_core as C
VERSION = 'evid-api/0.3'; COUNTRY, ORG = 'KR', 'AMA-KR'; STATS = dict(requests=0, errors=0, started=time.time())
class ApiError(Exception):
    def __init__(self, status, code, msg='', retry=False): self.status, self.code, self.msg, self.retry = status, code, msg, retry
def now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def ts(d=None): d = d or now(); return d.strftime('%Y-%m-%d %H:%M:%S.') + '%03d' % (d.microsecond // 1000)
def iso(v): return (v.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (v.microsecond // 1000)) if hasattr(v, 'strftime') else (str(v).replace(' ', 'T') + 'Z' if v and 'T' not in str(v) else v)

# ---------------- 저장소: pytds(T-SQL)와 sqlite(시험)가 같은 SQL을 쓴다 ----------------
class Repo:
    def __init__(self, kind, conn_factory): self.kind, self.cf, self.conn, self.lock, self.err, self.last_err = kind, conn_factory, None, threading.RLock(), 0, None
    def q(self, sql): return sql.replace('%s', '?').replace('dbo.', '') if self.kind == 'sqlite' else sql
    def top1(self, sql): return sql.replace('SELECT', 'SELECT TOP 1', 1) if self.kind == 'sql' else sql + ' LIMIT 1'
    def tx(self, fn):
        with self.lock:
            for t in (0, 1):
                try:
                    if self.conn is None: self.conn = self.cf()
                    cur = self.conn.cursor(); r = fn(cur); self.conn.commit(); return r
                except ApiError: self._rb(); raise
                except Exception as e:
                    self.err += 1; self.last_err = (type(e).__name__ + ': ' + str(e))[:160]; self._rb()
                    if self.kind == 'sql':
                        try: self.conn.close()
                        except Exception: pass
                        self.conn = None
                    if t or self.kind == 'sqlite': raise ApiError(503, 'STORE_UNAVAILABLE', '저장소 오류로 처리하지 못했습니다.', True)
                    time.sleep(0.3)
    def _rb(self):
        try: self.conn.rollback()
        except Exception: pass
    def ex(self, cur, sql, p=()): cur.execute(self.q(sql), p); return cur
    def audit(self, cur, actor, action, target, decision, reason='', th=None, purpose=None, cid=None):
        self.ex(cur, self.top1('SELECT entryHash FROM dbo.EvidenceAccessAudit ORDER BY auditSeq DESC')); r = cur.fetchall(); prev = r[0][0] if r else None; at = ts()
        h = hashlib.sha256(('%s|%s|%s|%s|%s|%s|%s|%s' % (prev, actor, action, target, th, decision, reason, at)).encode()).hexdigest()
        self.ex(cur, 'INSERT INTO dbo.EvidenceAccessAudit(actor, action, target, targetHash, purpose, decision, reason, correlationId, at, prevHash, entryHash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', ((actor or 'internal-unverified')[:120], action, target, th, purpose, decision, (reason or '')[:300], cid, at, prev, h))
    def stats(self): return self.tx(lambda cur: (self.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.EvidenceRequest), (SELECT COUNT(*) FROM dbo.EvidenceAccessAudit), (SELECT COUNT(*) FROM dbo.AuditPackage)'), dict(zip(('requests', 'audits', 'packages'), cur.fetchall()[0])))[1]) | dict(kind=self.kind, errors=self.err, last_err=self.last_err)
def sql_repo():
    import pytds, certifi; srv, db = os.environ['SQL_SERVER'], os.environ['SQL_DB']
    def tok():
        q = {'resource': 'https://database.windows.net/', 'api-version': '2019-08-01'}
        if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
        return json.loads(urllib.request.urlopen(urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=10).read())['access_token']
    return Repo('sql', lambda: pytds.connect(srv, db, port=1433, access_token_callable=tok, cafile=certifi.where(), autocommit=False, login_timeout=20, timeout=30))
R = None

# ---------------- Blob·생산자 ----------------
class Blob:
    """현지 evidence 컨테이너. 불변 object key에 If-None-Match:* 조건부 생성(덮어쓰기 불가)."""
    def __init__(self): self.store = os.environ['STORE_URL'].rstrip('/') + '/evidence'
    def _h(self, extra=None):
        ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=https://storage.azure.com/&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
        t = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
        return dict({'Authorization': 'Bearer ' + t, 'x-ms-version': '2023-11-03', 'x-ms-date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}, **(extra or {}))
    def put_new(self, name, data):
        try: urllib.request.urlopen(urllib.request.Request(self.store + '/' + name, data=data, method='PUT', headers=self._h({'x-ms-blob-type': 'BlockBlob', 'If-None-Match': '*', 'Content-Type': 'application/json' if name.endswith('.json') else 'application/zip'})), timeout=60).read(); return 'created'
        except urllib.error.HTTPError as e:
            if e.code in (409, 412): return 'exists'
            raise
    def get(self, name):
        try: return urllib.request.urlopen(urllib.request.Request(self.store + '/' + name, headers=self._h()), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            raise
BLOB = None
class KvSigner:
    """Key Vault 비대칭 키(EC P-256)로 digest에 서명·검증. 키 원문은 받지 않고 sign/verify 연산만 호출한다(최소 권한: Key Vault Crypto User, 키 범위).
    KEY_URL 예: https://kv-...vault.azure.net/keys/evid-sign-kr01 (버전 없으면 최신 활성 버전; 응답 kid의 버전을 keyRef로 고정 기록)."""
    alg = C.SIGN_ALG
    def __init__(self, key_url): self.key = key_url.rstrip('/')
    def _tok(self):
        ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=https://vault.azure.net&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
    def _post(self, url, body):
        rq = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST', headers={'Authorization': 'Bearer ' + self._tok(), 'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(rq, timeout=20).read())
    @staticmethod
    def b64(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    def sign(self, digest_hex):
        r = self._post(self.key + '/sign?api-version=7.4', dict(alg=self.alg, value=self.b64(bytes.fromhex(digest_hex)))); return r['value'], r['kid']
    def verify(self, digest_hex, sig, key_ref):
        r = self._post(key_ref + '/verify?api-version=7.4', dict(alg=self.alg, digest=self.b64(bytes.fromhex(digest_hex)), value=sig)); return r.get('value') is True
SIGNER = None
def http_get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=20) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
FETCH = http_get

# ---------------- 작업(S12 대행) ----------------
def assemble(rq):
    """run을 소유 서비스(S02) API로, 접수 이력을 S01 API로 읽어 정확한 바이트를 항목으로 고정한다. S05 공개 상태는 계약 미합의라 MISSING."""
    cu, iu = os.environ.get('CALC_API_URL', '').rstrip('/'), os.environ.get('INGEST_API_URL', '').rstrip('/'); items, files = [], {}
    st, body = FETCH(cu + '/v1/calc-runs/' + rq['sourceRef'])
    if st == 404: raise ApiError(404, 'SOURCE_NOT_FOUND', '해당 run이 S02에 없습니다.')
    if st != 200: raise ApiError(503, 'AUTHORITY_UNAVAILABLE', 'S02 run 조회에 실패했습니다(원천 불명은 사용 차단).', True)
    run = json.loads(body)
    if run['plantId'] != rq['plantId'] or run['country'] != rq['country']: raise ApiError(422, 'LINEAGE_MISMATCH', 'run의 국가·공장이 요청과 다릅니다.')
    facts = [dict(metric=v['metric'], value=v['value'], unit=v['unit'], boundary=v['boundaryRef']) for v in run.get('values', [])] or None
    items.append(C.item_ref('S02-RUN', 'S02', 'run:' + run['runId'], run['updatedAt'], body, fact=facts)); files['S02-RUN.json'] = body
    st, ib = FETCH(iu + '/v1/ingestions?plantId=%s&periodStart=%s&periodEnd=%s&limit=100' % (rq['plantId'], urllib.parse.quote(run['periodStart']), urllib.parse.quote(run['periodEnd'])))
    if st == 200: items.append(C.item_ref('S01-INGESTIONS', 'S01', 'ingestions:%s:%s..%s' % (rq['plantId'], run['periodStart'], run['periodEnd']), None, ib)); files['S01-INGESTIONS.json'] = ib
    else: items.append(C.item_ref('S01-INGESTIONS', 'S01', 'ingestions:' + rq['plantId'], None, None, inclusion='MISSING', reason='S01 조회 실패(%s) — 원천 불명, 0으로 대체하지 않음' % st))
    items.append(C.item_ref('S05-DISCLOSURE', 'S05', 'disclosure:none', None, None, inclusion='EXCLUDED', reason='run 초안은 공개 자격이 없고 S05 상태 조회의 S06 호출 계약도 미합의 — 공개 연계 사용 차단(S06 §3·§5.2)'))
    lineage = [dict(edgeId='L1', fromRef=items[1]['sourceRef'], toRef='run:' + run['runId'], method='S01 접수 batch → S02 입력 snapshot'), dict(edgeId='L2', fromRef='run:' + run['runId'], toRef='manifest:' + rq['manifestId'], method='S06 봉인')]
    if items[1]['inclusionStatus'] != 'INCLUDED': lineage = lineage[1:]
    return run, items, files, lineage
def work(rq):
    try:
        R.tx(lambda cur: set_state(cur, rq, 'ASSEMBLING')); run, items, files, lineage = assemble(rq)
        ctx = dict(country=rq['country'], orgId=rq['orgId'], plantId=rq['plantId'], manifestId=rq['manifestId'], manifestVersion=rq['manifestVersion'], sourceBinding=dict(kind=rq['sourceKind'], runId=run['runId'], runUpdatedAt=run['updatedAt']), snapshotId=run['runKey'][:32], periodStart=run['periodStart'], periodEnd=run['periodEnd'], timeZone=run['timezone'], purpose=rq['purpose'], recipientScope=rq['recipientScope'], mode=run['mode'], classification='INTERNAL')
        body = C.build_manifest(ctx, items, lineage); mb, mh = C.seal(body); missing = any(i['inclusionStatus'] == 'MISSING' for i in items)
        zb, ah = C.make_zip(mb, files, C.readme(body, 'DETACHED(signature.json)' if SIGNER else 'NOT_CONFIGURED')); name = '%s/%s/%s/v%d/package.zip' % (rq['country'], rq['orgId'], rq['manifestId'], rq['manifestVersion'])
        res = BLOB.put_new(name, zb)
        if res == 'exists':
            cur_b = BLOB.get(name)
            if cur_b is None or C.sha(cur_b) != ah: raise ApiError(409, 'OBJECT_CONFLICT', '같은 object key에 다른 내용이 있습니다.')
        signing, sigrow = sign_package(rq, name, mh, ah)
        final = C.final_state2(signing, missing)
        def commit(cur):
            R.ex(cur, 'INSERT INTO dbo.EvidenceManifest(country, orgId, manifestId, manifestVersion, plantId, sourceBinding, snapshotId, periodStart, periodEnd, timeZone, purpose, recipientScope, inputDigest, manifestHash, supersedesRef, mode, classification, schemaVersion, bodyJson, createdBy, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (rq['country'], rq['orgId'], rq['manifestId'], rq['manifestVersion'], rq['plantId'], json.dumps(body['sourceBinding']), ctx['snapshotId'], body['period']['start'].replace('T', ' ').replace('Z', ''), body['period']['end'].replace('T', ' ').replace('Z', ''), ctx['timeZone'], rq['purpose'], rq['recipientScope'], C.sha(C.canon([i['byteHash'] for i in items])), mh, None, ctx['mode'], 'INTERNAL', C.SCHEMA, mb.decode('utf-8'), rq['principal'], ts()))
            for i in items: R.ex(cur, 'INSERT INTO dbo.EvidenceItemRef(manifestId, manifestVersion, itemId, ownerService, sourceRef, sourceVersion, byteHash, byteSize, mediaType, inclusionStatus, inclusionReason, factRef) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (rq['manifestId'], rq['manifestVersion'], i['itemId'], i['ownerService'], i['sourceRef'], i['sourceVersion'], i['byteHash'] or '0' * 64, i['byteSize'], i['mediaType'], i['inclusionStatus'], i['inclusionReason'], json.dumps(i['factRef']) if i['factRef'] else None))
            for e in lineage: R.ex(cur, 'INSERT INTO dbo.LineageRef(manifestId, manifestVersion, edgeId, fromRef, toRef, method) VALUES (%s,%s,%s,%s,%s,%s)', (rq['manifestId'], rq['manifestVersion'], e['edgeId'], e['fromRef'], e['toRef'], e['method']))
            R.ex(cur, 'INSERT INTO dbo.SignatureRef(manifestId, manifestVersion, signatureId, signedDigest, signingProfileVersion, algorithm, keyRef, signedAt, verificationStatus) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)', (rq['manifestId'], rq['manifestVersion'], 'SIG-0', sigrow.get('digest'), sigrow.get('profile'), sigrow.get('alg'), sigrow.get('keyRef'), sigrow.get('at'), signing))
            R.ex(cur, 'INSERT INTO dbo.AuditPackage(manifestId, manifestVersion, packageId, blobRef, artifactHash, byteSize, templateVersion, generationState, signingState, localOnly, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (rq['manifestId'], rq['manifestVersion'], 'PKG-1', name, ah, len(zb), C.TEMPLATE, final, signing, 1, ts()))
            if sigrow.get('keyRef'): ensure_key_row(cur, sigrow['keyRef'])
            set_state(cur, rq, 'SEALED_DRAFT'); set_state(cur, rq, final)
        R.tx(commit)
    except ApiError as e: fail(rq, e.code + ' ' + e.msg, 'BLOCKED' if e.status in (409, 422) else 'FAILED')
    except Exception as e: fail(rq, (type(e).__name__ + ': ' + str(e))[:280], 'FAILED')
def sign_package(rq, name, mh, ah):
    """서명 경로: 패키지 hash 확인 → 분리 서명 → 같은 digest로 검증 → signature.json을 ZIP 옆에 불변 생성. 응답 유실·오류는 UNKNOWN(자동 재서명 안 함), 검증 불일치는 BAD.
    서명 성공은 외부 인증이 아니며 PACKAGE_READY여도 localOnly·외부 제공 닫힘이다."""
    if SIGNER is None: return C.signing_decision(False, False, None), {}
    pl, dg = C.sign_payload(mh, ah, rq['manifestId'], rq['manifestVersion'])
    try:
        sig, kid = SIGNER.sign(dg); ok = SIGNER.verify(dg, sig, kid)
        row = dict(digest=dg, profile=C.SIGN_PROFILE, alg=SIGNER.alg, keyRef=kid[:200], at=ts())
        if ok:
            doc = json.dumps(dict(payload=json.loads(pl), digest=dg, algorithm=SIGNER.alg, keyRef=kid, signature=sig), ensure_ascii=False, sort_keys=True).encode()
            sname = name.rsplit('/', 1)[0] + '/signature.json'
            if BLOB.put_new(sname, doc) == 'exists' and BLOB.get(sname) != doc: return 'UNKNOWN', row
        return C.signing_decision(True, ok, None), row
    except Exception: return C.signing_decision(True, False, 'sign-error'), {}
def set_state(cur, rq, to):
    R.ex(cur, 'SELECT generationState, stateVersion FROM dbo.EvidenceRequest WHERE requestId=%s', (rq['requestId'],)); a, v = cur.fetchall()[0]
    if not C.can(a, to): raise RuntimeError('BAD_TRANSITION %s->%s' % (a, to))
    R.ex(cur, 'UPDATE dbo.EvidenceRequest SET generationState=%s, stateVersion=%s, updatedAt=%s WHERE requestId=%s AND stateVersion=%s', (to, v + 1, ts(), rq['requestId'], v))      # CAS
    if cur.rowcount != 1: raise RuntimeError('CAS_CONFLICT')
    R.audit(cur, 'evid-worker', 'STATE', rq['requestId'], 'ALLOW', '%s->%s' % (a, to))
def fail(rq, reason, state):
    def f(cur):
        R.ex(cur, 'SELECT generationState FROM dbo.EvidenceRequest WHERE requestId=%s', (rq['requestId'],)); a = cur.fetchall()[0][0]
        if not C.can(a, state): state_ = 'FAILED' if C.can(a, 'FAILED') else a
        else: state_ = state
        R.ex(cur, 'UPDATE dbo.EvidenceRequest SET generationState=%s, stateVersion=stateVersion+1, failReason=%s, updatedAt=%s WHERE requestId=%s', (state_, reason[:300], ts(), rq['requestId'])); R.audit(cur, 'evid-worker', 'STATE', rq['requestId'], 'DENY', reason)
    try: R.tx(f)
    except Exception: pass

# ---------------- API ----------------
def create(body, actor, idem, cid):
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    sb = body.get('sourceBinding') or {}; kind = sb.get('kind')
    if kind == 'release': raise ApiError(422, 'RELEASE_BINDING_BLOCKED', 'release 연계는 S02 발행본(certified)이 생기기 전까지 사용할 수 없습니다. run 초안만 지원합니다.')
    if kind != 'run' or not sb.get('runId'): raise ApiError(400, 'BAD_REQUEST', 'sourceBinding={kind:"run", runId}가 필요합니다.')
    try: uuid.UUID(str(sb['runId']))
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'runId 형식이 올바르지 않습니다.')
    plant = str(body.get('plantId') or ''); purpose = str(body.get('purpose') or 'AUDIT_DRAFT'); scope = str(body.get('recipientScope') or 'LOCAL')
    if plant != 'KR-01' or body.get('country', COUNTRY) != COUNTRY: raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역 DB06은 KR-01만 다룹니다. 다른 국가 증빙은 해당 국가 서비스가 소유합니다.')
    if scope != 'LOCAL' or purpose != 'AUDIT_DRAFT': raise ApiError(422, 'PURPOSE_NOT_ALLOWED', '현재는 purpose=AUDIT_DRAFT, recipientScope=LOCAL(국내 미서명 초안)만 허용합니다. 외부 제공·반출은 닫혀 있습니다.')
    rd = C.sha(C.canon(dict(plant=plant, run=sb['runId'], purpose=purpose, scope=scope))); principal = (actor or 'internal-unverified')[:120]
    rid, mid = str(uuid.uuid4()), str(uuid.uuid4())
    def f(cur):
        R.ex(cur, 'SELECT requestId, requestDigest, manifestId, manifestVersion, generationState, stateVersion FROM dbo.EvidenceRequest WHERE country=%s AND orgId=%s AND principal=%s AND idemKey=%s', (COUNTRY, ORG, principal, idem[:100])); r = cur.fetchall()
        if r:
            if r[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, dict(requestId=r[0][0], manifestId=r[0][2], manifestVersion=r[0][3], generationState=r[0][4], stateVersion=r[0][5], statusUrl='/v1/manifests/' + r[0][2]), None
        R.ex(cur, 'INSERT INTO dbo.EvidenceRequest(requestId, country, orgId, plantId, principal, idemKey, requestDigest, sourceKind, sourceRef, purpose, recipientScope, manifestId, manifestVersion, generationState, stateVersion, correlationId, createdAt, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,1,%s,%s,%s)', (rid, COUNTRY, ORG, plant, principal, idem[:100], rd, 'run', sb['runId'], purpose, scope, mid, 'REQUESTED', cid, ts(), ts()))
        R.audit(cur, principal, 'EVIDENCE_REQUEST', rid, 'ALLOW', 'accepted', purpose=purpose, cid=cid)
        return 202, dict(requestId=rid, manifestId=mid, manifestVersion=1, generationState='REQUESTED', stateVersion=1, statusUrl='/v1/manifests/' + mid), dict(requestId=rid, country=COUNTRY, orgId=ORG, plantId=plant, principal=principal, sourceKind='run', sourceRef=sb['runId'], purpose=purpose, recipientScope=scope, manifestId=mid, manifestVersion=1)
    c, out, job = R.tx(f)
    if job: threading.Thread(target=work, args=(job,), daemon=True).start()
    return c, out
def load(mid):
    try: uuid.UUID(mid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'manifestId 형식이 올바르지 않습니다.')
    def f(cur):
        R.ex(cur, 'SELECT requestId, generationState, stateVersion, failReason, plantId, purpose, recipientScope, manifestVersion, createdAt, updatedAt FROM dbo.EvidenceRequest WHERE manifestId=%s', (mid,)); r = cur.fetchall()
        if not r: return None
        d = dict(requestId=r[0][0], manifestId=mid, manifestVersion=r[0][7], generationState=r[0][1], stateVersion=r[0][2], failReason=r[0][3], plantId=r[0][4], purpose=r[0][5], recipientScope=r[0][6], createdAt=iso(r[0][8]), updatedAt=iso(r[0][9]))
        R.ex(cur, 'SELECT manifestHash, bodyJson, mode FROM dbo.EvidenceManifest WHERE manifestId=%s', (mid,)); m = cur.fetchall()
        if m:
            core = json.loads(m[0][1]); d['manifestHash'] = m[0][0]; d['manifestCore'] = core; d['mode'] = m[0][2]
            R.ex(cur, 'SELECT blobRef, artifactHash, byteSize, generationState, signingState, reviewState, externalVerificationState, localOnly FROM dbo.AuditPackage WHERE manifestId=%s', (mid,)); p = cur.fetchall()
            if p: d['package'] = dict(artifactHash=p[0][1], byteSize=p[0][2], signingState=p[0][4], reviewState=p[0][5], externalVerificationState=p[0][6], localOnly=bool(p[0][7]), blobRef=p[0][0])
        return d
    return R.tx(f)
def view(d):
    out = dict(requestId=d['requestId'], manifestId=d['manifestId'], manifestVersion=d['manifestVersion'], generationState=d['generationState'], stateVersion=d['stateVersion'], plantId=d['plantId'], purpose=d['purpose'], recipientScope=d['recipientScope'], createdAt=d['createdAt'], updatedAt=d['updatedAt'])
    if d.get('failReason'): out['failReason'] = d['failReason']
    if 'manifestCore' in out or d.get('manifestCore'):
        core = d['manifestCore']; out.update(manifestHash=d['manifestHash'], mode=d['mode'], manifestCore=core, missingItems=[dict(itemId=i['itemId'], status=i['inclusionStatus'], reason=i['inclusionReason']) for i in core['items'] if i['inclusionStatus'] != 'INCLUDED'])
        p = d.get('package') or {}; out['signingState'] = p.get('signingState'); out['reviewState'] = p.get('reviewState'); out['externalVerificationState'] = p.get('externalVerificationState'); out['localOnly'] = p.get('localOnly'); out['artifactHash'] = p.get('artifactHash'); out['supersedesRef'] = core.get('supersedesRef')
        out['label'] = {'LOCAL_UNSIGNED_DRAFT_READY': '미서명 국내 초안(모의·외부 제공 불가)', 'PACKAGE_READY': '서명 패키지(외부 인증 아님)', 'PARTIAL': '일부 누락(부분 패키지)'}.get(d['generationState'], d['generationState'])
    return out
def get_manifest(mid):
    d = load(mid)
    if not d: raise ApiError(404, 'NOT_FOUND', '해당 증빙 요청이 없습니다.')
    return view(d)
def ensure_key_row(cur, ref):
    """서명에 쓴 키 버전(kid)을 상태표에 active로 등록한다(이미 있으면 그대로)."""
    R.ex(cur, 'SELECT status FROM dbo.SigningKeyStatus WHERE keyRef=%s', (ref[:300],))
    if not cur.fetchall(): R.ex(cur, 'INSERT INTO dbo.SigningKeyStatus(keyRef, status, reason, changedAt, changedBy) VALUES (%s,%s,%s,%s,%s)', (ref[:300], 'active', None, ts(), 'system'))
def key_status(ref):
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT status FROM dbo.SigningKeyStatus WHERE keyRef=%s', ((ref or '')[:300],)), cur.fetchall())[1]); return r[0][0] if r else None
KEY_TRANS = {('active', 'retired'), ('active', 'revoked'), ('retired', 'revoked'), ('retired', 'active')}   # revoked는 종결(되돌리지 않음)
def list_keys(): 
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT keyRef, status, reason, changedAt, changedBy FROM dbo.SigningKeyStatus ORDER BY changedAt DESC'), cur.fetchall())[1])
    return dict(items=[dict(keyRef=x[0], status=x[1], reason=x[2], changedAt=iso(x[3]), changedBy=x[4]) for x in r], note='active: 새 서명에 사용 중이거나 사용 가능한 키 버전, retired: 새 서명에는 쓰지 않지만 과거 서명 검증은 유효, revoked: 이 키로 서명된 패키지는 제공하지 않습니다(BLOCKED).')
def set_key_status(body, actor, cid):
    """POST /v1/signing-keys/status (내부 전용·포털 차단): 키 버전의 상태를 바꾼다. revoked는 사유 필수·종결."""
    ref = str(body.get('keyRef') or ''); st = str(body.get('status') or ''); why = str(body.get('reason') or '').strip()
    if not ref.startswith('https://') or '/keys/' not in ref or st not in ('active', 'retired', 'revoked'): raise ApiError(400, 'BAD_REQUEST', 'keyRef(키 URL)와 status(active·retired·revoked)가 필요합니다.')
    if st != 'active' and not why: raise ApiError(400, 'BAD_REQUEST', 'retired·revoked는 reason이 필요합니다.')
    def f(cur):
        R.ex(cur, 'SELECT status FROM dbo.SigningKeyStatus WHERE keyRef=%s', (ref[:300],)); r = cur.fetchall()
        if not r: raise ApiError(404, 'NOT_FOUND', '이 서비스가 서명에 사용한 적 없는 키 버전입니다.')
        if r[0][0] == st: return dict(keyRef=ref, status=st, unchanged=True)
        if (r[0][0], st) not in KEY_TRANS: raise ApiError(409, 'INVALID_TRANSITION', '%s → %s 전환은 허용되지 않습니다(revoked는 되돌릴 수 없음).' % (r[0][0], st))
        R.ex(cur, 'UPDATE dbo.SigningKeyStatus SET status=%s, reason=%s, changedAt=%s, changedBy=%s WHERE keyRef=%s', (st, why[:300] or None, ts(), (actor or 'internal-unverified')[:120], ref[:300]))
        R.audit(cur, actor, 'KEY_STATUS', ref[-60:], 'ALLOW', '%s->%s' % (r[0][0], st), cid=cid); return dict(keyRef=ref, status=st, previous=r[0][0])
    return R.tx(f)
def package_bytes(d, actor, cid, action):
    p = d.get('package')
    if not p: raise ApiError(409, 'STATE_BLOCKED', '아직 패키지가 없습니다(상태: %s).' % d['generationState'])
    if d['generationState'] not in ('LOCAL_UNSIGNED_DRAFT_READY', 'PACKAGE_READY', 'PARTIAL'): raise ApiError(409, 'STATE_BLOCKED', '현재 상태에서는 제공할 수 없습니다: ' + d['generationState'])
    b = BLOB.get(p['blobRef'])
    if b is None: raise ApiError(503, 'AUTHORITY_UNAVAILABLE', '패키지 객체를 읽지 못했습니다.', True)
    v = C.verify_package(b, p['artifactHash'], d['manifestHash'])
    if v['verdict'] != 'PASS':
        R.tx(lambda cur: (R.audit(cur, actor, action, d['manifestId'], 'DENY', 'HASH_MISMATCH', th=p['artifactHash'], cid=cid), R.ex(cur, 'UPDATE dbo.EvidenceRequest SET generationState=%s, stateVersion=stateVersion+1, failReason=%s WHERE manifestId=%s', ('BLOCKED', 'package verify failed', d['manifestId']))))
        raise ApiError(409, 'STATE_BLOCKED', '패키지 hash 검증에 실패해 제공하지 않습니다(BLOCKED).')
    if p['signingState'] == 'VERIFIED':      # 제공 직전에 분리 서명을 다시 검증(키 폐기·변조 탐지). 검증할 수 없으면 제공하지 않는다.
        ok = False
        try:
            sd = BLOB.get(p['blobRef'].rsplit('/', 1)[0] + '/signature.json'); doc = json.loads(sd) if sd else None
            if doc and SIGNER and key_status(doc['keyRef']) == 'revoked': v['checks'].append(dict(check='KEY_STATUS', ok=False, reason='KEY_REVOKED')); raise RuntimeError('revoked')
            if doc and SIGNER:
                _pl, dg = C.sign_payload(d['manifestHash'], p['artifactHash'], d['manifestId'], d['manifestVersion']); ok = (doc['digest'] == dg) and SIGNER.verify(dg, doc['signature'], doc['keyRef'])
        except Exception: ok = False
        v['checks'].append(dict(check='SIGNATURE', ok=ok))
        if not ok:
            R.tx(lambda cur: (R.audit(cur, actor, action, d['manifestId'], 'DENY', 'SIGNATURE_INVALID', th=p['artifactHash'], cid=cid), R.ex(cur, 'UPDATE dbo.EvidenceRequest SET generationState=%s, stateVersion=stateVersion+1, failReason=%s WHERE manifestId=%s', ('BLOCKED', 'signature verify failed', d['manifestId']))))
            raise ApiError(409, 'STATE_BLOCKED', '서명 검증에 실패해 제공하지 않습니다(BLOCKED).')
    return b, v
def download(mid, actor, cid):
    d = load(mid)
    if not d: raise ApiError(404, 'NOT_FOUND', '해당 증빙 요청이 없습니다.')
    if d['generationState'] == 'PARTIAL': raise ApiError(422, 'INCOMPLETE_EVIDENCE', '누락 항목이 있는 부분 패키지는 완전본으로 내려받을 수 없습니다. manifest의 missingItems를 확인하세요.')
    b, v = package_bytes(d, actor, cid, 'DOWNLOAD')
    try: R.tx(lambda cur: R.audit(cur, actor, 'DOWNLOAD', mid, 'ALLOW', 'pre-audit', th=d['package']['artifactHash'], purpose=d['purpose'], cid=cid))      # 사전 감사: 실패하면 첫 바이트 전에 503
    except ApiError: raise ApiError(503, 'AUDIT_UNAVAILABLE', '감사 기록에 실패해 데이터를 제공하지 않습니다.', True)
    return b, d['package']['artifactHash']
def verify(mid, actor, cid):
    d = load(mid)
    if not d: raise ApiError(404, 'NOT_FOUND', '해당 증빙 요청이 없습니다.')
    b, v = package_bytes(d, actor, cid, 'VERIFY'); return dict(manifestId=mid, verdict=v['verdict'], checks=v['checks'], artifactHash=d['package']['artifactHash'], manifestHash=d['manifestHash'], signingState=d['package']['signingState'], note='hash 일치는 무결성 확인일 뿐 내용의 진실성·법적 유효성·외부 인증을 뜻하지 않습니다.')
def list_requests(plant, limit):
    def f(cur):
        R.ex(cur, R.top1('SELECT requestId, manifestId, generationState, plantId, purpose, createdAt, sourceRef FROM dbo.EvidenceRequest' + (' WHERE plantId=%s' if plant else '') + ' ORDER BY createdAt DESC').replace('LIMIT 1', 'LIMIT %d' % limit).replace('TOP 1', 'TOP %d' % limit), (plant,) if plant else ())
        return [dict(requestId=r[0], manifestId=r[1], generationState=r[2], plantId=r[3], purpose=r[4], createdAt=iso(r[5]), runId=r[6]) for r in cur.fetchall()]
    return R.tx(f)
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def send(self, code, obj, cid=None, raw=None, ctype='application/json; charset=utf-8', extra=None):
        b = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store')
        if cid: self.send_header('X-Correlation-Id', cid)
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def go(self, m):
        STATS['requests'] += 1; cid = self.headers.get('X-Correlation-Id') or str(uuid.uuid4()); u = urlparse(self.path); qs = parse_qs(u.query); p = u.path.rstrip('/'); actor = self.headers.get('X-Actor') or 'internal-unverified'
        try:
            body = {}
            if m == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                if n > 20000: raise ApiError(413, 'PAYLOAD_TOO_LARGE')
                try: body = json.loads(self.rfile.read(n) or b'{}')
                except Exception: raise ApiError(400, 'BAD_REQUEST', 'JSON 형식이 아닙니다.')
            if m == 'GET' and p == '/health': return self.send(200, dict(ok=True, version=VERSION, db=R.stats(), **STATS), cid)
            if m == 'POST' and p == '/v1/evidence-requests': c, o = create(body, actor, self.headers.get('Idempotency-Key'), cid); return self.send(c, o, cid)
            if m == 'GET' and p == '/v1/evidence-requests': return self.send(200, dict(items=list_requests((qs.get('plantId') or [None])[0], min(int((qs.get('limit') or ['20'])[0]), 100))), cid)
            parts = p.split('/')
            if m == 'GET' and p == '/v1/signing-keys': return self.send(200, list_keys(), cid)
            if m == 'POST' and p == '/v1/signing-keys/status': return self.send(200, set_key_status(body, actor, cid), cid)
            if m == 'GET' and len(parts) == 4 and parts[1] == 'v1' and parts[2] == 'manifests': return self.send(200, get_manifest(parts[3]), cid)
            if m == 'GET' and len(parts) == 5 and parts[2] == 'manifests' and parts[4] == 'download':
                b, ah = download(parts[3], actor, cid); return self.send(200, None, cid, raw=b, ctype='application/zip', extra={'X-Artifact-Hash': ah, 'Content-Disposition': 'attachment; filename="evidence-draft-%s.zip"' % parts[3][:8]})
            if m == 'GET' and len(parts) == 5 and parts[2] == 'manifests' and parts[4] == 'verify': return self.send(200, verify(parts[3], actor, cid), cid)
            raise ApiError(405 if p.startswith('/v1/') else 404, 'METHOD_NOT_ALLOWED' if p.startswith('/v1/') else 'NOT_FOUND')
        except ApiError as e:
            if e.status >= 500: STATS['errors'] += 1
            self.send(e.status, dict(code=e.code, message=e.msg, retryable=e.retry, correlationId=cid), cid)
        except Exception: STATS['errors'] += 1; self.send(500, dict(code='INTERNAL', retryable=False, correlationId=cid), cid)
    def do_GET(self): self.go('GET')
    def do_POST(self): self.go('POST')
class TS(ThreadingHTTPServer): daemon_threads = True; request_queue_size = 64
def main():
    global R, BLOB, SIGNER; R = sql_repo(); BLOB = Blob(); SIGNER = KvSigner(os.environ['SIGN_KEY_URL']) if os.environ.get('SIGN_KEY_URL') else None; TS(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
if __name__ == '__main__': main()
