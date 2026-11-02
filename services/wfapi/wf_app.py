#!/usr/bin/env python3
"""workflow-api — S12-P1 POST /v1/jobs · P2 GET /v1/jobs/{id} · P3 cancel/resume (체크리스트 2-8-2~2-8-4). 설계: design/services/S12 §4~5.
v0.2(2026-10-31): **수동 엔진** `POST /v1/engine/tick`을 추가한다. 호출될 때만 한정된 수(limit, 기본 10·최대 50)의 작업을 처리하며 cron·dispatcher·백그라운드 스레드는 없다(자동 기동은 승인 전 금지).
처리: (1) CANCEL_REQUESTED → CANCELLED(실행 중인 단계가 없음을 엔진이 확인) (2) 마감 지난 비종료 작업 → FAILED(DEADLINE_EXCEEDED) (3) 임차(lease) 만료된 RUNNING → READY·epoch+1(재실행 아님, 다음 틱이 다시 판단) (4) 등록된 핸들러가 있는 작업만 실행: calc.run은 S02 calc-api의 실행 상태를 **읽기 전용으로 관찰**한다(ready→SUCCEEDED·dq_failed→FAILED·진행 중/없음→WAITING_SOURCE·확인 불가→변경 없음). evidence.assemble은 S06 evid-api(GET /v1/manifests/{id})를 읽기 전용으로 관찰한다(패키지 준비→SUCCEEDED·FAILED/BLOCKED→FAILED·진행 중/없음→WAITING_SOURCE). ingest.followup은 S01 ingest-api(GET /v1/ingestions/{id})를 읽기 전용으로 관찰한다(LANDED→SUCCEEDED·QUARANTINED/REJECTED→FAILED·수신 중/없음→WAITING_SOURCE). 핸들러가 없는 workflowType은 PENDING에 두고 가짜 진행률을 만들지 않는다.
SUCCEEDED는 작업 완료이지 certified·승인·거래 성공이 아니다.
resume은 의존 권위 확인 경로가 없어 항상 422 UNSAFE_RESUME. cancel은 CANCEL_REQUESTED(접수)까지이고 실제 중단(CANCELLED)은 엔진이 확인해야 한다. 사용자 인가는 S07 이후(X-Actor 미검증 라벨)."""
import os, sys, json, uuid, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svc_common import *
import wf_core as K
VERSION = 'workflow-api/0.4'; COUNTRY, ENV, ORG = 'KR', 'prod', 'AMA-KR'; STATS = {}; R = None; FETCH = http_get; CALC_URL = os.environ.get('CALC_API_URL', ''); EVID_URL = os.environ.get('EVID_API_URL', ''); INGEST_URL = os.environ.get('INGEST_API_URL', ''); LEASE_S = 120; ENGINE = 'engine-manual'
def A(cur, actor, action, target, before=None, after=None, reason='', cid=None):
    R.chain(cur, 'TransitionAudit', 'hash', 'auditId', dict(actor=(actor or 'internal-unverified')[:120], action=action, target=target, beforeVersion=before, afterVersion=after, reason=(reason or '')[:300], correlationId=cid))
