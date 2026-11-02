import sys, os, json, threading, sqlite3, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cqapi'))
import cq_app as CQ, cq_core as K
from svc_common import Repo, make_server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
def rej(fn, code):
    try: fn(); return False
    except K.Reject as e: return e.code == code
NOW = '2026-10-31T00:00:00Z'
def mk(xid='x1', kind='snapshot', **kw):
    e = dict(exportId=xid, country='KR', senderId='S09-KR', destination='S10-KRC', classification='INTERNAL', schemaVersion='fed-snapshot-v1', canonicalizationVersion='ama-json-c14n-v1', kind=kind,
        sourceRefs=[dict(authority='S02', objectId='r1', revision=1, digest='a' * 64), dict(authority='S05', objectId='d1', revision=1, digest='b' * 64)],
        authorityStates=[dict(authority='S02', objectId='r1', status='published', statusVersion=3, checkedAt='2026-10-30T00:00:00Z', validUntil='2027-01-01T00:00:00Z'), dict(authority='S05', objectId='d1', status='published', statusVersion=2, checkedAt='2026-10-30T00:00:00Z', validUntil='2027-01-01T00:00:00Z')],
        policyDecisionRef='p1', policyVersion='1', recipientScope='HQ', purpose='portfolio', fieldMask=['items.plantScope', 'items.metric', 'items.unit', 'items.valueDecimal', 'items.periodStart', 'items.periodEnd', 'items.boundaryRef'], issuedAt='2026-10-30T00:00:00Z', validUntil='2027-01-01T00:00:00Z',
        payload=dict(orgId='ORG1', items=[dict(plantScope='PLANT-1', metric='scope1', unit='tCO2e', valueDecimal='459.4', periodStart='2026-01-01T00:00:00Z', periodEnd='2026-12-31T00:00:00Z', boundaryRef='B1')]))
    if kind == 'withdrawal': e.update(payload={}, fieldMask=[], targetExportId='x1')
    if kind == 'correction': e.update(targetExportId='x1', replacesExportId='x1')
    e.update(kw); e['envelopeHash'] = K.envelope_hash({k: v for k, v in e.items() if k != 'envelopeHash'}); return e
def rehash(e): e = {k: v for k, v in e.items() if k != 'envelopeHash'}; e['envelopeHash'] = K.envelope_hash(e); return e
E0 = mk()
chk('envelope 검증 통과(r1 계약)', K.validate(E0, NOW))
chk('필수 필드 누락 400', rej(lambda: K.validate({k: v for k, v in E0.items() if k != 'purpose'}, NOW), 'BAD_REQUEST'))
chk('해시 변조 400', rej(lambda: K.validate(dict(E0, validUntil='2028-01-01T00:00:00Z'), NOW), 'HASH_MISMATCH'))
chk('미등록 상위 필드 422', rej(lambda: K.validate(rehash(dict(E0, extra='x')), NOW), 'SCHEMA_VIOLATION'))
chk('operation=status는 채택하지 않음(kind 미등록 422)', rej(lambda: K.validate(rehash(dict(E0, kind='status')), NOW), 'SCHEMA_VIOLATION'))
chk('미등록 schema·정규화 조합 422', rej(lambda: K.validate(rehash(dict(E0, schemaVersion='x')), NOW), 'SCHEMA_VIOLATION') and rej(lambda: K.validate(rehash(dict(E0, canonicalizationVersion='x')), NOW), 'SCHEMA_VIOLATION'))
chk('fieldMask 밖 payload 필드 422', rej(lambda: K.validate(rehash(dict(E0, fieldMask=['items.metric'])), NOW), 'FIELD_NOT_ALLOWED'))
it = dict(E0['payload']['items'][0], secret='x'); chk('허용 목록 밖 payload 필드 422', rej(lambda: K.validate(rehash(dict(E0, payload=dict(orgId='O', items=[it]))), NOW), 'FIELD_NOT_ALLOWED'))
chk('만료 422', rej(lambda: K.validate(rehash(dict(E0, validUntil='2026-10-01T00:00:00Z')), NOW), 'EXPIRED'))
chk('미등록 권위 상태 422(unknown 차단)', rej(lambda: K.validate(rehash(dict(E0, authorityStates=[dict(E0['authorityStates'][0], status='weird'), E0['authorityStates'][1]])), NOW), 'SCHEMA_VIOLATION'))
chk('공개 snapshot은 S02·S05 상태가 모두 필요(S05 없음 422)', rej(lambda: K.validate(rehash(dict(E0, authorityStates=[E0['authorityStates'][0]])), NOW), 'AUTHORITY_INCOMPLETE'))
chk('정정·철회는 대상 필수', rej(lambda: K.validate(rehash({k: v for k, v in mk(kind='withdrawal').items() if k != 'targetExportId'}), NOW), 'BAD_REQUEST'))
chk('구버전은 recorded_stale(부활 금지), 최신은 applied', K.outcome(E0, {('S02', 'r1'): 5}) == 'recorded_stale' and K.outcome(E0, {('S02', 'r1'): 3}) == 'applied')
ts0 = int(time.time()); VK = {}
def fv(ref, dg, sig):
    if ref == 'BOOM': raise RuntimeError('kv down')
    return sig == 'sig:' + ref + ':' + dg
