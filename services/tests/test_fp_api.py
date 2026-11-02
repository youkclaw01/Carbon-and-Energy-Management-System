import sys, os, json, threading, sqlite3, urllib.request, urllib.error, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fpapi'))
import fp_app as FP, fp_core as K
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
DDL = '''CREATE TABLE CustomerRequest(requestId TEXT PRIMARY KEY, country, orgId, plantId, principal, idemKey, requestDigest, kind, quoteId, shipmentId, productId, batchRefs, quantityValue, quantityUnit, declaredUnit, boundary, periodStart, periodEnd, recipientScope, purpose, schemaVersion, releaseRef, sourceVersion, assumptionRef, requestState, waitReason, footprintStatus, rev, correlationId, createdAt, updatedAt, UNIQUE(country,orgId,principal,idemKey));
CREATE TABLE FootprintAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
FP.R = Repo('sqlite', cf); mode = dict(st=404, body={}); os.environ['CALC_API_URL'] = 'http://calc'
FP.FETCH = lambda url: (mode['st'], json.dumps(mode['body']).encode())
srv = make_server(8848, FP.route, FP.health, FP.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8848'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
SH = dict(kind='shipment', shipmentId='SHP-1', sourceVersion='erp-7', productId='P-104', batchRefs=['B-1'], quantity=dict(value='25000', unit='kg'), declaredUnit=dict(quantity='1', unit='kg'), boundary=dict(type='cradle-to-gate', includedStages=['scope1', 'scope2'], excludedStages=['raw-material', 'transport']), period=dict(start='2026-10-01T00:00:00Z', end='2026-10-31T00:00:00Z'), recipientScope='CUSTOMER-A', purpose='disclosure', schemaVersion='1', plantId='KR-01')
QT = dict(SH, kind='quote', quoteId='Q-1', assumptionRef='assume-3'); del QT['shipmentId'], QT['sourceVersion']
def post(b, k, h=None): return call('POST', '/v1/footprint-requests', b, dict({'Idempotency-Key': k, 'X-Actor': 'internal-1'}, **(h or {})))
c, d = call('POST', '/v1/footprint-requests', SH); chk('Idempotency-Key 없으면 400', c == 400, d)
c, d = post(SH, 's1'); rid = d.get('requestId'); chk('출하 요청 202·releaseRef 없음 → waiting_source·result 없음·공개 불가', c == 202 and d['requestState'] == 'waiting_source' and d['waitReason'] == 'SOURCE_RELEASE_REQUIRED' and d['result'] is None and d['disclosable'] is False and d['footprintStatus'] == 'none', (c, d))
c, d2 = post(SH, 's1'); chk('같은 키·같은 내용 → 200 같은 요청', c == 200 and d2['requestId'] == rid, (c, d2))
c, d2 = post(dict(SH, productId='P-999'), 's1'); chk('같은 키·다른 내용 → 409', c == 409, d2)
c, d = post(dict(QT), 'q1'); chk('견적 요청(assumptionRef) 접수·waiting_source', c == 202 and d['kind'] == 'quote' and d['quoteId'] == 'Q-1', (c, d))
for n, b, code in [('kind 불일치(quote인데 shipmentId)', dict(QT, shipmentId='S'), 400), ('출하는 sourceVersion 필수', {k: v for k, v in SH.items() if k != 'sourceVersion'}, 400), ('견적은 assumptionRef 필수', {k: v for k, v in QT.items() if k != 'assumptionRef'}, 400), ('수량 0 거절(양수 decimal)', dict(SH, quantity=dict(value='0', unit='kg')), 400), ('수량 float 거절', dict(SH, quantity=dict(value=25000.5, unit='kg')), 400), ('기간 역전', dict(SH, period=dict(start='2026-10-31T00:00:00Z', end='2026-10-01T00:00:00Z')), 400), ('경계 없음', {k: v for k, v in SH.items() if k != 'boundary'}, 400), ('batchRefs 비어 있음', dict(SH, batchRefs=[]), 400)]:
    c, d = post(b, 'v-' + str(abs(hash(n)))); chk(n + ' → ' + str(code), c == code, (c, d))
c, d = post(dict(SH, quantity=dict(value='25', unit='t')), 'u1'); chk('단위 불일치(t vs kg)는 변환 근거 없으면 422', c == 422 and d['code'] == 'UNIT_MISMATCH', (c, d))
c, d = post(dict(SH, emissions='123.4'), 'c1'); chk('클라이언트 제출 배출량은 채택하지 않음 422', c == 422 and d['code'] == 'CLIENT_VALUE_REJECTED', (c, d))
c, d = post(dict(SH, plantId='JP-01'), 'p1'); chk('다른 국가 공장 422', c == 422 and d['code'] == 'PLANT_NOT_IN_SCOPE', (c, d))
mode.update(st=404); c, d = post(dict(SH, releaseRef=dict(releaseId='r-x', revision=1, hash='a' * 64)), 'r1'); chk('releaseRef 있으나 S02에 없음 → SOURCE_RELEASE_NOT_FOUND(수치·공개본 없음)', d['waitReason'] == 'SOURCE_RELEASE_NOT_FOUND' and d['result'] is None, d)
mode.update(st=503); c, d = post(dict(SH, releaseRef=dict(releaseId='r-y', revision=1, hash='a' * 64)), 'r2'); chk('S02 확인 실패 → SOURCE_STATE_UNKNOWN(최신성 미확인)', d['waitReason'] == 'SOURCE_STATE_UNKNOWN', d)
mode.update(st=200, body=dict(status='correction_pending', restrictionFlag=True)); c, d = post(dict(SH, releaseRef=dict(releaseId='r-z', revision=1, hash='a' * 64)), 'r3'); chk('S02 correction_pending → 자료 대기(차단)', d['requestState'] == 'waiting_source' and d['result'] is None, d)
mode.update(st=200, body=dict(status='issued', restrictionFlag=False)); c, d = post(dict(SH, releaseRef=dict(releaseId='r-w', revision=1, hash='a' * 64)), 'r4'); chk('S02 issued·usable → ready이지만 수치·공개는 만들지 않음(S02 manifest 계약 미합의)', d['requestState'] == 'ready' and d['result'] is None and d['disclosable'] is False, d)
c, d = call('GET', '/v1/footprint-requests/' + rid); chk('요청 조회', c == 200 and d['requestId'] == rid, d)
c, d = call('GET', '/v1/footprint-requests/not-uuid'); chk('형식 오류 400', c == 400, d)
c, d = call('GET', '/v1/footprint-requests/' + str(uuid.uuid4())); chk('없는 요청 404', c == 404, d)
c, d = call('GET', '/v1/shipments/SHP-1/footprint?purpose=disclosure'); chk('출하 탄소정보 조회: 수치 없이 409 FOOTPRINT_NOT_AVAILABLE(0/추정 없음)', c == 409 and d['code'] == 'FOOTPRINT_NOT_AVAILABLE' and 'value' not in json.dumps(d), (c, d))
c, d = call('GET', '/v1/shipments/NONE/footprint'); chk('요청 없는 출하 404', c == 404, d)
c, d = call('POST', '/v1/disclosure-releases', dict(requestId=rid), {'X-Actor': 'x'}); chk('공개본 생성 422 DISCLOSURE_BLOCKED(발행본·정책·IdP 미비)', c == 422 and d['code'] == 'DISCLOSURE_BLOCKED', (c, d))
c, d = call('POST', '/v1/disclosure-releases/' + str(uuid.uuid4()) + '/withdrawals', {}); chk('없는 공개본 철회 404', c == 404, d)
c, d = call('POST', '/v1/disclosure-releases/' + str(uuid.uuid4()) + '/status-proofs', {}, {'X-Actor': 'x'}); chk('상태 증명: 서명 키 미구성 → 503(유효 증명 미발급)', c == 503 and d['code'] == 'SIGNING_KEY_NOT_CONFIGURED' and d['retryable'], (c, d))
c, d = call('GET', '/v1/disclosure-releases/' + str(uuid.uuid4()) + '/export-projection'); chk('반출 projection: 공개본 없음 404', c == 404, d)
rows = FP.R.tx(lambda cur: (FP.R.ex(cur, 'SELECT prevHash, hash FROM dbo.FootprintAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 해시 체인 연속 %d행' % len(rows), all(rows[i][0] == (rows[i - 1][1] if i else None) for i in range(len(rows))) and len(rows) >= 8)
c, d = call('GET', '/health'); chk('health(모드 표시)', c == 200 and 'no-release' in d['mode'], d)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