JC = 'jobId, state, revision, waitingReason, workflowType, ownerService, jobKey, inputRef, runKey, deadlineAt, createdAt, updatedAt, leaseEpoch'
def view(r): return dict(jobId=r[0], state=r[1], revision=r[2], waitingReason=r[3], workflowType=r[4], ownerService=r[5], jobKey=r[6], inputRef=r[7], runKey=r[8], deadlineAt=iso(r[9]), createdAt=iso(r[10]), updatedAt=iso(r[11]), leaseEpoch=r[12], statusUrl='/v1/jobs/' + r[0], stage=None, attemptNo=0, nextWakeAt=None, checkpointRef=None, resultRefs=[], stale=False, note='수동 엔진이 처리하기 전입니다(POST /v1/engine/tick). 진행률을 만들지 않습니다.' if r[1] == 'PENDING' else None)
def create(body, h, cid):
    idem = h.get('Idempotency-Key')
    if not idem: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]
    try: K.validate_create(body)
    except K.Reject as e: raise ApiError(e.status, e.code, e.msg)
    plant = body.get('plantId')
    if plant not in (None, 'KR-01'): raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역 DB12는 KR-01 작업만 다룹니다.')
    try: ddl = dt.datetime.strptime(body['deadlineAt'].replace('Z', '').split('.')[0], '%Y-%m-%dT%H:%M:%S')
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'deadlineAt은 UTC ISO여야 합니다.')
    if ddl <= now(): raise ApiError(422, 'DEADLINE_PASSED', '마감 시각이 이미 지났습니다.')
    rd = sha(canon({k: v for k, v in body.items()})); jid = str(uuid.uuid4()); t = ts()
    def f(cur):
        R.ex(cur, 'SELECT ' + JC + ', requestDigest FROM dbo.Job WHERE country=%s AND orgId=%s AND principal=%s AND jobKey=%s', (COUNTRY, ORG, actor, body['jobKey'][:100])); x = cur.fetchall()
        if x:
            if x[0][13] != rd: raise ApiError(409, 'KEY_DIGEST_CONFLICT', '같은 jobKey에 다른 내용입니다.')
            return 200, view(x[0])
        if body['workflowType'] == 'calc.run':       # 같은 runKey 제출 Job은 호출 키가 달라도 하나(중복 제출 방지)
            R.ex(cur, 'SELECT ' + JC + ' FROM dbo.Job WHERE country=%s AND orgId=%s AND ownerService=%s AND runKey=%s', (COUNTRY, ORG, 'S02', body['runKey'])); y = cur.fetchall()
            if y: return 200, dict(view(y[0]), note='같은 runKey의 기존 작업입니다.')
        R.ex(cur, 'INSERT INTO dbo.Job(jobId, country, environment, orgId, plantId, principal, jobKey, requestDigest, ownerService, workflowType, definitionVersion, inputRef, inputDigest, runKey, state, revision, deadlineAt, retryPolicyVersion, createdAt, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',
            (jid, COUNTRY, ENV, ORG, plant, actor, body['jobKey'][:100], rd, body['ownerService'], body['workflowType'], body['definitionVersion'], body['inputRef'][:200], body['inputDigest'], body.get('runKey'), 'PENDING', ts(ddl), body['retryPolicyVersion'][:16], t, t))
        A(cur, actor, 'JOB_CREATE', jid, after='1', reason=body['workflowType'], cid=cid)
        R.ex(cur, 'SELECT ' + JC + ' FROM dbo.Job WHERE jobId=%s', (jid,)); return 202, view(cur.fetchall()[0])
    return R.tx(f)
def get_job(jid):
    try: uuid.UUID(jid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'jobId 형식이 올바르지 않습니다.')
    x = R.tx(lambda cur: (R.ex(cur, 'SELECT ' + JC + ' FROM dbo.Job WHERE jobId=%s', (jid,)), cur.fetchall())[1])
    if not x: raise ApiError(404, 'NOT_FOUND', '해당 작업이 없습니다.')
    return view(x[0])
def control(jid, action, body, h, cid):
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]; im = h.get('If-Match')
    if not im or not im.strip('"').isdigit(): raise ApiError(400, 'IF_MATCH_REQUIRED', 'If-Match(revision)가 필요합니다.')
    if not body.get('commandId') or not body.get('reason'): raise ApiError(400, 'BAD_REQUEST', 'commandId, reason 필요')
    exp = int(im.strip('"'))
    def f(cur):
        R.ex(cur, 'SELECT ' + JC + ' FROM dbo.Job WHERE jobId=%s', (jid,)); x = cur.fetchall()
        if not x: raise ApiError(404, 'NOT_FOUND', '해당 작업이 없습니다.')
        job = dict(state=x[0][1], revision=x[0][2])
        try:
            to = K.resume_check(job, None) if action == 'resume' else 'CANCEL_REQUESTED'
            nj = K.transition(job, to, exp)
        except K.Reject as e:
            A(cur, actor, 'JOB_' + action.upper() + '_DENIED', jid, before=str(job['revision']), reason=e.code, cid=cid); return ('denied', e)      # 거절도 감사에 남긴다(트랜잭션 커밋 후 오류 응답)
        R.ex(cur, 'UPDATE dbo.Job SET state=%s, revision=%s, updatedAt=%s WHERE jobId=%s AND revision=%s', (nj['state'], nj['revision'], ts(), jid, exp))
        if cur.rowcount != 1: raise ApiError(412, 'CAS_MISMATCH', '동시 변경이 있었습니다.')
        A(cur, actor, 'JOB_CANCEL_REQUEST', jid, before=str(exp), after=str(nj['revision']), reason=body['reason'], cid=cid); R.ex(cur, 'SELECT ' + JC + ' FROM dbo.Job WHERE jobId=%s', (jid,)); return view(cur.fetchall()[0])
    r = R.tx(f)
    if isinstance(r, tuple): raise ApiError(r[1].status, r[1].code, r[1].msg)
    return r

