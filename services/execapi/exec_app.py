#!/usr/bin/env python3
"""exec-api — S08 API09 POST /v1/executions · GET /v1/executions/{id} (체크리스트 2-11-2~2-11-3). 설계: design/services/S08 §2~4.
v0.2(2026-10-31): 서명 permit을 S07에서 검증받고(permit-sign-v1 digest 재계산 → DB 상태·Key Vault ES256 verify) 통과한 건만 **모의 제공자(sim-provider)** 로 실행한다. 실거래·외부 송신은 없다.
검증은 S07 approval-api(APPROVAL_API_URL)의 POST /v1/permits/verify에 맡기며 exec-api는 서명 키 권한이 없다. 검증기가 없으면 이전처럼 닫힘(503 PERMIT_VERIFICATION_UNAVAILABLE).
사용 1회: permitId UNIQUE(ExecutionIntentRef)로 같은 permit의 두 번째 실행을 막는다(S07 claim API가 없어 S08 로컬 보증, 한계는 문서화). 같은 작업 재요청은 기존 실행을 200으로 돌려준다.
상태: accepted → sending → executed(모의 영수증 검증됨). 대사(POST /v1/executions/{id}/reconcile)는 영수증 payloadDigest를 다시 계산해 불일치면 review-required.
오류 봉투: {code, message, retryable, correlationId, reasonCode}."""
import os, sys, json, uuid, base64, datetime as dt, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
VERSION = 'exec-api/0.4'; STATS = {}; R = None; VERIFIER = None; COUNTRY = os.environ.get('COUNTRY', 'KR'); ORG = os.environ.get('ORG_ID', 'AMA'); PROVIDER = 'sim-provider'
REQ = ('schemaVersion', 'sourceService', 'businessOperationId', 'intentId', 'intentVersion', 'intentDigest', 'canonicalizationVersion', 'digestAlgorithm', 'sourceProjectionRef', 'signedPermit', 'fencingEpoch')
CANON, ALG = 'ama.intent.v1/jcs-1', 'sha256'
PERMIT_FIELDS = ('permitId', 'requestId', 'operationKey', 'intentDigest', 'approvalVersion', 'authorityVersion', 'reservationId', 'amountMinor', 'currency', 'expiresAt')
def permit_digest(p):
    """S07 approval-api의 permit_payload와 같은 규칙(permit-sign-v1)."""
    return sha(canon(dict(profile='permit-sign-v1', **{k: p[k] for k in PERMIT_FIELDS})))