def hd(sid, ref, ts, data, bad=False): return {'X-AMA-Sender-Id': sid, 'X-AMA-Timestamp': str(ts), 'X-AMA-Signature': 'bad' if bad else 'sig:' + ref + ':' + K.sender_digest(ts, data)}
SN = {'S': dict(keyRef='K1')}
chk('KV 서명 인증: 정상·데이터 변조·서명 변조·시각 초과·미등록·빈 등록부·비활성·keyRef 없음', all([
    K.auth_sender(hd('S', 'K1', ts0, b'd'), b'd', SN, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0, b'd'), b'x', SN, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0, b'd', bad=True), b'd', SN, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0 - 999, b'd'), b'd', SN, ts0, fv),
    not K.auth_sender(hd('Z', 'K1', ts0, b'd'), b'd', SN, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0, b'd'), b'd', {}, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0, b'd'), b'd', {'S': dict(keyRef='K1', status='disabled')}, ts0, fv),
    not K.auth_sender(hd('S', 'K1', ts0, b'd'), b'd', {'S': dict(status='active')}, ts0, fv)]))
chk('등록부의 keyRef만 사용(요청의 다른 키로 서명하면 거절)', not K.auth_sender(hd('S', 'K2', ts0, b'd'), b'd', SN, ts0, fv))
try: K.auth_sender(hd('S', 'BOOM', ts0, b'd'), b'd', {'S': dict(keyRef='BOOM')}, ts0, fv); r = False
except RuntimeError: r = True
chk('Key Vault 호출 실패는 예외 전파(401로 위장하지 않음)', r)
DDL = '''CREATE TABLE FederationInbox(country, senderId, exportId, envelopeHash, schemaVersion, receivedSourceVersions, receivedAt, ackId, outcome, ackBody, PRIMARY KEY(country, senderId, exportId));
CREATE TABLE AuthorityState(country, authority, objectId, revision, statusVersion, status, digest, verifiedAt, validUntil, tombstone, provenanceRef, PRIMARY KEY(country, authority, objectId));
CREATE TABLE PortfolioProjection(projectionKey PRIMARY KEY, orgId, country, plantScope, periodStart, periodEnd, boundaryRef, metric, unit, currency, valueDecimal, sourceRefs, sourceAsOf, lastVerifiedAt, validUntil, rowVersion);
CREATE TABLE CentralReadAudit(auditId INTEGER PRIMARY KEY AUTOINCREMENT, actor, action, target, beforeVersion, afterVersion, reason, correlationId, at, prevHash, hash);'''
def cf():
    c = sqlite3.connect(':memory:', check_same_thread=False); c.executescript(DDL); return c
CQ.R = Repo('sqlite', cf); srv = make_server(8850, CQ.route, CQ.health, CQ.STATS, '127.0.0.1'); threading.Thread(target=srv.serve_forever, daemon=True).start(); B = 'http://127.0.0.1:8850'
def call(m, p, body=None, h=None):
    rq = urllib.request.Request(B + p, data=json.dumps(body).encode() if body is not None else None, method=m, headers=dict({'Content-Type': 'application/json'}, **(h or {})))
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
KR = 'https://kv-cems-prd-krc-02.vault.azure.net/keys/fedsend-kr-01'; JP = 'https://kv-cems-prd-krc-02.vault.azure.net/keys/fedsend-jp-01'
def sh(body=None, path=None, sid='S09-KR', key=KR, t=None):
    t = t or int(time.time()); data = K.canon(body) if body is not None else path.encode()
    return hd(sid, key, t, data)
