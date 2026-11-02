#!/usr/bin/env python3
"""calc-api — S02 탄소 산정 API02/API03 + 발행 명령(체크리스트 2-2-3·2-2-4). 설계: design/services/S02 §5·6·7.
차이(문서화): S12(작업 엔진)가 아직 없어 후보 생성·검증을 이 앱의 내부 작업자가 대행한다. 사용자·워크로드 인가(calc.request 등)는 S07 권한 원장 구축 전이라 없다 → 내부 전용·호출자는 X-Actor 헤더(미검증 라벨)로만 기록.
발행: certified는 ACTUAL + 분리된 사람 승인(S07) + 권한 출처 확정이 모두 있어야 하며, 현재는 어느 것도 충족되지 않아 항상 차단하고 차단 사실을 ReleaseCommand·감사에 남긴다(수치 보충·우회 없음).
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, STORE_URL(Silver 읽기), INGEST_API_URL(S01 소유 API로 source mode 확인), PORT. 시험: CALC_FAKE=1."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, sys, json, time, uuid, hashlib, threading, datetime as dt, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core
VERSION = 'calc-api/0.1'; COUNTRY = 'KR'; ORG = 'AMA-KR'; MAX_DAYS = 7
GRANT_AUTHORITY_RESOLVED = False       # 설계 07 §7.1·S10 07: 권한 출처 미결. S07 구축·결정 후 true
STATS = dict(requests=0, errors=0, runs=0, started=time.time())

def now(): return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
def iso(v): return v.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (v.microsecond // 1000) if hasattr(v, 'strftime') else v
def parse_iso(s):
    try: return dt.datetime.strptime(s.replace('Z', '').split('.')[0], '%Y-%m-%dT%H:%M:%S')
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'periodStart/periodEnd는 UTC ISO(YYYY-MM-DDTHH:MM:SSZ)여야 합니다.')
def ms(d): return int(d.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
class ApiError(Exception):
    def __init__(self, status, code, msg='', retry=False): self.status, self.code, self.msg, self.retry = status, code, msg, retry

# ---------------- 저장소 ----------------
class Fake:
    def __init__(self): self.runs = {}; self.cands = {}; self.vals = {}; self.idem = {}; self.cmds = {}; self.audits = []; self.lock = threading.RLock(); self.releases = {}
    def audit(self, actor, action, target, result, reason='', before=None, after=None, trace=None):
        with self.lock:
            prev = self.audits[-1]['recordHash'] if self.audits else None; at = iso(now()); h = hashlib.sha256(('%s|%s|%s|%s|%s|%s|%s' % (prev, actor, action, target, result, reason, at)).encode()).hexdigest()
            self.audits.append(dict(actor=actor, action=action, target=target, result=result, reason=reason, at=at, previousHash=prev, recordHash=h))
    def create_run(self, run, idem):
        with self.lock:
            k = idem
            if k in self.idem: return ('idem', self.idem[k])
            for r in self.runs.values():
                if r['runKey'] == run['runKey']: return ('existing', r)
            self.runs[run['runId']] = dict(run); self.idem[k] = (run['requestDigest'], run['runId']); self.audit(run['calcRequestedBy'], 'CALC_RUN_ACCEPTED', run['runId'], 'OK'); return ('new', run)
    def by_key(self, key): return next((r for r in self.runs.values() if r['runKey'] == key), None)
    def set_state(self, rid, st, reason=''):
        with self.lock: self.runs[rid]['businessState'] = st; self.runs[rid]['updatedAt'] = iso(now()); self.audit('calc-worker', 'CALC_STATE', rid, st, reason)
    def save_candidate(self, rid, cand, h):
        with self.lock: self.cands[rid] = dict(cand, candidateHash=h)
    def save_validation(self, v):
        with self.lock: self.vals[v['runId']] = v
    def get_run(self, rid):
        with self.lock:
            r = self.runs.get(rid)
            return None if not r else dict(r, candidate=self.cands.get(rid), validation=self.vals.get(rid))
    def list_runs(self, plant, limit):
        with self.lock: return [dict(r) for r in sorted(self.runs.values(), key=lambda x: x['createdAt'], reverse=True) if not plant or r['plantId'] == plant][:limit]
    def idem_get(self, k):
        with self.lock: return self.idem.get(k)
    def add_command(self, c):
        with self.lock: self.cmds[c['commandId']] = c; self.audit(c['releaseRequestedBy'], 'RELEASE_COMMAND', c['commandId'], c['commandState'], c['denyReason'] or '')
    def get_command(self, cid): return self.cmds.get(cid)
    def get_release(self, rid): return self.releases.get(rid)
    def stats(self): return dict(kind='fake', runs=len(self.runs), audits=len(self.audits), commands=len(self.cmds))

class Sql:
    def __init__(self):
        import pytds, certifi
        self.pytds, self.cafile, self.conn, self.lock = pytds, certifi.where(), None, threading.RLock(); self.srv, self.db = os.environ['SQL_SERVER'], os.environ['SQL_DB']; self.err = 0; self.last_err = None
    def _tok(self):
        q = {'resource': 'https://database.windows.net/', 'api-version': '2019-08-01'}
        if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
        return json.loads(urllib.request.urlopen(urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=10).read())['access_token']
    def _c(self):
        if self.conn is None: self.conn = self.pytds.connect(self.srv, self.db, port=1433, access_token_callable=self._tok, cafile=self.cafile, autocommit=False, login_timeout=20, timeout=30)
        return self.conn
    def tx(self, fn):
        """트랜잭션 실행. 연결 오류는 재연결 후 한 번 더. 질의는 직렬화한다(pytds 연결은 스레드 안전하지 않음)."""
        with self.lock:
            for t in (0, 1):
                try:
                    c = self._c(); cur = c.cursor(); r = fn(cur); c.commit(); return r
                except ApiError: self._rb(); raise
                except Exception as e:
                    self.err += 1; self.last_err = (type(e).__name__ + ': ' + str(e))[:160]; self._rb()
                    try: self.conn.close()
                    except Exception: pass
                    self.conn = None
                    if t: raise ApiError(503, 'STORE_UNAVAILABLE', '저장소 오류로 처리하지 못했습니다. 같은 키로 다시 시도할 수 있습니다.', True)
                    time.sleep(0.3)
    def _rb(self):
        try: self.conn.rollback()
        except Exception: pass
    def _audit(self, cur, actor, action, target, result, reason='', trace=None):
        cur.execute('SELECT TOP 1 recordHash FROM dbo.CarbonAudit WITH (UPDLOCK, HOLDLOCK) ORDER BY auditId DESC'); r = cur.fetchall(); prev = r[0][0] if r else None; at = now(); atp = at.strftime('%Y-%m-%d %H:%M:%S.') + '%03d' % (at.microsecond // 1000)
        h = hashlib.sha256(('%s|%s|%s|%s|%s|%s|%s' % (prev, actor, action, target, result, reason, atp)).encode()).hexdigest()
        cur.execute('INSERT INTO dbo.CarbonAudit(actor, action, target, result, reason, traceId, at, previousHash, recordHash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)', (actor[:120], action, target, result, reason[:400], trace, atp, prev, h))
    def audit(self, actor, action, target, result, reason='', **kw): self.tx(lambda cur: self._audit(cur, actor, action, target, result, reason))
    RCOLS = 'runId, runKey, calculationKind, country, organizationId, plantId, periodStart, periodEnd, timezone, boundaryRef, mode, inputSnapshotRef, inputSnapshotDigest, versionSet, scenarioRef, requestDigest, businessState, calcRequestedBy, createdAt, updatedAt'
    RK = RCOLS.split(', ')
    def _run(self, r):
        d = dict(zip(self.RK, r)); d['runId'] = str(d['runId']); d['versionSet'] = json.loads(d['versionSet']);
        for k in ('periodStart', 'periodEnd', 'createdAt', 'updatedAt'): d[k] = iso(d[k])
        return d
    def create_run(self, run, idem):
        def f(cur):
            cur.execute('SELECT requestDigest, resultRef FROM dbo.IdempotencyEntry WITH (UPDLOCK) WHERE country=%s AND organizationId=%s AND principal=%s AND operation=%s AND idemKey=%s', idem[:5]); r = cur.fetchall()
            if r: return ('idem', (r[0][0], r[0][1]))
            cur.execute('SELECT ' + self.RCOLS + ' FROM dbo.CalcRun WHERE runKey=%s', (run['runKey'],)); r = cur.fetchall()
            if r: return ('existing', self._run(r[0]))
            ts = lambda s: s.replace('T', ' ').replace('Z', '')
            cur.execute('INSERT INTO dbo.CalcRun(runId, runKey, calculationKind, country, organizationId, plantId, periodStart, periodEnd, timezone, boundaryRef, mode, inputSnapshotRef, inputSnapshotDigest, versionSet, scenarioRef, requestDigest, businessState, calcRequestedBy, createdAt, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        (run['runId'], run['runKey'], run['calculationKind'], run['country'], run['organizationId'], run['plantId'], ts(run['periodStart']), ts(run['periodEnd']), run['timezone'], run['boundaryRef'], run['mode'], run['inputSnapshotRef'], run['inputSnapshotDigest'], json.dumps(run['versionSet']), run['scenarioRef'], run['requestDigest'], run['businessState'], run['calcRequestedBy'], ts(run['createdAt']), ts(run['updatedAt'])))
            cur.execute('INSERT INTO dbo.IdempotencyEntry(country, organizationId, principal, operation, idemKey, requestDigest, resultRef, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,SYSUTCDATETIME())', idem[:5] + (run['requestDigest'], run['runId']))
            self._audit(cur, run['calcRequestedBy'], 'CALC_RUN_ACCEPTED', run['runId'], 'OK'); return ('new', run)
        return self.tx(f)
    def idem_get(self, k): return None
    def by_key(self, key): return None
    def set_state(self, rid, st, reason=''):
        def f(cur): cur.execute('UPDATE dbo.CalcRun SET businessState=%s, updatedAt=SYSUTCDATETIME() WHERE runId=%s', (st, rid)); self._audit(cur, 'calc-worker', 'CALC_STATE', rid, st, reason)
        self.tx(f)
    def save_candidate(self, rid, cand, h):
        def f(cur): cur.execute('INSERT INTO dbo.CalcCandidate(runId, candidateHash, valuesJson, samples, expectedSamples, coverage, manifestRef, createdAt) VALUES (%s,%s,%s,%s,%s,%s,%s,SYSUTCDATETIME())', (rid, h, json.dumps(cand['values'], ensure_ascii=False), cand['samples'], cand['expectedSamples'], cand['coverage'], cand.get('manifestRef')))
        self.tx(f)
    def save_validation(self, v):
        def f(cur): cur.execute('INSERT INTO dbo.ValidationResult(validationId, runId, candidateHash, inputDigest, dqPolicyVersion, checkerCodeDigest, verdict, checksJson, checkedAt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,SYSUTCDATETIME())', (v['validationId'], v['runId'], v['candidateHash'], v['inputDigest'], v['dqPolicyVersion'], v['checkerCodeDigest'], v['verdict'], json.dumps(v['checks'], ensure_ascii=False)))
        self.tx(f)
    def get_run(self, rid):
        def f(cur):
            cur.execute('SELECT ' + self.RCOLS + ' FROM dbo.CalcRun WHERE runId=%s', (rid,)); r = cur.fetchall()
            if not r: return None
            d = self._run(r[0]); cur.execute('SELECT candidateHash, valuesJson, samples, expectedSamples, coverage FROM dbo.CalcCandidate WHERE runId=%s', (rid,)); c = cur.fetchall()
            d['candidate'] = dict(candidateHash=c[0][0], values=json.loads(c[0][1]), samples=c[0][2], expectedSamples=c[0][3], coverage=c[0][4]) if c else None
            cur.execute('SELECT TOP 1 validationId, verdict, checksJson, dqPolicyVersion, checkedAt FROM dbo.ValidationResult WHERE runId=%s ORDER BY checkedAt DESC', (rid,)); v = cur.fetchall()
            d['validation'] = dict(validationId=str(v[0][0]), verdict=v[0][1], checks=json.loads(v[0][2]), dqPolicyVersion=v[0][3], checkedAt=iso(v[0][4])) if v else None
            return d
        return self.tx(f)
    def list_runs(self, plant, limit):
        def f(cur):
            cur.execute('SELECT TOP (%d) ' % limit + self.RCOLS + ' FROM dbo.CalcRun' + (' WHERE plantId=%s' if plant else '') + ' ORDER BY createdAt DESC', (plant,) if plant else ()); return [self._run(r) for r in cur.fetchall()]
        return self.tx(f)
    def add_command(self, c):
        def f(cur):
            cur.execute('INSERT INTO dbo.ReleaseCommand(commandId, runId, validationId, commandDigest, releaseRequestedBy, decisionRef, approvedBy, commandState, denyReason, createdAt, updatedAt) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,SYSUTCDATETIME(),SYSUTCDATETIME())', (c['commandId'], c['runId'], c['validationId'], c['commandDigest'], c['releaseRequestedBy'][:120], c.get('decisionRef'), c['commandState'], c['denyReason']))
            self._audit(cur, c['releaseRequestedBy'], 'RELEASE_COMMAND', c['commandId'], c['commandState'], c['denyReason'] or '')
        self.tx(f)
    def get_command(self, cid):
        r = self.tx(lambda cur: (cur.execute('SELECT commandId, runId, commandState, denyReason, createdAt FROM dbo.ReleaseCommand WHERE commandId=%s', (cid,)), cur.fetchall())[1])
        return dict(commandId=str(r[0][0]), runId=str(r[0][1]), commandState=r[0][2], denyReason=r[0][3], createdAt=iso(r[0][4])) if r else None
    def get_release(self, rid):
        r = self.tx(lambda cur: (cur.execute('SELECT releaseId, runId, status, statusVersion, restrictionFlag, issuedAt FROM dbo.Release WHERE releaseId=%s', (rid,)), cur.fetchall())[1])
        return dict(releaseId=str(r[0][0]), runId=str(r[0][1]), status=r[0][2], statusVersion=r[0][3], restrictionFlag=bool(r[0][4]), issuedAt=iso(r[0][5])) if r else None
    def stats(self):
        r = self.tx(lambda cur: (cur.execute('SELECT (SELECT COUNT(*) FROM dbo.CalcRun), (SELECT COUNT(*) FROM dbo.CarbonAudit), (SELECT COUNT(*) FROM dbo.ReleaseCommand)'), cur.fetchall())[1]); return dict(kind='sql', runs=r[0][0], audits=r[0][1], commands=r[0][2], errors=self.err, last_err=self.last_err)
DB = None

# ---------------- 입력·모드 ----------------
def load_samples(plant, start, end):
    """S01 소유 Silver(energy_flow)에서 기간 표본을 읽어 event_id로 중복 제거한다. 반환: (표본, 스냅샷 참조)."""
    import refine
    days = []; d = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while d < end: days.append(d.strftime('%Y-%m-%d')); d += dt.timedelta(days=1)
    seen = {}; s_ms, e_ms = ms(start), ms(end)
    for day in days:
        for r in refine.read_silver('energy_flow', day):
            if r.get('site') == plant and s_ms <= r['ts'] < e_ms and r.get('event_id') not in seen: seen[r['event_id']] = r
    return [dict(ts_ms=r['ts'], grid_kw=r['grid'] or 0.0, gas_nm3h=r['gas_nm3h'] or 0.0) for r in sorted(seen.values(), key=lambda x: x['ts'])], 'silver/energy_flow/date=%s..%s' % (days[0], days[-1])
def source_modes(plant):
    """mode는 S01(접수 서비스)이 소유한다. 소유 API로 확인하고 확인 못 하면 산정하지 않는다(요청 mode를 믿지 않음)."""
    url = os.environ.get('INGEST_API_URL', '').rstrip('/')
    if not url: raise RuntimeError('INGEST_API_URL not set')
    with urllib.request.urlopen(url + '/v1/sources?plantId=' + urllib.parse.quote(plant), timeout=15) as r: d = json.loads(r.read())
    return [x['mode'] for x in d.get('items', []) if x.get('status') == 'ACTIVE']
LOADER = {'samples': load_samples, 'modes': source_modes}

# ---------------- 작업자(후보 → 독립 검증) ----------------
CHECKER_DIGEST = hashlib.sha256(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core.py'), 'rb').read()).hexdigest()
def work(run_id, plant, start, end):
    try:
        DB.set_state(run_id, 'awaiting_candidate')
        samples, ref = LOADER['samples'](plant, start, end); period = dict(startMs=ms(start), endMs=ms(end))
        cand = core.candidate(samples, period); h = core.sha(cand); DB.save_candidate(run_id, cand, h); DB.set_state(run_id, 'candidate_ready')
        DB.set_state(run_id, 'validating'); v = core.validate(cand, samples, period)
        DB.save_validation(dict(validationId=str(uuid.uuid4()), runId=run_id, candidateHash=h, inputDigest=core.sha([[s['ts_ms'], s['grid_kw'], s['gas_nm3h']] for s in samples]), dqPolicyVersion=v['dqPolicyVersion'], checkerCodeDigest=CHECKER_DIGEST, verdict=v['verdict'], checks=v['checks']))
        DB.set_state(run_id, core.business_state(v['verdict']), v['verdict'])
    except Exception as e:
        try: DB.set_state(run_id, 'dq_failed', ('WORKER_ERROR ' + type(e).__name__ + ': ' + str(e))[:300])
        except Exception: pass

# ---------------- 업무 ----------------
def create_run(body, actor, idem_key):
    if not idem_key: raise ApiError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'Idempotency-Key 헤더가 필요합니다.')
    plant = str(body.get('plantId') or ''); kind = body.get('calculationKind', 'INVENTORY')
    if plant not in ('KR-01',): raise ApiError(422, 'PLANT_NOT_IN_SCOPE', '이 지역(KR) DB02는 KR-01만 산정합니다. 다른 국가 공장은 해당 국가 서비스가 소유합니다.')
    if kind != 'INVENTORY': raise ApiError(422, 'KIND_UNSUPPORTED', 'WHAT_IF는 S03 입력 projection 합의 전까지 제공하지 않습니다(BLOCKED_DEPENDENCY).')
    start, end = parse_iso(str(body.get('periodStart', ''))), parse_iso(str(body.get('periodEnd', '')))
    if not start < end: raise ApiError(400, 'BAD_PERIOD', 'periodStart < periodEnd(시작 포함·종료 제외)여야 합니다.')
    if end - start > dt.timedelta(days=MAX_DAYS): raise ApiError(422, 'PERIOD_TOO_LONG', '한 번에 %d일까지 산정합니다.' % MAX_DAYS)
    if end > now() + dt.timedelta(seconds=1): raise ApiError(422, 'PERIOD_IN_FUTURE', '아직 지나지 않은 기간은 산정하지 않습니다.')
    for f in ('MOCK-EF-GRID-KR', 'MOCK-EF-GAS'): core.check_factor_period(f, start.strftime('%Y-%m-%d'))
    try: modes = LOADER['modes'](plant)
    except Exception as e: raise ApiError(503, 'SOURCE_MODE_UNAVAILABLE', 'S01 소스 mode를 확인하지 못해 산정하지 않습니다.', True)
    try: mode = core.mode_of(modes)
    except ValueError as e: raise ApiError(422, 'MODE_MIXED_OR_EMPTY', str(e))
    req_digest = core.sha(dict(plant=plant, kind=kind, start=iso(start), end=iso(end)))
    vs = core.version_set('pending', ['MOCK-EF-GRID-KR', 'MOCK-EF-GAS']); scope = '%s|%s|%s|%s' % (COUNTRY, plant, iso(start), iso(end))
    key = core.run_key(scope, kind, dict(vs, inputSnapshotDigest=None), None)      # 입력 snapshot은 작업 후 확정되므로 요청 범위+버전 집합으로 키를 고정한다
    rid = str(uuid.uuid4()); t = iso(now())
    run = dict(runId=rid, runKey=key, calculationKind=kind, country=COUNTRY, organizationId=ORG, plantId=plant, periodStart=iso(start), periodEnd=iso(end), timezone='Asia/Seoul', boundaryRef='SITE', mode=mode,
               inputSnapshotRef='silver/energy_flow', inputSnapshotDigest='0' * 64, versionSet=vs, scenarioRef=None, requestDigest=req_digest, businessState='accepted', calcRequestedBy=(actor or 'internal-unverified')[:120], createdAt=t, updatedAt=t)
    kind_r, val = DB.create_run(run, (COUNTRY, ORG, run['calcRequestedBy'], 'calc-run.create', idem_key[:100]))
    if kind_r == 'idem':
        if val[0] != req_digest: raise ApiError(409, 'IDEMPOTENCY_CONFLICT', '같은 Idempotency-Key에 다른 요청 내용입니다.')
        return 200, brief(DB.get_run(val[1]))
    if kind_r == 'existing': return 200, brief(DB.get_run(val['runId']), note='같은 범위·버전의 기존 run입니다.')
    STATS['runs'] += 1; threading.Thread(target=work, args=(rid, plant, start, end), daemon=True).start()
    return 202, dict(brief(run), statusUrl='/v1/calc-runs/' + rid)
def brief(r, note=None):
    c, v = r.get('candidate'), r.get('validation'); label = core.screen_label(r['mode'], kind=r['calculationKind'])
    st = r['businessState']
    if st in ('accepted', 'awaiting_candidate', 'validating'): label = '접수/처리·검증 중(확정 수치 없음)'
    elif st == 'dq_failed': label = '검증 실패(수치 사용 불가)'
    out = dict(runId=r['runId'], runKey=r['runKey'], businessState=st, calculationKind=r['calculationKind'], country=r['country'], plantId=r['plantId'], periodStart=r['periodStart'], periodEnd=r['periodEnd'], timezone=r['timezone'], boundaryRef=r['boundaryRef'], mode=r['mode'],
               versionSet=r['versionSet'], screenLabel=label, resultKind='SIMULATED' if r['mode'] == 'SIMULATED' else 'ACTUAL', publicationEligible=False, releaseId=None, createdAt=r['createdAt'], updatedAt=r['updatedAt'])
    if note: out['note'] = note
    if st == 'ready' and c and v: out['values'] = c['values']; out['candidateHash'] = c['candidateHash']
    if c: out['dq'] = dict(samples=c['samples'], expectedSamples=c['expectedSamples'], coverage=c['coverage'])
    if v: out['validation'] = dict(validationId=v['validationId'], verdict=v['verdict'], checks=v['checks'], checkedAt=v.get('checkedAt'))
    return out
def get_run(rid):
    try: uuid.UUID(rid)
    except Exception: raise ApiError(400, 'BAD_REQUEST', 'runId 형식이 올바르지 않습니다.')
    r = DB.get_run(rid)
    if not r: raise ApiError(404, 'NOT_FOUND', '해당 run이 없습니다.')
    return brief(r)
def release_command(body, actor):
    rid = str(body.get('runId') or ''); r = DB.get_run(rid) if rid else None
    if not r: raise ApiError(404, 'NOT_FOUND', '해당 run이 없습니다.')
    if r['calculationKind'] == 'WHAT_IF': raise ApiError(422, 'NON_PUBLISHABLE_RESULT', 'WHAT_IF 결과는 발행 대상이 아닙니다.')
    v = r.get('validation')
    if not v or v['verdict'] != 'PASS': raise ApiError(422, 'VALIDATION_NOT_PASSED', '독립 검증을 통과한 후보만 발행을 요청할 수 있습니다.')
    reasons = []
    if r['mode'] != 'ACTUAL': reasons.append('SIMULATED_INPUT')
    if not GRANT_AUTHORITY_RESOLVED: reasons.append('GRANT_AUTHORITY_UNRESOLVED')
    reasons.append('APPROVAL_S07_UNAVAILABLE')      # 분리된 사람 승인(S07) 근거가 없다
    if core.can_certify(r['mode'], False, GRANT_AUTHORITY_RESOLVED): raise ApiError(500, 'UNREACHABLE')
    cid = str(uuid.uuid4()); DB.add_command(dict(commandId=cid, runId=rid, validationId=v['validationId'], commandDigest=core.sha(dict(run=rid, cand=body.get('candidateHash'))), releaseRequestedBy=(actor or 'internal-unverified'), decisionRef=body.get('decisionRef'), commandState='blocked', denyReason=','.join(reasons)))
    raise ApiError(422, 'CERTIFIED_BLOCKED', 'certified 발행이 차단되었습니다: ' + ', '.join(reasons) + ' (commandId=%s)' % cid)

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def send(self, code, obj, cid=None):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.send_header('Cache-Control', 'no-store')
        if cid: self.send_header('X-Correlation-Id', cid)
        self.end_headers(); self.wfile.write(b)
    def handle_any(self, method):
        STATS['requests'] += 1; cid = self.headers.get('X-Correlation-Id') or str(uuid.uuid4()); u = urlparse(self.path); qs = parse_qs(u.query); p = u.path.rstrip('/')
        actor = self.headers.get('X-Actor'); body = {}
        try:
            if method == 'POST':
                n = int(self.headers.get('Content-Length') or 0)
                if n > 20000: raise ApiError(413, 'PAYLOAD_TOO_LARGE')
                try: body = json.loads(self.rfile.read(n) or b'{}')
                except Exception: raise ApiError(400, 'BAD_REQUEST', 'JSON 형식이 아닙니다.')
            if method == 'GET' and p == '/health': return self.send(200, dict(ok=True, version=VERSION, db=DB.stats(), checkerDigest=CHECKER_DIGEST[:12], **{k: v for k, v in STATS.items()}), cid)
            if method == 'POST' and p == '/v1/calc-runs': c, o = create_run(body, actor, self.headers.get('Idempotency-Key')); return self.send(c, o, cid)
            if method == 'GET' and p == '/v1/calc-runs': return self.send(200, dict(items=[brief(dict(r, candidate=None, validation=None)) for r in DB.list_runs((qs.get('plantId') or [None])[0], min(int((qs.get('limit') or ['20'])[0]), 100))]), cid)
            if method == 'GET' and p.startswith('/v1/calc-runs/'): return self.send(200, get_run(p.split('/')[-1]), cid)
            if method == 'POST' and p == '/v1/releases': release_command(body, actor)
            if method == 'GET' and p.startswith('/v1/release-commands/'):
                c = DB.get_command(p.split('/')[-1]); return self.send(200, c, cid) if c else self.send(404, dict(code='NOT_FOUND', retryable=False, correlationId=cid), cid)
            if method == 'GET' and p.startswith('/v1/releases/'):
                r = DB.get_release(p.split('/')[-1]); return self.send(200, r, cid) if r else self.send(404, dict(code='NOT_FOUND', message='발행본이 없습니다.', retryable=False, correlationId=cid), cid)
            raise ApiError(405 if p.startswith('/v1/') else 404, 'METHOD_NOT_ALLOWED' if p.startswith('/v1/') else 'NOT_FOUND')
        except ApiError as e:
            if e.status >= 500: STATS['errors'] += 1
            self.send(e.status, dict(code=e.code, message=e.msg, retryable=e.retry, correlationId=cid), cid)
        except Exception as e:
            STATS['errors'] += 1; self.send(500, dict(code='INTERNAL', retryable=False, correlationId=cid), cid)
    def do_GET(self): self.handle_any('GET')
    def do_POST(self): self.handle_any('POST')
class TS(ThreadingHTTPServer): daemon_threads = True; request_queue_size = 64
def main():
    global DB
    DB = Fake() if os.environ.get('CALC_FAKE') else Sql()
    TS(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
if __name__ == '__main__': main()