class PermitVerifier:
    """permit 검증은 S07(approval-api)에 맡긴다(POST /v1/permits/verify: DB 상태 active·사용 금지 아님·서명 일치·Key Vault 서명 검증). exec-api는 서명 키 권한을 갖지 않는다."""
    def __init__(self, url): self.url = url.rstrip('/')
    def verify_permit(self, pm):
        rq = urllib.request.Request(self.url + '/v1/permits/verify', data=json.dumps(pm).encode(), method='POST', headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(rq, timeout=20) as r: d = json.loads(r.read())
        return bool(d.get('valid')), str(d.get('reason') or '')
    def claim_permit(self, permit_id, claimant):
        """S07 POST /v1/permits/claim: 1회 사용 확정. 같은 claimant의 재호출은 replay로 성공, 다른 claimant는 거절."""
        rq = urllib.request.Request(self.url + '/v1/permits/claim', data=json.dumps(dict(permitId=permit_id, claimant=claimant)).encode(), method='POST', headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(rq, timeout=20) as r: d = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 409:
                try: d = json.loads(e.read())
                except Exception: d = {}
                return False, str(d.get('reason') or d.get('code') or 'CONFLICT')
            raise
        return bool(d.get('claimed')), ('REPLAY' if d.get('replay') else 'CLAIMED')
def A(cur, actor, action, target, reason='', cid=None):
    R.chain(cur, 'ExecutionAudit', 'hash', 'auditId', dict(actor=(actor or 'unauthenticated')[:120], action=action, target=target, beforeVersion=None, afterVersion=None, reason=(reason or '')[:300], correlationId=cid))
def create(body, h, cid):
    if not h.get('Idempotency-Key'): raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    for k in REQ:
        if k not in body or body[k] in (None, ''): raise ApiError(400, 'BAD_REQUEST', k + ' 필요')
    if body['sourceService'] not in ('S04', 'S05'): raise ApiError(422, 'BINDING_MISMATCH', 'sourceService는 S04 또는 S05입니다.')
    if body['canonicalizationVersion'] != CANON or body['digestAlgorithm'] != ALG: raise ApiError(422, 'BINDING_MISMATCH', '등록되지 않은 정규화/알고리즘 규약입니다(관용 동치 없음).')
    sp = body['sourceProjectionRef']
    if not isinstance(sp, dict) or not sp.get('projectionId') or not sp.get('projectionVersion') or not sp.get('contentHash'): raise ApiError(422, 'BINDING_MISMATCH', 'sourceProjectionRef{projectionId, projectionVersion, contentHash} 필요')
    if any(isinstance(body.get(k), (dict, list)) and k not in ('sourceProjectionRef',) for k in ('intentDigest', 'businessOperationId')): raise ApiError(422, 'BINDING_MISMATCH', '필드 형식 오류')
    if VERIFIER is None:
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'EXECUTION_ATTEMPT_REJECTED', str(body['businessOperationId'])[:120], 'PERMIT_VERIFICATION_UNAVAILABLE', cid))
        raise ApiError(503, 'PERMIT_VERIFICATION_UNAVAILABLE', '실행이 닫혀 있습니다: permit 서명 검증 키가 구성되지 않았습니다. 실행 접수·송신·성공 ack를 만들지 않았습니다.', False)
    pm = body['signedPermit']
    if not isinstance(pm, dict) or any(pm.get(k) in (None, '') for k in PERMIT_FIELDS + ('signature', 'keyRef')): raise ApiError(422, 'PERMIT_MALFORMED', 'signedPermit 필드가 부족합니다.')
    opid = str(body['businessOperationId'])[:100]
    # 1) 같은 작업·같은 permit 재요청이면 검증·claim 없이 기존 실행을 돌려준다(이미 claim된 permit은 검증을 통과하지 못하므로 먼저 확인)
    rp = R.tx(lambda cur: (R.ex(cur, 'SELECT executionId, permitId, intentDigest, executionState FROM dbo.ExecutionIntentRef WHERE country=%s AND sourceService=%s AND businessOperationId=%s', (COUNTRY, body['sourceService'], opid)), cur.fetchall())[1])
    if rp:
        if rp[0][1] == pm['permitId'] and rp[0][2] == body['intentDigest']: return 200, dict(executionId=rp[0][0], executionState=rp[0][3], replay=True)
        raise ApiError(409, 'OPERATION_CONFLICT', '같은 작업 ID에 다른 permit·digest가 이미 있습니다.')
    # 2) S07 검증(서명·상태) → 요청과의 결속 → S07 claim(1회 사용의 권위는 S07) → 로컬 실행 기록
    try: good, why = VERIFIER.verify_permit(dict({k: pm[k] for k in PERMIT_FIELDS + ('signature', 'keyRef')}))
    except Exception:
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'EXECUTION_ATTEMPT_REJECTED', opid, 'PERMIT_VERIFY_ERROR', cid))
        raise ApiError(503, 'PERMIT_VERIFICATION_UNAVAILABLE', 'permit 서명 검증을 완료하지 못했습니다. 접수·송신하지 않았습니다.', True)
    if not good:
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'EXECUTION_ATTEMPT_REJECTED', opid, 'PERMIT_INVALID:' + why[:40], cid))
        raise ApiError(422, 'PERMIT_INVALID', 'permit이 유효하지 않습니다(' + why + ').')
    if str(pm['expiresAt']) <= iso(now()): raise ApiError(422, 'PERMIT_EXPIRED', 'permit이 만료되었습니다.')
    if pm['intentDigest'] != body['intentDigest'] or pm['operationKey'] != str(body['businessOperationId']): raise ApiError(422, 'BINDING_MISMATCH', 'permit의 intentDigest·operationKey가 요청과 다릅니다.')
    if not isinstance(body['intentVersion'], int): raise ApiError(422, 'BINDING_MISMATCH', 'intentVersion은 정수입니다.')
    eid = str(uuid.uuid4()); aid = str(uuid.uuid4()); rid_ = str(uuid.uuid4())
    def pre(cur):
        R.ex(cur, 'SELECT executionId FROM dbo.ExecutionIntentRef WHERE permitId=%s', (pm['permitId'],))
        if cur.fetchall(): return 'PERMIT_ALREADY_USED'
        R.ex(cur, 'SELECT blocked FROM dbo.PermitGate WHERE permitId=%s', (pm['permitId'],)); g = cur.fetchall()
        return 'PERMIT_BLOCKED' if g and g[0][0] else None
    bad = R.tx(pre)
    if bad: raise ApiError(409, bad, {'PERMIT_ALREADY_USED': '이 permit은 이미 사용되었습니다(1회 사용).', 'PERMIT_BLOCKED': 'permit이 차단되었습니다.'}[bad])
    try: cl, cwhy = VERIFIER.claim_permit(pm['permitId'], eid)
    except Exception:
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'EXECUTION_ATTEMPT_REJECTED', opid, 'PERMIT_CLAIM_ERROR', cid))
        raise ApiError(503, 'PERMIT_CLAIM_UNAVAILABLE', 'permit 사용 확정(claim)을 완료하지 못했습니다. 접수·송신하지 않았습니다.', True)
    if not cl:
        R.tx(lambda cur: A(cur, h.get('X-Actor'), 'EXECUTION_ATTEMPT_REJECTED', opid, 'PERMIT_CLAIM_DENIED:' + cwhy[:40], cid))
        raise ApiError(409, 'PERMIT_ALREADY_USED' if cwhy == 'ALREADY_CLAIMED' else 'PERMIT_CLAIM_DENIED', 'S07이 permit 사용을 확정하지 않았습니다(' + cwhy + ').')
    def f(cur):
        t = ts(); dl = ts(now() + dt.timedelta(minutes=5))
        R.ex(cur, 'SELECT blocked FROM dbo.PermitGate WHERE permitId=%s', (pm['permitId'],))
        if not cur.fetchall(): R.ex(cur, 'INSERT INTO dbo.PermitGate(permitId, blocked, blockVersion, executionEpoch, dispatchStartedCount) VALUES (%s,0,0,1,1)', (pm['permitId'],))
        R.ex(cur, 'INSERT INTO dbo.ExecutionIntentRef(executionId, country, orgId, plantId, permitId, sourceService, businessOperationId, intentId, intentVersion, intentDigest, canonicalizationVersion, digestAlgorithm, executionState, rowVersion, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (eid, COUNTRY, ORG, str(body.get('plantId') or 'NA')[:32], pm['permitId'], body['sourceService'], opid, str(body['intentId'])[:60], body['intentVersion'], body['intentDigest'], CANON, ALG, 'sending', 2, t))
        R.ex(cur, 'INSERT INTO dbo.ExecutionAttempt(attemptId, executionId, attemptNo, executionEpoch, claimId, authorityVersion, sendState, startedAt, deadline, lastCheckedAt) VALUES (%s,%s,1,1,%s,%s,%s,%s,%s,%s)', (aid, eid, eid, int(pm['authorityVersion']), 'sent', t, dl, t))
        rcpt = receipt_for(eid, aid)
        R.ex(cur, 'INSERT INTO dbo.ExternalReceipt(receiptObservationId, executionId, attemptId, providerId, externalReceiptId, receiptVersion, payloadDigest, verified, observedAt, ownerEffectId, effectVersion, quantityStatus, quantityValue, quantityUnit) VALUES (%s,%s,%s,%s,%s,1,%s,1,%s,%s,1,%s,NULL,NULL)', (rid_, eid, aid, PROVIDER, rcpt['externalReceiptId'], rcpt['payloadDigest'], t, 'SIM-EFFECT-' + eid[:8], 'NOT_APPLICABLE'))
        R.ex(cur, "UPDATE dbo.ExecutionIntentRef SET executionState='executed', rowVersion=3 WHERE executionId=%s", (eid,))
        A(cur, h.get('X-Actor'), 'EXECUTION_SIMULATED', eid, 'sim-provider receipt ' + rcpt['externalReceiptId'] + ' · S07 claim ' + cwhy, cid)
        return 201, dict(executionId=eid, executionState='executed', provider=PROVIDER, simulated=True, attemptId=aid, externalReceiptId=rcpt['externalReceiptId'], permitId=pm['permitId'], claimedBy='S07', note='모의 제공자 실행입니다. 실거래·외부 송신은 없습니다.')
    return R.tx(f)
def receipt_for(eid, aid):
    rid = 'SIM-' + sha(eid + '|' + aid)[:16]; return dict(externalReceiptId=rid, payloadDigest=sha(canon(dict(provider=PROVIDER, executionId=eid, attemptId=aid, externalReceiptId=rid))))
def _uuid(eid):
    try: uuid.UUID(eid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'executionId 형식이 올바르지 않습니다.')
def _load(cur, eid):
    R.ex(cur, 'SELECT executionId, permitId, sourceService, businessOperationId, intentId, intentVersion, intentDigest, executionState, createdAt FROM dbo.ExecutionIntentRef WHERE executionId=%s', (eid,)); x = cur.fetchall()
    if not x: return None
    R.ex(cur, 'SELECT attemptId, attemptNo, sendState, startedAt FROM dbo.ExecutionAttempt WHERE executionId=%s ORDER BY attemptNo', (eid,)); at = cur.fetchall()
    R.ex(cur, 'SELECT attemptId, providerId, externalReceiptId, payloadDigest, verified, quantityStatus FROM dbo.ExternalReceipt WHERE executionId=%s', (eid,)); rc = cur.fetchall()
    return x[0], at, rc
def get_exec(eid):
    _uuid(eid); r = R.tx(lambda cur: _load(cur, eid))
    if not r: raise ApiError(404, 'NOT_FOUND', '해당 범위에 실행 기록이 없습니다(존재·미전송·해제의 증거가 아닙니다).')
    x, at, rc = r
    return 200, dict(executionId=x[0], permitId=x[1], sourceService=x[2], businessOperationId=x[3], intentId=x[4], intentVersion=x[5], intentDigest=x[6], executionState=x[7], createdAt=str(x[8]), simulated=True,
                     attempts=[dict(attemptId=a[0], attemptNo=a[1], sendState=a[2], startedAt=str(a[3])) for a in at], receipts=[dict(attemptId=c[0], providerId=c[1], externalReceiptId=c[2], payloadDigest=c[3], verified=bool(c[4]), quantityStatus=c[5]) for c in rc])
def by_permits(qs):
    """permitId(UUID, 추측 불가) 목록으로만 실행 상태를 조회한다. 열거(전체 목록)는 제공하지 않는다. 최대 50건."""
    ids = [x for x in ','.join(qs.get('permitIds') or []).split(',') if x][:50]
    for i in ids: _uuid(i)
    if not ids: return 200, dict(items=[])
    def f(cur):
        R.ex(cur, 'SELECT executionId, permitId, executionState, createdAt FROM dbo.ExecutionIntentRef WHERE permitId IN (' + ','.join(['%s'] * len(ids)) + ')', tuple(ids)); ex = cur.fetchall(); out = []
        for e in ex:
            R.ex(cur, 'SELECT providerId, externalReceiptId, verified, quantityStatus FROM dbo.ExternalReceipt WHERE executionId=%s', (e[0],)); rc = cur.fetchall()
            out.append(dict(executionId=e[0], permitId=e[1], executionState=e[2], createdAt=str(e[3]), simulated=True, receipts=[dict(providerId=c[0], externalReceiptId=c[1], verified=bool(c[2]), quantityStatus=c[3]) for c in rc]))
        return out
    return 200, dict(items=R.tx(f))
def reconcile(eid, h, cid):
    """모의 영수증 대사: 기록된 payloadDigest를 다시 계산해 일치하면 executed 유지, 아니면 review-required(자동 재송신 없음)."""
    _uuid(eid)
    def f(cur):
        r = _load(cur, eid)
        if not r: return None
        x, at, rc = r; good = bool(rc) and all(c[3] == receipt_for(eid, c[0])['payloadDigest'] and c[2] == receipt_for(eid, c[0])['externalReceiptId'] and c[1] == PROVIDER and c[4] for c in rc)
        st = 'executed' if good and x[7] in ('executed', 'reconciling') else 'review-required'
        if st != x[7]: R.ex(cur, 'UPDATE dbo.ExecutionIntentRef SET executionState=%s, rowVersion=rowVersion+1 WHERE executionId=%s', (st, eid))
        A(cur, h.get('X-Actor'), 'EXECUTION_RECONCILED', eid, st, cid); return dict(executionId=eid, executionState=st, receiptsChecked=len(rc), matched=good)
    d = R.tx(f)
    if d is None: raise ApiError(404, 'NOT_FOUND', '해당 범위에 실행 기록이 없습니다(존재·미전송·해제의 증거가 아닙니다).')
    return 200, d
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/executions': return create(body, h, cid)
    if m == 'GET' and p == '/v1/executions': return by_permits(qs)
    if m == 'GET' and len(P) == 4 and P[2] == 'executions': return get_exec(P[3])
    if m == 'POST' and len(P) == 5 and P[2] == 'executions' and P[4] == 'reconcile': return reconcile(P[3], h, cid)
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.ExecutionIntentRef), (SELECT COUNT(*) FROM dbo.ExecutionAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, executions=s[0], audits=s[1], errors=R.err, last_err=R.last_err), mode=('모의 실행(S07 permit 검증 후 sim-provider·실거래 없음)' if VERIFIER else '실행 닫힘(permit 검증 미구성·실거래 없음)'), **STATS)
def main():
    global R, VERIFIER
    R = sql_repo(); u = os.environ.get('APPROVAL_API_URL'); VERIFIER = PermitVerifier(u) if u else None; make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
