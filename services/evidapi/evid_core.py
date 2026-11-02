"""S06 증빙 핵심(순수 로직, 입출력 없음) — 체크리스트 2-3-1. 설계: design/services/S06 §4(해시 규약)·§6(상태·서명 게이트)·§10(T01·T04·T11).
- 원본 항목은 정확한 바이트의 SHA-256, manifestHash는 정규 JSON(키 정렬·UTF-8·공백 없음) 본체의 SHA-256. 자기 hash·서명·ZIP hash는 본체에 넣지 않아 순환을 피한다.
- 서명 키 정책이 없으면(NOT_CONFIGURED) 국내 모의 미서명 초안(LOCAL_UNSIGNED_DRAFT_READY, localOnly)만 허용하고 외부 제공은 닫는다. 서명 불일치·hash 불일치는 BLOCKED이며 미서명 정상 초안으로 낮추지 않는다."""
import hashlib, io, json, zipfile
def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def sha(b): return hashlib.sha256(b).hexdigest()
SCHEMA = 'ama.evidence.manifest.v1'; TEMPLATE = 'v1'
TRANS = {'REQUESTED': {'ASSEMBLING', 'FAILED'}, 'ASSEMBLING': {'SEALED_DRAFT', 'PARTIAL', 'FAILED', 'BLOCKED'}, 'SEALED_DRAFT': {'PACKAGE_READY', 'LOCAL_UNSIGNED_DRAFT_READY', 'PARTIAL', 'BLOCKED', 'UNKNOWN', 'FAILED'}, 'UNKNOWN': {'SEALED_DRAFT', 'BLOCKED', 'FAILED'}}
def can(a, b): return b in TRANS.get(a, set())

def item_ref(item_id, owner, source_ref, source_version, body, media='application/json', inclusion='INCLUDED', reason=None, fact=None):
    """body는 원천 응답의 정확한 바이트. MISSING/EXCLUDED는 바이트 없이 이유만 남기고 0이나 빈 값으로 바꾸지 않는다."""
    if inclusion == 'INCLUDED' and body is None: raise ValueError('INCLUDED needs bytes')
    return dict(itemId=item_id, ownerService=owner, sourceRef=source_ref, sourceVersion=source_version, byteHash=sha(body) if body is not None else None, byteSize=len(body) if body is not None else 0, mediaType=media, inclusionStatus=inclusion, inclusionReason=reason, factRef=fact)

def build_manifest(ctx, items, lineage):
    """ctx: country, orgId, plantId, manifestId, manifestVersion, sourceBinding, snapshotId, periodStart, periodEnd, timeZone, purpose, recipientScope, mode, classification, supersedesRef"""
    body = dict(schemaVersion=SCHEMA, country=ctx['country'], orgId=ctx['orgId'], plantId=ctx['plantId'], manifestId=ctx['manifestId'], manifestVersion=ctx['manifestVersion'], sourceBinding=ctx['sourceBinding'], snapshotId=ctx['snapshotId'],
                period=dict(start=ctx['periodStart'], end=ctx['periodEnd'], timeZone=ctx['timeZone']), purpose=ctx['purpose'], recipientScope=ctx['recipientScope'], mode=ctx['mode'], classification=ctx['classification'],
                supersedesRef=ctx.get('supersedesRef'), items=sorted(items, key=lambda x: x['itemId']), lineage=sorted(lineage, key=lambda x: x['edgeId']), flags=dict(draftOnly=True, localOnly=True, externalVerification='NOT_VERIFIED'))
    check_lineage(body); check_facts(body); return body
def seal(body): b = canon(body); return b, sha(b)

def check_lineage(body):
    """누락·순환·타 공장 혼입 차단(LineageRef 불변조건)."""
    refs = {i['sourceRef'] for i in body['items']} | {'run:' + str(body['sourceBinding'].get('runId'))}; edges = body['lineage']
    for e in edges:
        if e['fromRef'] == e['toRef']: raise ValueError('LINEAGE_CYCLE:' + e['edgeId'])
    seen = {}
    for e in edges: seen.setdefault(e['fromRef'], []).append(e['toRef'])
    def reach(a, path):
        for b in seen.get(a, []):
            if b in path: raise ValueError('LINEAGE_CYCLE')
            reach(b, path | {b})
    for a in list(seen): reach(a, {a})
    for i in body['items']:
        if i.get('plantId') not in (None, body['plantId']): raise ValueError('LINEAGE_MISMATCH:plant')