def _dtv(v):
    if v is None or isinstance(v, dt.datetime): return v
    return dt.datetime.strptime(str(v)[:19], '%Y-%m-%d %H:%M:%S') if ' ' in str(v)[:11] else dt.datetime.strptime(str(v)[:19], '%Y-%m-%dT%H:%M:%S')
def _job(cur, jid):
    R.ex(cur, 'SELECT ' + JC + ', leaseUntil, inputRef FROM dbo.Job WHERE jobId=%s', (jid,)); x = cur.fetchall(); return x[0] if x else None
def _set(cur, jid, rev, to, reason, cid, wait=None, lease=None):
    """CAS 전이 1회(+감사). lease=(owner, until) 이면 RUNNING 임차를 건다."""
    if lease: R.ex(cur, 'UPDATE dbo.Job SET state=%s, revision=revision+1, waitingReason=%s, leaseOwner=%s, leaseUntil=%s, leaseEpoch=leaseEpoch+1, updatedAt=%s WHERE jobId=%s AND revision=%s', (to, wait, lease[0], lease[1], ts(), jid, rev))
    else: R.ex(cur, 'UPDATE dbo.Job SET state=%s, revision=revision+1, waitingReason=%s, leaseOwner=NULL, leaseUntil=NULL, updatedAt=%s WHERE jobId=%s AND revision=%s', (to, wait, ts(), jid, rev))
    if cur.rowcount != 1: raise ApiError(412, 'CAS_MISMATCH', '동시 변경이 있었습니다.')
    A(cur, ENGINE, 'JOB_ENGINE_' + to, jid, before=str(rev), after=str(rev + 1), reason=reason, cid=cid); return rev + 1
def observe_calc(job):
    """S02 calc-api를 읽기 전용으로 관찰한다. inputRef는 'calc-run:<runId>' 논리 식별자. 반환: (outcome, detail)."""
    ref = job[-1] or ''
    if not ref.startswith('calc-run:') or not CALC_URL: return 'unknown', 'NO_CALC_REF'
    st, raw = FETCH(CALC_URL.rstrip('/') + '/v1/calc-runs/' + ref[9:])
    if st == 404: return 'missing', 'S02_RUN_NOT_FOUND'
    if st != 200: return 'unknown', 'S02_UNREACHABLE'
    try: d = json.loads(raw)
    except Exception: return 'unknown', 'S02_BAD_RESPONSE'
    if d.get('runKey') != job[8]: return 'mismatch', 'RUN_KEY_MISMATCH'
    b = d.get('businessState')
    if b == 'ready': return 'ready', str(d.get('candidateHash') or '')
    if b == 'dq_failed': return 'failed', 'DQ_FAILED'
    return 'waiting', 'S02_' + str(b).upper()
def observe_evid(job):
    """S06 evid-api를 읽기 전용으로 관찰한다. inputRef는 'manifest:<manifestId>' 논리 식별자. 패키지가 준비되면 완료(외부 인증·제출 아님)."""
    ref = job[-1] or ''
    if not ref.startswith('manifest:') or not EVID_URL: return 'unknown', 'NO_EVID_REF'
    st, raw = FETCH(EVID_URL.rstrip('/') + '/v1/manifests/' + ref[9:])
    if st == 404: return 'missing', 'S06_MANIFEST_NOT_FOUND'
    if st != 200: return 'unknown', 'S06_UNREACHABLE'
    try: d = json.loads(raw)
    except Exception: return 'unknown', 'S06_BAD_RESPONSE'
    g = d.get('generationState')
    if g in ('PACKAGE_READY', 'LOCAL_UNSIGNED_DRAFT_READY'): return 'ready', str((d.get('package') or {}).get('artifactHash') or d.get('manifestHash') or '')
    if g in ('FAILED', 'BLOCKED'): return 'failed', 'S06_' + g
    return 'waiting', 'S06_' + str(g).upper()