CQ.VERIFY = fv
# 1) 등록부 비어 있음 = 닫힘
c, d = call('POST', '/v1/federated-snapshots', E0, sh(E0)); chk('송신자 미등록(기본) → 401·수신 0건', c == 401 and d['code'] == 'UNAUTHENTICATED_SENDER', (c, d))
c, d = call('GET', '/v1/federated-snapshots/x1/ack', None, sh(path='/v1/federated-snapshots/x1/ack')); chk('미등록 ack 조회도 401', c == 401, d)
c, d = call('GET', '/health'); chk('health: 수신 닫힘', c == 200 and '닫힘' in d['mode'], d)
# 2) 송신자 등록(운영에서는 비밀 환경변수)
CQ.SENDERS = {'S09-KR': dict(keyRef=KR, country='KR', destination='S10-KRC', classifications=['INTERNAL'], status='active'), 'S09-JP': dict(keyRef=JP, country='JP', destination='S10-KRC', classifications=['INTERNAL'])}
c, d = call('POST', '/v1/federated-snapshots', E0, dict(sh(E0), **{'X-AMA-Signature': 'bad'})); chk('서명 불일치 401', c == 401, d)
c, d = call('POST', '/v1/federated-snapshots', E0, sh(E0, t=int(time.time()) - 900)); chk('시각 초과(리플레이) 401', c == 401, d)
CQ.SENDERS['S09-BX'] = dict(keyRef='BOOM', country='KR', destination='S10-KRC', classifications=['INTERNAL']); c, d = call('POST', '/v1/federated-snapshots', E0, sh(E0, sid='S09-BX', key='BOOM')); chk('Key Vault 검증 실패 → 503 SENDER_AUTH_UNAVAILABLE(재시도 가능·접수 없음)', c == 503 and d['code'] == 'SENDER_AUTH_UNAVAILABLE' and d['retryable'], (c, d)); CQ.SENDERS.pop('S09-BX')
import re; os.environ['FEDERATION_SENDERS'] = json.dumps({'a': dict(keyRef=KR, country='KR'), 'b': dict(keyRef='https://evil.example/keys/x', country='KR'), 'c': dict(keyRef=KR, country='KRX')}); keep = CQ.SENDERS; CQ.load_senders(); chk('등록부 적재: Key Vault 키 URL·2자 국가만 허용(그 외 항목 폐기)', list(CQ.SENDERS) == ['a'], CQ.SENDERS); CQ.SENDERS = keep; del os.environ['FEDERATION_SENDERS']
c, d = call('POST', '/v1/federated-snapshots', mk('x8', country='JP'), sh(mk('x8', country='JP'))); chk('본문 country가 인증 신원과 다르면 403(본문 불신)', c == 403 and d['code'] == 'FORBIDDEN_SCOPE', (c, d))
e = mk('x9', classification='PUBLIC'); c, d = call('POST', '/v1/federated-snapshots', e, sh(e)); chk('허용 분류 밖 403', c == 403, d)
e = mk('x9', destination='OTHER'); c, d = call('POST', '/v1/federated-snapshots', e, sh(e)); chk('목적지 불일치 403', c == 403, d)
e = rehash(dict(mk('x9'), kind='status')); c, d = call('POST', '/v1/federated-snapshots', e, sh(e)); chk('kind=status 422·저장 없음', c == 422, d)
e = mk('x9', authorityStates=[mk()['authorityStates'][0]]); c, d = call('POST', '/v1/federated-snapshots', e, sh(e)); chk('S05 없는 공개 snapshot 422 AUTHORITY_INCOMPLETE', c == 422 and d['code'] == 'AUTHORITY_INCOMPLETE', d)
n = CQ.R.tx(lambda cur: (CQ.R.ex(cur, 'SELECT COUNT(*) FROM dbo.FederationInbox'), cur.fetchall()[0])[1]); chk('거절된 요청은 inbox에 없음', n[0] == 0, n)
# 3) 정상 수신
c, d = call('POST', '/v1/federated-snapshots', E0, sh(E0)); A1 = d; chk('API12 정상: 동기 200 applied·ack 필수 필드·receiverPrincipal은 서버 값', c == 200 and d['outcome'] == 'applied' and d['appliedAt'] and d['projectionRevision'] == 1 and d['receiverPrincipal'] == 'S10-central-query-krc' and all(k in d for k in ('ackSchemaVersion', 'ackId', 'country', 'senderId', 'exportId', 'envelopeHash', 'destination', 'receivedSourceVersions', 'appliedSourceVersions', 'receivedAt')), (c, d))
c, d = call('POST', '/v1/federated-snapshots', E0, sh(E0)); chk('같은 키·hash 중복 → 최초 ack 그대로(재생성 없음)', c == 200 and d == A1, d)
e = mk('x1', policyVersion='2'); c, d = call('POST', '/v1/federated-snapshots', e, sh(e)); chk('같은 키 다른 hash → 409 KEY_CONFLICT', c == 409 and d['code'] == 'KEY_CONFLICT', d)
c, d = call('GET', '/v1/federated-snapshots/x1/ack', None, sh(path='/v1/federated-snapshots/x1/ack')); chk('ack 조회: 같은 범위 저장 ack 200(payload 없음)', c == 200 and d == A1 and 'payload' not in d, d)
c, d = call('GET', '/v1/federated-snapshots/x1/ack', None, sh(path='/v1/federated-snapshots/x1/ack', sid='S09-JP', key=JP)); chk('다른 송신자 범위에서는 일관된 404(존재 노출 없음)', c == 404, d)
c, d = call('GET', '/v1/portfolio'); chk('포트폴리오: 수신된 허용 집계 1건(값은 수신한 그대로)', c == 200 and len(d['items']) == 1 and d['items'][0]['value'] == '459.4' and d['state'] == 'ok', d)
# 4) 구버전 → recorded_stale
old = mk('x2', authorityStates=[dict(mk()['authorityStates'][0], statusVersion=1), mk()['authorityStates'][1]]); c, d = call('POST', '/v1/federated-snapshots', old, sh(old)); chk('구버전 → 200 recorded_stale(appliedAt·revision null)·projection 불변', c == 200 and d['outcome'] == 'recorded_stale' and d['appliedAt'] is None and d['projectionRevision'] is None, d)
c, d = call('GET', '/v1/portfolio'); chk('stale은 projection에 반영되지 않음', len(d['items']) == 1, d)
# 5) 정정·철회
cor = mk('x3', kind='correction', payload=dict(orgId='ORG1', items=[dict(mk()['payload']['items'][0], valueDecimal='400.0')]), authorityStates=[dict(mk()['authorityStates'][0], statusVersion=4), mk()['authorityStates'][1]])
c, d = call('POST', '/v1/federated-snapshots', cor, sh(cor)); chk('정정: 원대상 projection 교체(값 400.0)', c == 200 and d['outcome'] == 'applied', d)
c, d = call('GET', '/v1/portfolio'); chk('정정 후 한 건·값 400.0', len(d['items']) == 1 and d['items'][0]['value'] == '400.0', d)
unk = mk('x4', kind='correction', targetExportId='nope', replacesExportId='nope'); c, d = call('POST', '/v1/federated-snapshots', unk, sh(unk)); chk('정정 대상 미지 → 422 TARGET_UNKNOWN', c == 422 and d['code'] == 'TARGET_UNKNOWN', d)
wd = mk('x5', kind='withdrawal', targetExportId='x3', authorityStates=[dict(mk()['authorityStates'][0], status='withdrawn', statusVersion=5), mk()['authorityStates'][1]])
c, d = call('POST', '/v1/federated-snapshots', wd, sh(wd)); chk('철회: projection 제거·권위 상태 withdrawn(tombstone)', c == 200 and d['outcome'] == 'applied', d)
c, d = call('GET', '/v1/portfolio'); chk('철회 후 포트폴리오 비어 있음(0으로 채우지 않음)', d['items'] == [] and d['state'] == 'no-federated-data', d)
rv = mk('x6', authorityStates=[dict(mk()['authorityStates'][0], statusVersion=6), mk()['authorityStates'][1]]); c, d = call('POST', '/v1/federated-snapshots', rv, sh(rv)); chk('철회된 원천의 늦은 snapshot은 부활하지 않음(recorded_stale)', c == 200 and d['outcome'] == 'recorded_stale', d)
c, d = call('GET', '/v1/portfolio'); chk('부활 없음', d['items'] == [], d)
# 6) 감사·경계
rows = CQ.R.tx(lambda cur: (CQ.R.ex(cur, 'SELECT action, reason FROM dbo.CentralReadAudit ORDER BY auditId'), cur.fetchall())[1])
chk('수신·거절 시도 감사(체인)', any(r[0] == 'FEDERATION_RECEIVED' for r in rows) and any(r[0] == 'FEDERATION_RECEIVE_REJECTED' for r in rows) and any(r[1] == 'UNAUTHENTICATED_SENDER' for r in rows), rows[:3])
ph = CQ.R.tx(lambda cur: (CQ.R.ex(cur, 'SELECT prevHash FROM dbo.CentralReadAudit ORDER BY auditId'), cur.fetchall())[1]); chk('감사 체인 첫 행 prevHash null·이후 연결', ph[0][0] is None and all(p[0] for p in ph[1:]), ph[:2])
c, d = call('GET', '/v1/disclosures/abc'); chk('API13 고객 공개 조회: 503 DISCLOSURE_PATH_CLOSED(수치 없음)', c == 503 and d['code'] == 'DISCLOSURE_PATH_CLOSED', (c, d))
c, d = call('GET', '/health'); chk('health: 수신 열림(등록 송신자 2)·비밀 값 미노출', c == 200 and '열림' in d['mode'] and 'fedsend' not in json.dumps(d), d)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
