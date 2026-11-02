#!/usr/bin/env python3
"""fp-api — S05 API05·공개 통제 경로(체크리스트 2-5-2~2-5-4). 설계: design/services/S05 §3~6.
현재 상태: S02 발행본(release)이 없다(certified 차단) → 모든 요청은 waiting_source로 남고 수치·QuoteFootprint·공개본은 만들지 않는다. 공개 생성은 422(차단 사유 명시), 상태 증명은 서명 키 미구성으로 503, 반출 projection은 차단.
고객 직접 조회는 S10 API13 단일화안이며 고객 IdP·권한 출처 미결이라 이 서비스는 내부 호출 전용이다(사용자 인가는 S07 이후, X-Actor는 미검증 라벨). 감사는 상태 변경과 같은 트랜잭션(해시 체인).
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, CALC_API_URL(S02 소유 API로 발행본 상태 확인)."""
import os, sys, json, uuid, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import fp_core as K
VERSION = 'fp-api/0.1'; COUNTRY, ORG = 'KR', 'AMA-KR'; STATS = {}; R = None; FETCH = http_get
def A(cur, actor, action, target, before=None, after=None, reason='', cid=None):
    R.chain(cur, 'FootprintAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
def source_state(release_ref):
    """S02 API03 재조회(권위). 반환 (상태, 사유). 이벤트·과거 응답으로 대신하지 않는다."""
    if not release_ref or not release_ref.get('releaseId'): return 'waiting_source', 'SOURCE_RELEASE_REQUIRED'
    url = os.environ.get('CALC_API_URL', '').rstrip('/') + '/v1/releases/' + str(release_ref['releaseId'])
    st, body = FETCH(url)
    if st == 404: return 'waiting_source', 'SOURCE_RELEASE_NOT_FOUND'
    if st != 200: return 'waiting_source', 'SOURCE_STATE_UNKNOWN'
    rel = json.loads(body); s, why, ok, _ = K.classify_source(dict(status=rel.get('status'), usable=not rel.get('restrictionFlag', False)))
    return ('ready', None) if ok else (s, why)      # ready여도 수치 생성은 S02 manifest 계약(미합의) 전이라 아직 하지 않는다
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    try: kind = K.validate_request(body)
    except K.Reject as e: raise ApiError(e.status, e.code, e.msg + (' (' + ', '.join(e.fields) + ')' if e.fields else ''))
    plant = str(body.get('plantId') or 'KR-01')
    if plant != 'KR-01': raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역 DB05는 KR-01만 다룹니다.')
    rd = sha(canon({k: v for k, v in body.items()})); rid = str(uuid.uuid4()); state, why = source_state(body.get('releaseRef')); t = ts(); q, per = body['quantity'], body['period']
    def f(cur):
        R.ex(cur, 'SELECT requestId, requestDigest FROM dbo.CustomerRequest WHERE country=%s AND orgId=%s AND principal=%s AND idemKey=%s', (COUNTRY, ORG, actor, idem[:100])); x = cur.fetchall()
        if x:
            if x[0][1] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
            return 200, x[0][0]
        R.ex(cur, 'INSERT INTO dbo.CustomerRequest(requestId, country, orgId, plantId, principal, idemKey, requestDigest, kind, quoteId, shipmentId, productId, batchRefs, quantityValue, quantityUnit, declaredUnit, boundary, periodStart, periodEnd, recipientScope, purpose, schemaVersion, releaseRef, sourceVersion, assumptionRef, requestState, waitReason, footprintStatus, rev, correlationId, createdAt, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s)',
            (rid, COUNTRY, ORG, plant, actor, idem[:100], rd, kind, body.get('quoteId'), body.get('shipmentId'), body['productId'][:80], json.dumps(body['batchRefs']), q['value'], q['unit'][:16], json.dumps(body['declaredUnit']), json.dumps(body['boundary']), per['start'].replace('T', ' ').replace('Z', '')[:23], per['end'].replace('T', ' ').replace('Z', '')[:23], body['recipientScope'][:40], body['purpose'][:40], body['schemaVersion'][:24], json.dumps(body.get('releaseRef')) if body.get('releaseRef') else None, body.get('sourceVersion'), body.get('assumptionRef'), state, why, 'none', cid, t, t))
        A(cur, actor, 'FOOTPRINT_REQUEST', rid, after='1', reason=state + ' ' + (why or ''), cid=cid); return 202, rid
    c, rid2 = R.tx(f); return c, view(get_row(rid2))
RC = 'requestId, kind, quoteId, shipmentId, productId, requestState, waitReason, footprintStatus, rev, recipientScope, purpose, createdAt, updatedAt'
def get_row(rid): return R.tx(lambda cur: (R.ex(cur, 'SELECT ' + RC + ' FROM dbo.CustomerRequest WHERE requestId=%s', (rid,)), cur.fetchall())[1])
def view(x):
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 요청이 없습니다.')
    x = x[0]; return dict(requestId=x[0], operationId=x[0], kind=x[1], quoteId=x[2], shipmentId=x[3], productId=x[4], requestState=x[5], waitReason=x[6], footprintStatus=x[7], rev=x[8], recipientScope=x[9], purpose=x[10], result=None, disclosable=False, statusUrl='/v1/footprint-requests/' + x[0], createdAt=iso(x[11]), updatedAt=iso(x[12]),
                          label={'waiting_source': '자료 대기(수치 없음)', 'ready': '준비됨', 'received': '접수', 'rejected': '반려'}.get(x[5], x[5]), note='수치는 S02 발행본에서만 제공되며 현재 발행본이 없어 result는 없습니다. 0이나 추정값으로 채우지 않습니다.')
def get_request(rid):
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'requestId 형식이 올바르지 않습니다.')
    return view(get_row(rid))
