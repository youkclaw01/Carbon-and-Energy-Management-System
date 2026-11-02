"""S07 승인·정책·한도 핵심(순수 로직) — 체크리스트 2-4-1. 설계: design/services/S07 §4(금액·한도 불변조건)·§5(API07)·§6(상태).
정책 allow·사람 승인·예약·permit·실행 성공은 서로 대체하지 않는다. D12(원문 전건 승인/한도 위임 관계)가 미결인 동안 평가는 항상 needs-approval/POLICY_UNRESOLVED/proposeOnly다."""
from decimal import Decimal, InvalidOperation
CANON = 'ama.intent.v1/jcs-1'; ALG = 'sha256'; EXP = {'KRW': 0, 'JPY': 0, 'USD': 2, 'SGD': 2, 'EUR': 2}
class Reject(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
def minor(value, currency):
    """decimal 문자열 → 통화별 최소단위 정수. 부동소수·미지원 통화·소수 자리 초과·음수는 거절(묵시 환산 금지)."""
    if currency not in EXP: raise Reject(400, 'BAD_CURRENCY', '지원하지 않는 통화입니다.')
    if not isinstance(value, str): raise Reject(400, 'BAD_AMOUNT', '금액은 decimal 문자열이어야 합니다.')
    try: d = Decimal(value)
    except InvalidOperation: raise Reject(400, 'BAD_AMOUNT', '금액 형식이 올바르지 않습니다.')
    if d < 0: raise Reject(400, 'BAD_AMOUNT', '금액은 0 이상이어야 합니다.')
    if d != d.quantize(Decimal(1).scaleb(-EXP[currency])): raise Reject(400, 'BAD_AMOUNT', '통화의 최소단위보다 작은 소수 자리가 있습니다.')
    return int(d.scaleb(EXP[currency]))
def evaluate(req):
    """API07. 부작용 없음. 필수 필드·규약 버전을 검사한 뒤 D12 미결이면 needs-approval(제안 전용)."""
    for k in ('action', 'resource', 'purpose', 'operationKey', 'intentDigest', 'canonicalizationVersion', 'digestAlgorithmId'):
        if not req.get(k): raise Reject(400, 'BAD_REQUEST', k + ' 필요')
    if req['canonicalizationVersion'] != CANON or req['digestAlgorithmId'] != ALG: raise Reject(422, 'CANONICALIZATION_UNSUPPORTED', '미지원·미합의 정규화/알고리즘 규약은 거절합니다(다른 digest를 동치 처리하지 않음).')
    if len(req['intentDigest']) != 64 or any(c not in '0123456789abcdef' for c in req['intentDigest']): raise Reject(400, 'BAD_DIGEST', 'intentDigest는 소문자 hex 64자입니다.')
    amt = req.get('amount'); am = cu = None
    if amt is not None:
        cu = amt.get('currency'); am = minor(amt.get('value'), cu)
    return dict(decision='needs-approval', reasonCode='POLICY_UNRESOLVED', proposeOnly=True, amountMinor=am, currency=cu, policyVersion='none-active')
# 신청 상태 기계
TR = {'pending': {'approved', 'rejected', 'cancelled', 'expired'}, 'approved': {'cancelled', 'expired'}}
def can(a, b): return b in TR.get(a, set())
def decide(state, requester, actor, decision, mfa_ok, digest_verified, expected_rev, rev):
    """승인 결정 규칙: 신청자≠승인자, MFA 증거 필수, 서버 재검증된 digest, expectedVersion CAS. 자동 재승인 없음."""
    if not mfa_ok: raise Reject(503, 'AUTH_CONTEXT_UNAVAILABLE', 'MFA 증거를 검증할 인증 문맥이 없습니다.')
    if requester == actor: raise Reject(403, 'SEPARATION_OF_DUTY', '신청자는 자기 신청을 승인할 수 없습니다.')
    if expected_rev != rev: raise Reject(409, 'VERSION_CONFLICT', '현재 버전과 다릅니다. 새 버전을 다시 확인하세요.')
    if decision == 'approve' and not digest_verified: raise Reject(503, 'BLOCKED_DEPENDENCY', '소유 서비스(S04/S05) API로 intent를 재검증하지 못해 승인할 수 없습니다.')
    to = {'approve': 'approved', 'reject': 'rejected', 'cancel': 'cancelled'}[decision]
    if not can(state, to): raise Reject(409, 'BAD_STATE', '%s에서 %s로 전이할 수 없습니다.' % (state, to))
    return to
# 한도 계정(정수 최소단위, cap ≥ held + settled). 부분 실패 없이 새 값을 반환한다.
def reserve(acc, amount):
    if amount < 0: raise Reject(400, 'BAD_AMOUNT')
    if acc['cap'] < acc['held'] + acc['settled'] + amount: raise Reject(409, 'LIMIT_EXCEEDED', '한도를 초과합니다.')
    return dict(acc, held=acc['held'] + amount, rev=acc['rev'] + 1)
def settle(acc, reserved, actual):
    """증거 있는 정산: held 감소·settled 증가. 실제 금액이 예약을 넘으면 거절(자동 보정 없음, 검토 필요)."""
    if actual < 0 or actual > reserved or acc['held'] < reserved: raise Reject(409, 'SETTLEMENT_MISMATCH', '정산 금액이 예약과 맞지 않아 review-required입니다.')
    return dict(acc, held=acc['held'] - reserved, settled=acc['settled'] + actual, rev=acc['rev'] + 1)
def release(acc, reserved, evidence_ok):
    """미전송 해제는 §7.5 증거가 모두 확인된 경우에만. 증거 부재·불명은 held 유지."""
    if not evidence_ok: raise Reject(409, 'RELEASE_EVIDENCE_INSUFFICIENT', '미전송 해제의 충분 증거가 없어 held를 유지합니다.')
    if acc['held'] < reserved: raise Reject(409, 'BAD_STATE')
    return dict(acc, held=acc['held'] - reserved, rev=acc['rev'] + 1)
