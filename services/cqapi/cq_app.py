#!/usr/bin/env python3
"""central-query — S10 API12 수신·API13 조회 경계 (체크리스트 2-7-2~2-7-3). 설계: design/services/S10 §2~5.
API12(POST /v1/federated-snapshots)와 ack 조회(GET .../{exportId}/ack)는 구현됐으나 **등록된 송신자가 없으면 닫혀 있다**: 송신자는 환경 비밀 FEDERATION_SENDERS(JSON {senderId:{keyRef,country,destination,classifications,status}}; 비밀 아님)로만 등록되고, 인증은 X-AMA-Sender-Id·Timestamp와 Key Vault ES256 서명(등록부의 keyRef로 verify)이다. 공유 비밀·환경 키가 없다(본문 country/senderId는 신원이 아니라 일치 검사 대상).
등록·송신 개시(S09 sender)는 국외 이전 승인 경계에 속하므로 건별 명시 승인 후에만 이루어진다. 이 서비스는 수신 측일 뿐 송신하거나 데이터를 가져오지 않는다.
고객 공개 경로(API13)는 닫혀 있다(고객 IdP·S05 현재성 증명 미결): 항상 503 DISCLOSURE_PATH_CLOSED. 포트폴리오는 수신된 허용 자료 projection만 보여 주며 없으면 0이 아니라 빈 목록이다."""
import os, sys, json, uuid, urllib.request
import cq_core as K
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
VERSION = 'central-query/0.3'; RECEIVER = 'S10-central-query-krc'; STATS = {}; R = None
def A(cur, actor, action, target, reason='', cid=None):
    R.chain(cur, 'CentralReadAudit', 'hash', 'auditId', dict(actor=(actor or 'unauthenticated')[:120], action=action, target=target, beforeVersion=None, afterVersion=None, reason=(reason or '')[:300], correlationId=cid))