def observe_ingest(job):
    """S01 ingest-api를 읽기 전용으로 관찰한다(GET /v1/ingestions/{batchId}). inputRef는 'ingestion:<batchId>'. LANDED면 완료(원본 해시 기록)."""
    ref = job[-1] or ''
    if not ref.startswith('ingestion:') or not INGEST_URL: return 'unknown', 'NO_INGEST_REF'
    st, raw = FETCH(INGEST_URL.rstrip('/') + '/v1/ingestions/' + ref[10:])
    if st == 404: return 'missing', 'S01_BATCH_NOT_FOUND'
    if st != 200: return 'unknown', 'S01_UNREACHABLE'
    try: d = json.loads(raw)
    except Exception: return 'unknown', 'S01_BAD_RESPONSE'
    g = d.get('status')
    if g == 'LANDED': return 'ready', str(d.get('rawDigest') or '')
    if g in ('QUARANTINED', 'REJECTED'): return 'failed', 'S01_' + g
    return 'waiting', 'S01_' + str(g).upper()
OBSERVERS = {'calc.run': observe_calc, 'evidence.assemble': observe_evid, 'ingest.followup': observe_ingest}
_STEP = {'calc.run': ('observe-s02', 'S02'), 'evidence.assemble': ('observe-s06', 'S06'), 'ingest.followup': ('observe-s01', 'S01')}
def tick(body, h, cid):
    """수동 엔진 1회 처리. 요청이 있을 때만 동작하며 자동 반복·재시도 루프가 없다."""
    try: lim = max(1, min(50, int(body.get('limit', 10))))
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'limit은 정수입니다.')
    actor = (h.get('X-Actor') or 'internal-unverified')[:120]; out = []
    ids = R.tx(lambda cur: (R.ex(cur, R.top("SELECT jobId FROM dbo.Job WHERE state NOT IN ('SUCCEEDED','FAILED','CANCELLED') ORDER BY createdAt", lim)), [r[0] for r in cur.fetchall()])[1])
    for jid in ids:
        def f(cur):
            j = _job(cur, jid)
            if not j or j[1] in K.TERMINAL: return None
            st, rev, now_ = j[1], j[2], now(); note = []
            if st == 'CANCEL_REQUESTED': _set(cur, jid, rev, 'CANCELLED', 'cancel confirmed: no running step', cid); return dict(jobId=jid, action='CANCELLED')
            if j[9] is not None and _dtv(j[9]) <= now_: _set(cur, jid, rev, 'FAILED', 'DEADLINE_EXCEEDED', cid, 'DEADLINE_EXCEEDED'); return dict(jobId=jid, action='FAILED', reason='DEADLINE_EXCEEDED')
            if st == 'RUNNING':
                if j[13] is not None and _dtv(j[13]) <= now_: _set(cur, jid, rev, 'READY', 'lease expired (recovered; not re-run)', cid); return dict(jobId=jid, action='LEASE_RECOVERED')
                return dict(jobId=jid, action='SKIPPED', reason='RUNNING_LEASE_ACTIVE')
            if j[4] not in OBSERVERS: return dict(jobId=jid, action='SKIPPED', reason='NO_HANDLER')
            if st == 'PENDING': rev = _set(cur, jid, rev, 'READY', 'engine pick', cid)
            elif st in ('WAITING_SOURCE', 'WAITING_APPROVAL'):
                if st == 'WAITING_APPROVAL': return dict(jobId=jid, action='SKIPPED', reason='WAITING_APPROVAL_UNHANDLED')
                rev = _set(cur, jid, rev, 'READY', 'recheck', cid)
            rev = _set(cur, jid, rev, 'RUNNING', 'engine lease', cid, lease=(ENGINE, ts(now_ + dt.timedelta(seconds=LEASE_S))))
            return dict(jobId=jid, rev=rev, observe=True)
        r = R.tx(f)
        if r is None: continue
        if not r.get('observe'): out.append(r); continue
        # 관찰(DB 밖 호출) 후 결과 전이. 관찰이 불확실하면 READY로 되돌린다(성공·실패를 만들지 않음).
        def g(cur):
            job = _job(cur, jid); oc, detail = OBSERVERS[job[4]](job); rev = job[2]
            if oc == 'ready':
                R.ex(cur, 'SELECT COALESCE(MAX(attemptNo),0) FROM dbo.StepAttempt WHERE jobId=%s AND stepId=%s', (jid, _STEP[job[4]][0])); n = cur.fetchall()[0][0] + 1
                R.ex(cur, 'INSERT INTO dbo.StepAttempt(jobId, stepId, attemptNo, operationKey, targetService, taskType, targetRef, expectedTargetVersion, dispatchState, outcome, epoch, providerJobRef, observedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,NULL,%s)', (jid, _STEP[job[4]][0], n, jid + ':observe:' + str(n), _STEP[job[4]][1], 'observe_' + job[4].replace('.', '_'), job[-1][:200], 'observed', 'ready', job[12], ts()))
                R.ex(cur, 'SELECT COALESCE(MAX(checkpointNo),0) FROM dbo.[Checkpoint] WHERE jobId=%s', (jid,)); cn = cur.fetchall()[0][0] + 1
                R.ex(cur, 'INSERT INTO dbo.[Checkpoint](jobId, checkpointNo, definitionVersion, lastCommittedStep, sourceRefs, digest, revision, epoch) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)', (jid, cn, '1', _STEP[job[4]][0], json.dumps([job[-1]]), (detail if len(detail) == 64 else sha(detail)), rev, job[12]))
                _set(cur, jid, rev, 'SUCCEEDED', 'S02 candidate ready (작업 완료이며 certified·승인 아님)', cid); return dict(jobId=jid, action='SUCCEEDED', candidateHash=detail)
            if oc in ('failed', 'mismatch'): _set(cur, jid, rev, 'FAILED', detail, cid, detail); return dict(jobId=jid, action='FAILED', reason=detail)
            if oc in ('waiting', 'missing'): _set(cur, jid, rev, 'WAITING_SOURCE', detail, cid, detail); return dict(jobId=jid, action='WAITING_SOURCE', reason=detail)
            _set(cur, jid, rev, 'READY', 'observation unavailable (no progress made): ' + detail, cid); return dict(jobId=jid, action='UNCHANGED', reason=detail)
        out.append(R.tx(g))
    return 200, dict(processed=len(out), results=out, mode='manual-tick', note='수동 1회 처리입니다. 자동 반복은 없으며 SUCCEEDED는 certified·승인이 아닙니다.')