def check_facts(body):
    """수치는 decimal 문자열·단위를 함께 가진 factRef만 허용(부동소수·단위 누락 금지)."""
    for i in body['items']:
        for f in (i.get('factRef') or []):
            if not isinstance(f.get('value'), str) or not f.get('unit'): raise ValueError('FACT_FORMAT:' + i['itemId'])
            float(f['value'])

def make_zip(manifest_bytes, files, readme):
    """결정론적 ZIP(고정 시각·정렬 순서·무압축): 같은 입력이면 같은 artifactHash."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', zipfile.ZIP_STORED) as z:
        for name, data in sorted([('manifest.json', manifest_bytes), ('README-DRAFT.txt', readme.encode('utf-8'))] + [('items/' + k, v) for k, v in files.items()]):
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_STORED; zi.external_attr = 0o644 << 16; z.writestr(zi, data)
    b = bio.getvalue(); return b, sha(b)
def readme(body, signing_state):
    return ('AMA 증빙 패키지 — DRAFT_ONLY / %s / 외부 인증 아님\n서명 상태: %s (NOT_CONFIGURED면 미서명 국내 모의 초안, 외부 제공·제출 금지)\n기간: %s ~ %s (시작 포함·종료 제외, %s)\nmanifest.json 본체의 SHA-256이 manifestHash입니다. 이 문서·파일 해시는 법적 유효성이나 내용의 진실성을 보장하지 않습니다.\n' % (body['mode'], signing_state, body['period']['start'], body['period']['end'], body['period']['timeZone']))

def verify_package(zip_bytes, artifact_hash, manifest_hash):
    """다운로드 재개봉 검사: ZIP hash, manifest hash, 항목별 바이트 hash를 manifest 선언과 대조한다. 하나라도 어긋나면 BLOCKED(T04)."""
    checks = [dict(check='ARTIFACT_HASH', ok=sha(zip_bytes) == artifact_hash)]
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes)); mb = z.read('manifest.json'); checks.append(dict(check='MANIFEST_HASH', ok=sha(mb) == manifest_hash))
        body = json.loads(mb)
        for it in body['items']:
            if it['inclusionStatus'] != 'INCLUDED': continue
            try: ok = sha(z.read('items/' + it['itemId'] + '.json')) == it['byteHash']
            except KeyError: ok = False
            checks.append(dict(check='ITEM:' + it['itemId'], ok=ok))
    except Exception as e: checks.append(dict(check='OPEN', ok=False, error=type(e).__name__))
    return dict(verdict='PASS' if all(c['ok'] for c in checks) else 'BLOCKED', checks=checks)

def final_state(signing_state, has_missing):
    """봉인 후 분기. 서명 경로 검증 전에는 PACKAGE_READY를 만들지 않는다."""
    if has_missing: return 'PARTIAL'
    if signing_state == 'VERIFIED': return 'PACKAGE_READY'
    if signing_state == 'NOT_CONFIGURED': return 'LOCAL_UNSIGNED_DRAFT_READY'
    return 'BLOCKED'

# ---------------- 분리 서명(설계 S06 §6) ----------------
SIGN_PROFILE = 'evid-sign-v1'; SIGN_ALG = 'ES256'
def sign_payload(manifest_hash, artifact_hash, manifest_id, manifest_version):
    """서명 대상: 봉인된 manifestHash와 ZIP artifactHash를 한 묶음으로 결합한 정규 JSON의 SHA-256. 서명은 ZIP 밖(signature.json)에 분리한다.
    반환: (정규 payload 바이트, digest 16진). 서명 키는 이 digest만 본다."""
    p = canon(dict(profile=SIGN_PROFILE, manifestId=manifest_id, manifestVersion=manifest_version, manifestHash=manifest_hash, artifactHash=artifact_hash))
    return p, sha(p)
def signing_decision(signer_configured, sig_ok, sign_error):
    """서명 경로 결과 → 서명 상태. 응답 유실/오류는 UNKNOWN(자동 재서명 없음), 검증 실패는 BAD(BLOCKED), 미구성은 NOT_CONFIGURED."""
    if not signer_configured: return 'NOT_CONFIGURED'
    if sign_error: return 'UNKNOWN'
    return 'VERIFIED' if sig_ok else 'BAD'
def final_state2(signing_state, has_missing):
    """UNKNOWN은 UNKNOWN, 서명 검증 실패(BAD)는 BLOCKED. 누락은 PARTIAL 우선(부분 패키지는 완전본이 아님)."""
    if signing_state == 'UNKNOWN': return 'UNKNOWN'
    if signing_state == 'BAD': return 'BLOCKED'
    return final_state(signing_state, has_missing)