SENDERS = {}; RATE = {}
KEYREF_RE = __import__('re').compile(r'^https://[a-z0-9-]{3,24}\.vault\.azure\.net/keys/[A-Za-z0-9-]{1,127}(/[0-9a-f]{32})?$')
class KvVerifier:
    """Key Vault EC P-256 공개 연산(verify)만 호출한다. 개인키·공유 비밀 없음. 이 서비스의 관리 ID에 해당 키의 Key Vault Crypto User(verify 가능)만 필요하다."""
    alg = 'ES256'
    def _tok(self):
        ep, hd = os.environ['IDENTITY_ENDPOINT'], os.environ['IDENTITY_HEADER']; u = ep + '?resource=https://vault.azure.net&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'X-IDENTITY-HEADER': hd}), timeout=10).read())['access_token']
    def __call__(self, key_ref, digest_hex, sig):
        b64 = lambda b: __import__('base64').urlsafe_b64encode(b).rstrip(b'=').decode()
        rq = urllib.request.Request(key_ref.rstrip('/') + '/verify?api-version=7.4', data=json.dumps(dict(alg=self.alg, digest=b64(bytes.fromhex(digest_hex)), value=sig)).encode(), method='POST', headers={'Authorization': 'Bearer ' + self._tok(), 'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(rq, timeout=20).read()).get('value') is True
VERIFY = KvVerifier()
def load_senders():
    """FEDERATION_SENDERS(JSON; 비밀 아님)로 송신자를 등록한다: {senderId:{keyRef,country,destination,classifications,status}}. keyRef는 Key Vault 키 URL이어야 하며 형식이 틀린 항목은 버린다. 비어 있으면 수신은 닫혀 있다."""
    global SENDERS
    try: raw = json.loads(os.environ.get('FEDERATION_SENDERS') or '{}')
    except Exception: raw = {}
    SENDERS = {k: v for k, v in raw.items() if isinstance(v, dict) and KEYREF_RE.match(str(v.get('keyRef', ''))) and len(str(v.get('country', ''))) == 2}
def rate_ok(sid, limit=60):
    t = int(now().timestamp() // 60); k = (sid, t)
    for o in [x for x in RATE if x[1] < t]: RATE.pop(o, None)
    RATE[k] = RATE.get(k, 0) + 1; return RATE[k] <= limit
def authed(h, data, cid, what, target):
    try: s = K.auth_sender(h, data, SENDERS, int(now().timestamp()), VERIFY)
    except Exception:
        R.tx(lambda cur: A(cur, 'unauthenticated:' + (h.get('X-AMA-Sender-Id') or '-')[:40], what, target, 'SENDER_KEY_VERIFY_UNAVAILABLE', cid))
        raise ApiError(503, 'SENDER_AUTH_UNAVAILABLE', '송신자 서명 검증(Key Vault)을 완료하지 못했습니다. 접수하지 않았습니다.', True)
    if not s:
        R.tx(lambda cur: A(cur, 'unauthenticated:' + (h.get('X-AMA-Sender-Id') or '-')[:40], what, target, 'UNAUTHENTICATED_SENDER', cid))
        raise ApiError(401, 'UNAUTHENTICATED_SENDER', '송신자 인증에 실패했습니다(등록된 송신자의 서명·시각 필요). 본문의 country/senderId는 신원으로 인정하지 않습니다.')
    if not rate_ok(s['senderId']): raise ApiError(429, 'RATE_LIMITED', '요청이 너무 많습니다.', True)
    return s
def ack_dict(ack_id, s, e, outcome_, recv, applied, recv_at, applied_at, rev):
    return dict(ackSchemaVersion='fed-ack-v1', ackId=ack_id, country=s['country'], senderId=s['senderId'], exportId=e['exportId'], envelopeHash=e['envelopeHash'], destination=e['destination'], receiverPrincipal=RECEIVER, outcome=outcome_, receivedSourceVersions=recv, appliedSourceVersions=applied, receivedAt=recv_at, appliedAt=applied_at, projectionRevision=rev)
def receive(body, h, cid):
    """API12 POST /v1/federated-snapshots — 인증 → 범위 → 검증 → 멱등 inbox → 적용 → 동기 200 ack(설계 S10 §5.1). 응답에 타 국가·송신자 정보를 싣지 않는다."""
    e = body if isinstance(body, dict) else {}
    s = authed(h, K.canon(e), cid, 'FEDERATION_RECEIVE_ATTEMPT', str(e.get('exportId') or '-')[:60])
    def deny(code, status, msg, why):
        R.tx(lambda cur: A(cur, 'S09:' + s['senderId'], 'FEDERATION_RECEIVE_REJECTED', str(e.get('exportId') or '-')[:60], why, cid)); raise ApiError(status, code, msg)
    try: K.validate(e, iso(now()))
    except K.Reject as r: deny(r.code, r.status, r.msg or r.code, r.code)
    if e['country'] != s['country'] or e['senderId'] != s['senderId'] or e['destination'] != s.get('destination') or e['classification'] not in s.get('classifications', []): deny('FORBIDDEN_SCOPE', 403, '송신자 범위(국가·목적지·분류)가 인증 신원과 일치하지 않습니다.', 'SCOPE')
    ctry, sid, xid = s['country'], s['senderId'], e['exportId']
    def f(cur):
        R.ex(cur, 'SELECT envelopeHash, ackBody FROM dbo.FederationInbox WHERE country=%s AND senderId=%s AND exportId=%s', (ctry, sid, xid)); r = cur.fetchall()
        if r:
            if r[0][0] == e['envelopeHash']: return 200, json.loads(r[0][1])  # 최초 저장 ack 그대로(당시 벡터·시각 재생성 금지)
            return 409, 'KEY_CONFLICT'
        known = {}
        for a in e['authorityStates']:
            R.ex(cur, 'SELECT statusVersion, tombstone FROM dbo.AuthorityState WHERE country=%s AND authority=%s AND objectId=%s', (ctry, a['authority'], a['objectId'])); g = cur.fetchall()
            if g: known[(a['authority'], a['objectId'])] = g[0][0]
        tomb = False
        for r_ in e['sourceRefs']:
            R.ex(cur, 'SELECT tombstone FROM dbo.AuthorityState WHERE country=%s AND authority=%s AND objectId=%s', (ctry, r_['authority'], r_['objectId'])); g = cur.fetchall()
            tomb = tomb or bool(g and g[0][0])
        tgt = e.get('targetExportId')
        if e['kind'] == 'correction':
            R.ex(cur, 'SELECT exportId FROM dbo.FederationInbox WHERE country=%s AND senderId=%s AND exportId=%s', (ctry, sid, tgt)); 
            if not cur.fetchall(): return 422, 'TARGET_UNKNOWN'
        t = ts(); recv = [dict(authority=a['authority'], objectId=a['objectId'], statusVersion=a['statusVersion']) for a in e['authorityStates']]
        out = 'recorded_stale' if (K.outcome(e, known) == 'recorded_stale' or (tomb and e['kind'] != 'withdrawal')) else 'applied'
        rev = None; applied = recv
        if out == 'applied':
            for a in e['authorityStates']:
                R.ex(cur, 'SELECT revision FROM dbo.AuthorityState WHERE country=%s AND authority=%s AND objectId=%s', (ctry, a['authority'], a['objectId']))
                ref = next((x for x in e['sourceRefs'] if x['authority'] == a['authority'] and x['objectId'] == a['objectId']), None) or dict(revision=0, digest='0' * 64)
                wd = e['kind'] == 'withdrawal' or a['status'] in ('revoked', 'withdrawn', 'superseded')
                if cur.fetchall(): R.ex(cur, 'UPDATE dbo.AuthorityState SET revision=%s, statusVersion=%s, status=%s, digest=%s, verifiedAt=%s, validUntil=%s, tombstone=%s, provenanceRef=%s WHERE country=%s AND authority=%s AND objectId=%s', (int(ref['revision']), a['statusVersion'], a['status'], ref['digest'], t, None, 1 if wd else 0, xid, ctry, a['authority'], a['objectId']))
                else: R.ex(cur, 'INSERT INTO dbo.AuthorityState(country, authority, objectId, revision, statusVersion, status, digest, verifiedAt, validUntil, tombstone, provenanceRef) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (ctry, a['authority'], a['objectId'], int(ref['revision']), a['statusVersion'], a['status'], ref['digest'], t, None, 1 if wd else 0, xid))
            if e['kind'] in ('withdrawal', 'correction'): R.ex(cur, "DELETE FROM dbo.PortfolioProjection WHERE country=%s AND projectionKey LIKE %s", (ctry, ctry + '|' + sid + '|' + tgt + '|%'))
            if e['kind'] != 'withdrawal':
                for it in e['payload']['items']:
                    R.ex(cur, 'INSERT INTO dbo.PortfolioProjection(projectionKey, orgId, country, plantScope, periodStart, periodEnd, boundaryRef, metric, unit, currency, valueDecimal, sourceRefs, sourceAsOf, lastVerifiedAt, validUntil, rowVersion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)',
                        (ctry + '|' + sid + '|' + xid + '|' + it['plantScope'] + '|' + it['metric'] + '|' + it['periodStart'], str(e['payload']['orgId'])[:40], ctry, it['plantScope'][:32], it['periodStart'].replace('T', ' ').rstrip('Z'), it['periodEnd'].replace('T', ' ').rstrip('Z'), it['boundaryRef'][:40], it['metric'][:60], it['unit'][:24], it.get('currency'), str(it['valueDecimal'])[:40], json.dumps(e['sourceRefs'])[:4000], e['issuedAt'].replace('T', ' ').rstrip('Z'), t, e['validUntil'].replace('T', ' ').rstrip('Z')))
            R.ex(cur, 'SELECT COUNT(*) FROM dbo.FederationInbox WHERE outcome=%s', ('applied',)); rev = cur.fetchall()[0][0] + 1
        ack = ack_dict(str(uuid.uuid4()), s, e, out, recv, applied if out == 'applied' else None, iso(t), iso(t) if out == 'applied' else None, rev)
        R.ex(cur, 'INSERT INTO dbo.FederationInbox(country, senderId, exportId, envelopeHash, schemaVersion, receivedSourceVersions, receivedAt, ackId, outcome, ackBody) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (ctry, sid, xid, e['envelopeHash'], e['schemaVersion'], json.dumps(recv), t, ack['ackId'], out, json.dumps(ack)))
        A(cur, 'S09:' + sid, 'FEDERATION_RECEIVED', xid, 'apiId=API12 kind=' + e['kind'] + ' outcome=' + out, cid)
        return 200, ack
    c, d = R.tx(f)
    if c == 409: raise ApiError(409, 'KEY_CONFLICT', '같은 키에 다른 envelopeHash가 이미 있습니다.')
    if c == 422: raise ApiError(422, d, '정정·철회 대상을 자기 키공간에서 확인할 수 없습니다.')
    return 200, d
def ack_get(xid, h, cid):
    """GET /v1/federated-snapshots/{exportId}/ack — 같은 송신자 범위의 저장 ack만(payload 없음). 다른 범위·없음은 일관된 404."""
    s = authed(h, ('/v1/federated-snapshots/' + xid + '/ack').encode(), cid, 'FEDERATION_ACK_READ_ATTEMPT', xid[:60])
    r = R.tx(lambda cur: (R.ex(cur, 'SELECT ackBody FROM dbo.FederationInbox WHERE country=%s AND senderId=%s AND exportId=%s', (s['country'], s['senderId'], xid)), cur.fetchall())[1])
    if not r: raise ApiError(404, 'NOT_FOUND', '해당 수신 기록이 없습니다(미수신 증거는 아님).')
    return 200, json.loads(r[0][0])
def portfolio(qs):
    rows = R.tx(lambda cur: (R.ex(cur, 'SELECT projectionKey, plantScope, metric, unit, valueDecimal, periodStart, periodEnd, validUntil FROM dbo.PortfolioProjection ORDER BY periodStart DESC'), cur.fetchall())[1])
    return dict(items=[dict(projectionKey=r[0], plantScope=r[1], metric=r[2], unit=r[3], value=r[4], periodStart=iso(r[5]), periodEnd=iso(r[6]), validUntil=iso(r[7])) for r in rows], state='no-federated-data' if not rows else 'ok',
                note='중앙이 수신한 허용 집계가 없습니다(국가 반출 닫힘). 미수신은 0이 아니며 값을 만들어 채우지 않습니다.' if not rows else None)
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/federated-snapshots': return receive(body, h, cid)
    if m == 'GET' and len(P) == 5 and P[2] == 'federated-snapshots' and P[4] == 'ack': return ack_get(P[3], h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'disclosures': raise ApiError(503, 'DISCLOSURE_PATH_CLOSED', '고객 공개 조회 경로는 닫혀 있습니다(고객 IdP·권한 출처·현재 상태 증명 미결). 수치를 반환하지 않습니다.', True)
    if m == 'GET' and p == '/v1/portfolio': return 200, portfolio(qs)
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.FederationInbox), (SELECT COUNT(*) FROM dbo.PortfolioProjection), (SELECT COUNT(*) FROM dbo.CentralReadAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, inbox=s[0], projections=s[1], audits=s[2], errors=R.err, last_err=R.last_err), mode=('수신 열림(등록 송신자 %d)' % len(SENDERS)) if SENDERS else '수신 닫힘(등록된 송신자 없음)', **STATS)
def main():
    global R
    R = sql_repo(); load_senders(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