def shipment_footprint(sid, qs):
    x = R.tx(lambda cur: (R.ex(cur, R.top('SELECT ' + RC + ' FROM dbo.CustomerRequest WHERE shipmentId=%s ORDER BY createdAt DESC'), (sid,)), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 출하의 탄소정보 요청이 없습니다.')
    w = x[0][6] or ''
    if w == 'SOURCE_STATE_UNKNOWN': raise ApiError(503, 'SOURCE_STATE_UNKNOWN', '산정 발행본 상태를 확인하지 못해 수치를 제공하지 않습니다.', True)
    if w in ('SOURCE_SUPERSEDED', 'SOURCE_REVOKED'): raise ApiError(410, w, '원천 발행본이 대체·철회되어 수치를 제공하지 않습니다.')
    raise ApiError(409, 'FOOTPRINT_NOT_AVAILABLE', '수치를 제공할 수 없습니다: %s (S02 발행본 필요, 후보는 수치로 제공하지 않음)' % (w or 'NO_RESULT'))
def blocked(h, cid, action, code, msg, status=422):
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]; R.tx(lambda cur: A(cur, actor, action, '-', reason=code, cid=cid)); raise ApiError(status, code, msg, status == 503)
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/footprint-requests': return create(body, h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'footprint-requests': return 200, get_request(P[3])
    if m == 'GET' and len(P) == 5 and P[2] == 'shipments' and P[4] == 'footprint': shipment_footprint(P[3], qs)
    if m == 'POST' and p == '/v1/disclosure-releases': blocked(h, cid, 'DISCLOSURE_CREATE_ATTEMPT', 'DISCLOSURE_BLOCKED', '공개본을 만들 수 없습니다: 확인된 S02 발행본(수치) 없음, S07 공개 정책·승인(D12) 미결, 고객 IdP·권한 출처 미결, 외부 고객 노출 닫힘.')
    if m == 'POST' and len(P) == 5 and P[2] == 'disclosure-releases' and P[4] in ('corrections', 'withdrawals'): raise ApiError(404, 'NOT_FOUND', '대상 공개본이 없습니다(공개본 생성이 차단되어 존재하지 않음).')
    if m == 'GET' and len(P) == 5 and P[2] == 'disclosure-releases' and P[4] in ('status', 'export-projection'): raise ApiError(404, 'NOT_FOUND', '대상 공개본이 없습니다.')
    if m == 'POST' and len(P) == 5 and P[2] == 'disclosure-releases' and P[4] == 'status-proofs': blocked(h, cid, 'STATUS_PROOF_ATTEMPT', 'SIGNING_KEY_NOT_CONFIGURED', '상태 증명 서명 키·알고리즘·시계 검증 정책이 구성되지 않아 증명을 발급하지 않습니다.', 503)
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.CustomerRequest), (SELECT COUNT(*) FROM dbo.FootprintAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, requests=s[0], audits=s[1], errors=R.err, last_err=R.last_err), mode='no-release(S02 발행본 없음)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
