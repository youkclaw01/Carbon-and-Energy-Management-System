"""S05 견적·출하 탄소정보 핵심(순수 로직) — 체크리스트 2-5-1. 설계: design/services/S05 §3~6.
S05는 수치를 계산하지 않는다. 수치는 S02 발행본(release issued·usable)에서만 오며, 현재는 발행본이 없어(S02 certified 차단) 요청은 waiting_source로 남고 수치·공개본은 만들지 않는다.
상태 매핑(§6): candidate/ready·Release 없음 → provisional/result=null, issued+usable+실출하 일치 → certified(그 위에 §5.2 공개 조건 별도), correction_pending 409, superseded/revoked 410, 알 수 없음 503."""
from decimal import Decimal, InvalidOperation
class Reject(Exception):
    def __init__(self, status, code, msg='', fields=None): self.status, self.code, self.msg, self.fields = status, code, msg, fields or []
def dec_pos(v, name):
    if not isinstance(v, str): raise Reject(400, 'VALIDATION', name + '는 decimal 문자열이어야 합니다.', [name])
    try: d = Decimal(v)
    except InvalidOperation: raise Reject(400, 'VALIDATION', name + ' 형식 오류', [name])
    if d <= 0: raise Reject(400, 'VALIDATION', name + '는 양수여야 합니다.', [name])
    return v
def validate_request(b):
    """API05 접수 검증: kind별 id는 정확히 하나, 출하는 ERP sourceVersion, 견적은 assumptionRef 필수. 클라이언트 제출 배출량은 채택하지 않는다."""
    if any(k in b for k in ('emissions', 'value', 'footprintValue', 'co2e')): raise Reject(422, 'CLIENT_VALUE_REJECTED', '클라이언트가 제출한 배출량 수치는 채택하지 않습니다. 수치는 S02 발행본에서만 옵니다.')
    kind = b.get('kind')
    if kind not in ('quote', 'shipment'): raise Reject(400, 'VALIDATION', 'kind는 quote 또는 shipment입니다.', ['kind'])
    q, s = b.get('quoteId'), b.get('shipmentId')
    if (kind == 'quote') != bool(q) or (kind == 'shipment') != bool(s) or (q and s): raise Reject(400, 'VALIDATION', 'kind에 맞는 quoteId 또는 shipmentId 하나만 필요합니다.', ['quoteId', 'shipmentId'])
    if kind == 'shipment' and not b.get('sourceVersion'): raise Reject(400, 'VALIDATION', '출하 요청은 ERP sourceVersion이 필요합니다.', ['sourceVersion'])
    if kind == 'quote' and not b.get('assumptionRef'): raise Reject(400, 'VALIDATION', '견적 요청은 assumptionRef(가정 버전)가 필요합니다.', ['assumptionRef'])
    for k in ('productId', 'recipientScope', 'purpose', 'schemaVersion'):
        if not b.get(k): raise Reject(400, 'VALIDATION', k + ' 필요', [k])
    if not isinstance(b.get('batchRefs'), list) or not b['batchRefs']: raise Reject(400, 'VALIDATION', 'batchRefs(비어 있지 않은 목록) 필요', ['batchRefs'])
    qty = b.get('quantity') or {}; dec_pos(qty.get('value'), 'quantity.value')
    if not qty.get('unit'): raise Reject(400, 'VALIDATION', 'quantity.unit 필요', ['quantity.unit'])
    du = b.get('declaredUnit') or {}; dec_pos(du.get('quantity'), 'declaredUnit.quantity')
    if not du.get('unit'): raise Reject(400, 'VALIDATION', 'declaredUnit.unit 필요', ['declaredUnit.unit'])
    bd = b.get('boundary') or {}
    if not bd.get('type') or not isinstance(bd.get('includedStages'), list) or not bd['includedStages']: raise Reject(400, 'VALIDATION', 'boundary{type,includedStages[,excludedStages]} 필요', ['boundary'])
    per = b.get('period') or {}
    if not per.get('start') or not per.get('end') or per['start'] >= per['end']: raise Reject(400, 'VALIDATION', 'period.start < period.end(시작 포함·종료 제외) 필요', ['period'])
    if qty['unit'] != du['unit'] and not b.get('unitConversionRef'): raise Reject(422, 'UNIT_MISMATCH', '수량 단위와 선언 단위가 다르면 단위 변환 근거가 필요합니다(묵시 환산 없음).', ['quantity.unit', 'declaredUnit.unit'])
    return kind
def classify_source(release):
    """S02 API03 응답 → (요청 상태, 사유, 공개 수치 가능 여부). release=None은 확인 실패(불명)."""
    if release is None: return 'waiting_source', 'SOURCE_STATE_UNKNOWN', False, 503
    st = release.get('status')
    if st == 'issued' and release.get('usable') is True: return 'ready', None, True, 200
    if st == 'correction_pending': return 'waiting_source', 'SOURCE_CORRECTION_PENDING', False, 409
    if st in ('superseded', 'revoked'): return 'waiting_source', 'SOURCE_' + st.upper(), False, 410
    return 'waiting_source', 'SOURCE_NOT_USABLE', False, 409
def footprint_status(has_release, kind, issued_usable):
    """provisional/estimated/certified 표현. 후보만 있으면 provisional(수치 없음), 견적 가정 기반 issued는 estimated."""
    if not has_release: return 'none'
    return ('estimated' if kind == 'quote' else 'certified') if issued_usable else 'none'
