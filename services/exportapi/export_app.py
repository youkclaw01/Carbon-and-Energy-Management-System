#!/usr/bin/env python3
"""export-api — S09 API11 POST /v1/exports · GET /v1/exports/{id} (체크리스트 2-6-2~2-6-3). 설계: design/services/S09 §3~5.
현재: 활성 DataPolicyVersion이 없고(법적 근거·보안 근거 미확인), 소유 API(S05 export-projection 등)가 승인 view를 제공하지 않아 모든 반출은 BLOCK/UNKNOWN(422)이며 outbox·송신·ack는 만들지 않는다. 사용자 요청: 국외 자료 이전 제외 — 이 서비스는 송신을 열지 않는다.
country·senderId는 서버가 도출(이 지역 KR 고정), 본문 country 불일치는 403. 사용자 인가는 S07 이후(X-Actor 미검증 라벨). 감사는 같은 트랜잭션 해시 체인.
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, FP_API_URL(S05 소유 API)."""
import os, sys, json, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import export_core as K
VERSION = 'export-api/0.1'; COUNTRY, SENDER = 'KR', 'S09-KR'; STATS = {}; R = None; FETCH = http_get
def A(cur, actor, action, target, reason='', cid=None, before=None, after=None):
    R.chain(cur, 'ExportAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def projection_state(b):
    """소유 서비스의 등록된 API로만 재확인한다. 미지원·미합의·장애는 None(불명)이며 일반 응답/Blob/SQL로 보충하지 않는다."""
    sp = b['sourceProjectionRef']
    if sp['ownerService'] == 'S05' and os.environ.get('FP_API_URL'):
        st, body = FETCH(os.environ['FP_API_URL'].rstrip('/') + '/v1/disclosure-releases/%s/export-projection?revision=%s&purpose=%s' % (sp['projectionId'], sp['projectionVersion'], b['purpose']))
        if st == 200:
            d = json.loads(body); return dict(status=d.get('status', 'unknown'))
    return None
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    try: K.validate(body)
    except K.Reject as e: raise ApiError(e.status, e.code, e.msg)
    if body['country'] != COUNTRY: raise ApiError(403, 'COUNTRY_MISMATCH', '인증된 지역의 국가와 본문 country가 다릅니다(본문 값은 대조용).')
    rd = K.request_digest(body)
    if body['digest'] != rd: raise ApiError(400, 'DIGEST_MISMATCH', 'digest가 정규화 규칙(키 정렬·digest 자신 제외)으로 계산한 값과 다릅니다.')
    ps = projection_state(body); elig, reason, http = K.review(body, None, ps, False)      # 활성 정책 없음(조회 결과 없음)
    eid = str(uuid.uuid4()); t = ts()
    def f(cur):
        R.ex(cur, 'SELECT exportId, requestDigest, eligibility, reasonCode FROM dbo.ExportRelease WHERE country=%s AND requesterPrincipal=%s AND idemKey=%s', (COUNTRY, actor, idem[:100])); x = cur.fetchall()
        if x:
            if x[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 digest입니다.')
            return x[0][0], x[0][2], x[0][3], True
        R.ex(cur, 'SELECT activationApproverId FROM dbo.DataPolicyVersion WHERE status=%s', ('active',)); pol = cur.fetchall()
        e2, r2, h2 = (elig, reason, http) if not pol else K.review(body, pol[0], ps, False)
        R.ex(cur, 'INSERT INTO dbo.ExportRelease(country, exportId, requesterPrincipal, idemKey, requestDigest, sourceOwner, senderId, operation, sourceProjectionRef, sourceRefs, schemaRef, policyDecisionRef, purpose, recipientScope, destination, targetExportId, replacesExportId, eligibility, reasonCode, rowVersion, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s)',
            (COUNTRY, eid, actor, idem[:100], rd, body['sourceProjectionRef']['ownerService'], SENDER, body['operation'], json.dumps(body['sourceProjectionRef']), json.dumps(body['sourceRefs']), body['schemaRef'][:80], body.get('policyDecisionRef'), body['purpose'][:40], body['recipientScope'][:40], body['destination'][:60], body.get('targetExportId'), body.get('replacesExportId'), e2, r2, t))
        A(cur, actor, 'EXPORT_REVIEW', eid, reason=e2 + ' ' + r2, cid=cid); return eid, e2, r2, False
    eid2, e2, r2, replay = R.tx(f)
    if e2 == 'ALLOW': return 202, dict(exportId=eid2, eligibility=e2, outboxState='PENDING', rowVersion=1)
    raise_ = dict(exportId=eid2, eligibility=e2, reasonCode=r2, retryable=(e2 == 'UNKNOWN'), correlationId=cid, replay=replay, note='반출이 차단되었습니다. 송신·outbox·ack는 만들지 않았습니다(활성 정책·법적 근거·소유 API 확인 없음).')
    return 422, raise_
def get_export(eid):
    try: uuid.UUID(eid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'exportId 형식이 올바르지 않습니다.')
    x = R.tx(lambda cur: (R.ex(cur, 'SELECT exportId, operation, eligibility, reasonCode, sourceOwner, purpose, recipientScope, destination, rowVersion, createdAt FROM dbo.ExportRelease WHERE country=%s AND exportId=%s', (COUNTRY, eid)), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 반출 요청이 없습니다.')
    x = x[0]; return dict(exportId=x[0], operation=x[1], eligibility=x[2], reasonCode=x[3], sourceOwner=x[4], purpose=x[5], recipientScope=x[6], destination=x[7], rowVersion=x[8], createdAt=iso(x[9]), outboxState=None, ack=None, payloadIncluded=False)
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/exports': return create(body, h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'exports': return 200, get_export(P[3])
    if m == 'GET' and p == '/v1/data-policies':
        rows = R.tx(lambda cur: (R.ex(cur, 'SELECT policyId, version, status, classification FROM dbo.DataPolicyVersion ORDER BY createdAt DESC'), cur.fetchall())[1]); return 200, dict(items=[dict(policyId=r[0], version=r[1], status=r[2], classification=r[3]) for r in rows], active=[r[0] for r in rows if r[2] == 'active'])
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.ExportRelease), (SELECT COUNT(*) FROM dbo.ExportOutbox), (SELECT COUNT(*) FROM dbo.ExportAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, exports=s[0], outbox=s[1], audits=s[2], errors=R.err, last_err=R.last_err), mode='송신 닫힘(활성 정책 없음)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
