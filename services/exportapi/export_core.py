"""S09 국가 반출 심사 핵심(순수) — 체크리스트 2-6-1. 설계: design/services/S09 §4·5.1·5.2.
envelopeHash는 불변 전송 필드 전체(자기 제외)의 정규 JSON SHA-256. 심사는 활성 정책·소유 API 재확인·법적/보안 근거가 모두 있어야 ALLOW이며 하나라도 없으면 BLOCK/UNKNOWN(허용 추정 없음)."""
import hashlib, json
OPS = {'snapshot', 'correction', 'withdrawal', 'status'}; OWNERS = {'S02', 'S03', 'S05', 'S06'}
class Reject(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
def canon(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
def sha(o): return hashlib.sha256(o if isinstance(o, bytes) else canon(o)).hexdigest()
def validate(b):
    for k in ('schemaRef', 'country', 'purpose', 'recipientScope', 'destination', 'operation', 'digest'):
        if not b.get(k): raise Reject(400, 'BAD_REQUEST', k + ' 필요')
    if b['operation'] not in OPS: raise Reject(400, 'BAD_REQUEST', 'operation은 snapshot/correction/withdrawal/status 중 하나입니다.')
    sp = b.get('sourceProjectionRef') or {}
    if sp.get('ownerService') not in OWNERS or not sp.get('projectionId') or not sp.get('projectionVersion') or not sp.get('contentHash'): raise Reject(400, 'BAD_REQUEST', 'sourceProjectionRef{ownerService(S02/S03/S05/S06), projectionId, projectionVersion, contentHash} 필요')
    if not isinstance(b.get('sourceRefs'), list) or not b['sourceRefs']: raise Reject(400, 'BAD_REQUEST', 'sourceRefs(비어 있지 않은 목록) 필요')
    op = b['operation']
    if op in ('correction', 'withdrawal', 'status') and not b.get('targetExportId'): raise Reject(400, 'BAD_REQUEST', op + '에는 targetExportId가 필요합니다.')
    if op == 'correction' and not b.get('replacesExportId'): raise Reject(400, 'BAD_REQUEST', 'correction에는 replacesExportId도 필요합니다.')
    if any(k in b for k in ('payload', 'url', 'sasUrl', 'sql')): raise Reject(422, 'FORBIDDEN_FIELD', '임의 payload·URL·SQL은 받지 않습니다. 소유 서비스의 등록된 API로만 projection을 해석합니다.')
def request_digest(b):
    """정규화 규약이 양측에 합의되지 않았으면 이 digest는 요청 멱등 판별용일 뿐 송신 허가 근거가 아니다."""
    return sha({k: b[k] for k in sorted(b) if k != 'digest'})
def review(b, active_policy, projection_state, legal_ok=False):
    """반환 (eligibility, reasonCode, http). projection_state: None=소유 API 확인 불가/미지원, dict=재확인 결과."""
    if projection_state is None: return 'UNKNOWN', 'BLOCKED_DEPENDENCY', 422
    if projection_state.get('status') not in ('issued', 'published'): return 'BLOCK', 'SOURCE_NOT_USABLE', 422
    if active_policy is None: return 'BLOCK', 'NO_ACTIVE_POLICY', 422
    if not legal_ok: return 'BLOCK', 'LEGAL_BASIS_UNCONFIRMED', 422
    return 'ALLOW', 'OK', 202
