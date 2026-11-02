import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'exportapi'))
import export_app as EX, export_core as K
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE ExportRelease(country, exportId, requesterPrincipal, idemKey, requestDigest, sourceOwner, senderId, operation, sourceProjectionRef, sourceRefs, schemaRef, policyDecisionRef, policyVersion, purpose, recipientScope, destination, targetExportId, replacesExportId, envelopeHash, eligibility, reasonCode, rowVersion, createdAt, PRIMARY KEY(country, exportId), UNIQUE(country, requesterPrincipal, idemKey));
CREATE TABLE DataPolicyVersion(policyId, version, policyDigest, fieldAllowlist, classification, scopeConditions, legalEvidenceRef, securityEvidenceRef, authorId, activationApproverId, status, createdAt);
CREATE TABLE ExportOutbox(country, exportId, destination, envelopeJson, deliveryState, attemptId, leaseEpoch, nextCheckAt, rowVersion);
CREATE TABLE ExportAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
EX.R = Repo('sqlite', cf); mode = dict(st=404, body={}); os.environ['FP_API_URL'] = 'http://fp'; EX.FETCH = lambda url: (mode['st'], json.dumps(mode['body']).encode())
srv = make_server(8849, EX.route, EX.health, EX.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8849'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
def body(**kw):
    b = dict(schemaRef='ama.disclosure.v1', country='KR', purpose='customer-disclosure', recipientScope='CUSTOMER-A', destination='HQ-S10', operation='snapshot', sourceProjectionRef=dict(ownerService='S05', projectionId=str(uuid.uuid4()), projectionVersion='1', contentHash='a' * 64), sourceRefs=[dict(owner='S02', id='r1', rev=1, digest='b' * 64)], plantScope='KR-01'); b.update(kw)
    b['digest'] = K.request_digest(b); return b
def post(b, k, h=None): return call('POST', '/v1/exports', b, dict({'Idempotency-Key': k, 'X-Actor': 'owner-s05'}, **(h or {})))
c, d = call('POST', '/v1/exports', body()); chk('Idempotency-Key 없으면 400', c == 400, d)
B0 = body(); c, d = post(B0, 'e1'); eid = d.get('exportId'); chk('소유 API 확인 불가 → 422 UNKNOWN/BLOCKED_DEPENDENCY(outbox·송신 없음, retryable)', c == 422 and d['eligibility'] == 'UNKNOWN' and d['reasonCode'] == 'BLOCKED_DEPENDENCY' and d['retryable'] is True, (c, d))
c, d2 = post(B0, 'e1'); chk('같은 키·같은 digest → 같은 exportId(재심사 없이 기록 반환)', d2['exportId'] == eid and d2['replay'] is True, d2)
c, d2 = post(dict(B0, purpose='other', digest=K.request_digest(dict({k: v for k, v in B0.items() if k != 'digest'}, purpose='other'))), 'e1'); chk('같은 키·다른 digest → 409', c == 409 and d2['code'] == 'KEY_DIGEST_CONFLICT', (c, d2))
mode.update(st=200, body=dict(status='published')); c, d = post(body(), 'e2'); chk('소유 projection이 published여도 활성 정책 없음 → BLOCK/NO_ACTIVE_POLICY(허용 추정 없음)', c == 422 and d['eligibility'] == 'BLOCK' and d['reasonCode'] == 'NO_ACTIVE_POLICY', (c, d))
mode.update(st=200, body=dict(status='withdrawn')); c, d = post(body(), 'e3'); chk('원천 철회/비가용 → BLOCK/SOURCE_NOT_USABLE', d['reasonCode'] == 'SOURCE_NOT_USABLE', d); mode.update(st=404)
b = body(); b['digest'] = '0' * 64; c, d = post(b, 'e4'); chk('digest 불일치 400', c == 400 and d['code'] == 'DIGEST_MISMATCH', d)
c, d = post(body(country='JP'), 'e5'); chk('본문 country 불일치 403', c == 403 and d['code'] == 'COUNTRY_MISMATCH', d)
b = body(); b['payload'] = {'x': 1}; b['digest'] = K.request_digest(b); c, d = post(b, 'e6'); chk('임의 payload 금지 422', c == 422 and d['code'] == 'FORBIDDEN_FIELD', d)
for n, kw in [('correction은 targetExportId·replacesExportId 필요', dict(operation='correction', targetExportId='t')), ('withdrawal은 targetExportId 필요', dict(operation='withdrawal')), ('operation 값 검증', dict(operation='delete')), ('owner 검증(S99)', dict(sourceProjectionRef=dict(ownerService='S99', projectionId='x', projectionVersion='1', contentHash='a' * 64)))]:
    bb = body(**kw); c, d = post(bb, 'v-' + str(abs(hash(n)))); chk(n + ' → 400', c == 400, (c, d))
c, d = call('GET', '/v1/exports/' + eid); chk('상태 조회: payload·ack·outbox 없음', c == 200 and d['payloadIncluded'] is False and d['outboxState'] is None and d['ack'] is None and d['eligibility'] == 'UNKNOWN', d)
c, d = call('GET', '/v1/exports/' + str(uuid.uuid4())); chk('없는 반출 404', c == 404, d)
c, d = call('GET', '/v1/exports/zzz'); chk('형식 오류 400', c == 400, d)
c, d = call('GET', '/v1/data-policies'); chk('활성 정책 없음(items 0)', c == 200 and d['items'] == [] and d['active'] == [], d)
rows = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT prevHash, hash FROM dbo.ExportAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and len(rows) >= 3)
out = EX.R.tx(lambda cur: (EX.R.ex(cur, 'SELECT COUNT(*) FROM dbo.ExportOutbox'), cur.fetchall())[1]); chk('outbox 0건(ALLOW만 생성)', out[0][0] == 0)
c, d = call('GET', '/health'); chk('health(송신 닫힘 표시)', c == 200 and '닫힘' in d['mode'], d)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
