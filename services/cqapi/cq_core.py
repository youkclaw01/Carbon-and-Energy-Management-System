"""S10 중앙 조회 핵심(순수) — 체크리스트 2-7-1. 설계: design/services/S10 §4·5.
envelopeHash 재계산·필수 필드·fieldMask-payload 일치·유효시간 검사. 송신자(country,senderId)는 인증된 workload 매핑에서만 도출한다."""
import hashlib, json, datetime as dt
REQ = ('exportId', 'country', 'senderId', 'destination', 'classification', 'schemaVersion', 'canonicalizationVersion', 'envelopeHash', 'kind', 'sourceRefs', 'authorityStates', 'policyDecisionRef', 'policyVersion', 'recipientScope', 'purpose', 'fieldMask', 'issuedAt', 'validUntil', 'payload')
OPT = ('targetExportId', 'replacesExportId')
KINDS = {'snapshot', 'correction', 'withdrawal'}  # 독립 operation=status는 채택하지 않음(422). 설계 S10 §5.1
SCHEMAS = {'fed-snapshot-v1'}; CANON = {'ama-json-c14n-v1'}
STATUSES = ('issued', 'published', 'correction_pending', 'superseded', 'revoked', 'withdrawn')
ITEM = ('plantScope', 'metric', 'unit', 'valueDecimal', 'periodStart', 'periodEnd', 'boundaryRef')
class Reject(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def envelope_hash(e): return hashlib.sha256(canon({k: v for k, v in e.items() if k != 'envelopeHash'})).hexdigest()
def flat_keys(p, pre=''):
    out = set()
    for k, v in (p or {}).items():
        out.add(pre + k)
        if isinstance(v, dict): out |= flat_keys(v, pre + k + '.')
    return out
def validate(e, now_iso):
    """S10 §5.1 r1 계약. 미등록 상위 필드·schema·정규화·kind·권위 상태는 저장 전에 거절한다(임의 URL 역참조 없음)."""
    if not isinstance(e, dict): raise Reject(400, 'BAD_REQUEST', 'JSON 객체가 필요합니다.')
    for k in REQ:
        if k not in e: raise Reject(400, 'BAD_REQUEST', k + ' 필요')
    extra = set(e) - set(REQ) - set(OPT)
    if extra: raise Reject(422, 'SCHEMA_VIOLATION', '미등록 필드가 있습니다.')
    if e['kind'] not in KINDS: raise Reject(422, 'SCHEMA_VIOLATION', '미등록 kind(snapshot·correction·withdrawal만 허용)')
    if e['schemaVersion'] not in SCHEMAS or e['canonicalizationVersion'] not in CANON: raise Reject(422, 'SCHEMA_VIOLATION', '미등록 schema·정규화 조합')
    if not isinstance(e['sourceRefs'], list) or not e['sourceRefs'] or not isinstance(e['authorityStates'], list) or not e['authorityStates']: raise Reject(400, 'BAD_REQUEST', 'sourceRefs·authorityStates 필요')
    if not isinstance(e['fieldMask'], list) or not isinstance(e['payload'], dict): raise Reject(400, 'BAD_REQUEST', 'fieldMask는 배열·payload는 객체')
    if envelope_hash(e) != e['envelopeHash']: raise Reject(400, 'HASH_MISMATCH', 'envelopeHash가 불변 필드의 정규 JSON 해시와 다릅니다.')
    for r in e['sourceRefs']:
        if not isinstance(r, dict) or any(not r.get(k) and r.get(k) != 0 for k in ('authority', 'objectId', 'revision', 'digest')): raise Reject(422, 'SCHEMA_VIOLATION', 'sourceRefs는 authority,objectId,revision,digest가 필요합니다.')
    for a in e['authorityStates']:
        if not isinstance(a, dict) or any(k not in a for k in ('authority', 'objectId', 'status', 'statusVersion', 'checkedAt', 'validUntil')): raise Reject(422, 'SCHEMA_VIOLATION', 'authorityStates 필드가 부족합니다.')
        if a['status'] not in STATUSES or not isinstance(a['statusVersion'], int): raise Reject(422, 'SCHEMA_VIOLATION', '미등록 권위 상태는 unknown으로 차단합니다.')
    if e['kind'] in ('correction', 'withdrawal') and not e.get('targetExportId'): raise Reject(400, 'BAD_REQUEST', 'targetExportId 필요')
    if e['kind'] == 'correction' and not e.get('replacesExportId'): raise Reject(400, 'BAD_REQUEST', 'correction은 replacesExportId 필요')
    if e['kind'] == 'snapshot':
        have = {a['authority']: a['status'] for a in e['authorityStates']}
        if have.get('S02') not in ('issued', 'published') or have.get('S05') not in ('issued', 'published'): raise Reject(422, 'AUTHORITY_INCOMPLETE', '공개 snapshot에는 S02 release와 S05 disclosure의 유효 상태가 모두 필요합니다.')
    if e['kind'] != 'withdrawal':
        items = e['payload'].get('items')
        if set(e['payload']) - {'orgId', 'items'} or not e['payload'].get('orgId') or not isinstance(items, list): raise Reject(422, 'FIELD_NOT_ALLOWED', 'payload는 orgId·items만 허용합니다.')
        for it in items:
            if not isinstance(it, dict) or set(it) - set(ITEM) - {'currency'} or any(k not in it for k in ITEM): raise Reject(422, 'FIELD_NOT_ALLOWED', 'items 항목 필드가 허용 목록과 다릅니다.')
            if set('items.' + k for k in it) - set(e['fieldMask']): raise Reject(422, 'FIELD_NOT_ALLOWED', 'payload에 fieldMask 밖 필드가 있습니다.')
    elif e['payload'] != {} or e['fieldMask'] != []: raise Reject(422, 'SCHEMA_VIOLATION', 'withdrawal은 payload={}·fieldMask=[]이어야 합니다.')
    if e['validUntil'] <= now_iso: raise Reject(422, 'EXPIRED', '유효시간이 지났습니다.')
    return True
def sender_digest(ts, data): return hashlib.sha256(str(ts).encode() + b'.' + data).hexdigest()
def auth_sender(h, data, senders, now_epoch, verify, skew=300):
    """송신자 인증(Key Vault 비대칭 서명): X-AMA-Sender-Id + X-AMA-Timestamp + X-AMA-Signature = ES256(sha256(ts + '.' + data)).
    검증 키는 요청이 아니라 등록부의 keyRef(Key Vault 키)에서만 정해진다(키 바꿔치기 불가). data는 POST면 본문의 정규 JSON, GET이면 경로.
    verify(keyRef, digestHex, signature) → bool; Key Vault 호출 실패는 예외로 전파한다(호출자가 503 처리, 401로 위장하지 않음).
    등록부가 비어 있거나 비활성이면 항상 None(수신 닫힘). 공유 비밀을 쓰지 않는다."""
    s = senders.get(h.get('X-AMA-Sender-Id', '')) if senders else None
    if not s or s.get('status', 'active') != 'active' or not s.get('keyRef'): return None
    try: ts = int(h.get('X-AMA-Timestamp', ''))
    except ValueError: return None
    if abs(now_epoch - ts) > skew or not h.get('X-AMA-Signature'): return None
    return dict(s, senderId=h['X-AMA-Sender-Id']) if verify(s['keyRef'], sender_digest(ts, data), h['X-AMA-Signature']) else None
def outcome(e, known):
    """known: 같은 (country,authority,objectId)에서 이미 받은 statusVersion 최댓값. 구버전이면 recorded_stale(구버전 부활 금지)."""
    for a in e['authorityStates']:
        if known.get((a['authority'], a['objectId']), -1) > a['statusVersion']: return 'recorded_stale'
    return 'applied'