def route(m, p, qs, body, h, cid):
    P = p.split('/')
    if m == 'POST' and p == '/v1/engine/tick': return tick(body, h, cid)
    if m == 'POST' and p == '/v1/jobs': return create(body, h, cid)
    if m == 'GET' and len(P) == 4 and P[2] == 'jobs': return 200, get_job(P[3])
    if m == 'POST' and len(P) == 5 and P[2] == 'jobs' and P[4] in ('cancel', 'resume'): return 202 if P[4] == 'cancel' else 200, control(P[3], P[4], body, h, cid)
    if m == 'GET' and p == '/v1/jobs':
        rows = R.tx(lambda cur: (R.ex(cur, R.top('SELECT ' + JC + ' FROM dbo.Job ORDER BY createdAt DESC', 50)), cur.fetchall())[1]); return 200, dict(items=[view(r) for r in rows])
    return None
def health():
    s = R.tx(lambda cur: (R.ex(cur, 'SELECT (SELECT COUNT(*) FROM dbo.Job), (SELECT COUNT(*) FROM dbo.TransitionAudit)'), cur.fetchall()[0])[1])
    return dict(version=VERSION, db=dict(kind=R.kind, jobs=s[0], audits=s[1], errors=R.err, last_err=R.last_err), mode='수동 엔진(POST /v1/engine/tick 호출 시에만 처리·자동 기동 없음)', **STATS)
def main():
    global R
    R = sql_repo(); make_server(int(os.environ.get('PORT', '8080')), route, health, STATS).serve_forever()
if __name__ == '__main__': main()
