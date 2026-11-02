"""S12 장기 작업 핵심(순수) — 체크리스트 2-8-1. 설계: design/services/S12 §3~5.
상태: PENDING→READY→RUNNING→WAITING_SOURCE/WAITING_APPROVAL→…→SUCCEEDED/FAILED, 취소는 CANCEL_REQUESTED(접수)와 CANCELLED(실제 중단)를 구분. SUCCEEDED는 작업 완료이지 certified·승인·거래 성공이 아니다.
재개는 의존 권위 확인 뒤에만, unknown 재송신·종료 덮어쓰기 금지. 이 모듈에는 cron·dispatcher가 없다(자동 기동 금지)."""
TR = {'PENDING': {'READY', 'CANCEL_REQUESTED', 'FAILED'}, 'READY': {'RUNNING', 'CANCEL_REQUESTED', 'WAITING_SOURCE', 'WAITING_APPROVAL', 'FAILED'}, 'RUNNING': {'SUCCEEDED', 'FAILED', 'WAITING_SOURCE', 'WAITING_APPROVAL', 'CANCEL_REQUESTED'},
      'WAITING_SOURCE': {'READY', 'CANCEL_REQUESTED', 'FAILED'}, 'WAITING_APPROVAL': {'READY', 'CANCEL_REQUESTED', 'FAILED'}, 'CANCEL_REQUESTED': {'CANCELLED', 'FAILED'}}
TERMINAL = {'SUCCEEDED', 'FAILED', 'CANCELLED'}
OWNERS = {'S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09'}
WORKFLOWS = {'calc.run': ('S02', '1'), 'evidence.assemble': ('S06', '1'), 'ingest.followup': ('S01', '1')}      # 등록된 정의만(미등록은 422)
class Reject(Exception):
    def __init__(self, status, code, msg=''): self.status, self.code, self.msg = status, code, msg
def can(a, b): return b in TR.get(a, set())
def validate_create(b):
    for k in ('jobKey', 'workflowType', 'definitionVersion', 'ownerService', 'inputRef', 'inputDigest', 'deadlineAt', 'retryPolicyVersion'):
        if not b.get(k): raise Reject(400, 'BAD_REQUEST', k + ' 필요')
    wt = b['workflowType']
    if wt not in WORKFLOWS: raise Reject(422, 'UNSUPPORTED_WORKFLOW', '등록되지 않은 workflowType입니다(미합의 계약은 열지 않음).')
    if WORKFLOWS[wt][0] != b['ownerService'] or WORKFLOWS[wt][1] != b['definitionVersion']: raise Reject(422, 'UNSUPPORTED_WORKFLOW', 'ownerService·definitionVersion이 등록 정의와 다릅니다.')
    if len(b['inputDigest']) != 64: raise Reject(400, 'BAD_REQUEST', 'inputDigest는 sha256 hex 64자입니다.')
    if '://' in b['inputRef'] and '@' in b['inputRef']: raise Reject(422, 'FORBIDDEN_REF', '자격이 포함된 URL은 역참조하지 않습니다. 등록된 소유 API의 논리 식별자만 받습니다.')
    if wt == 'calc.run' and not (b.get('runKey') and len(b['runKey']) == 64): raise Reject(400, 'BAD_REQUEST', '산정 작업은 S02가 고정한 runKey가 필요합니다.')
def transition(job, to, expected_rev):
    if expected_rev != job['revision']: raise Reject(412, 'CAS_MISMATCH', '현재 revision과 다릅니다(%s).' % job['revision'])
    if job['state'] in TERMINAL: raise Reject(409, 'TERMINAL_STATE', '종료된 작업은 되돌리거나 덮어쓸 수 없습니다.')
    if not can(job['state'], to): raise Reject(409, 'BAD_STATE', '%s에서 %s로 전이할 수 없습니다.' % (job['state'], to))
    return dict(job, state=to, revision=job['revision'] + 1)
def resume_check(job, dependency_state):
    """재개: WAITING_*에서만, 의존 권위 상태가 'confirmed'일 때만. unknown/없음이면 보류(자동 재시도·재송신 없음)."""
    if job['state'] not in ('WAITING_SOURCE', 'WAITING_APPROVAL'): raise Reject(409, 'BAD_STATE', '대기 상태가 아닌 작업은 재개할 수 없습니다.')
    if dependency_state != 'confirmed': raise Reject(422, 'UNSAFE_RESUME', '의존 권위 확인 없이 재개하지 않습니다(승인·최신성 미확인은 보류).')
    return 'READY'
