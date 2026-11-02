"""종합 보고서 서버 작성 서비스: 포털이 올린 분석 보고서(gen.pptx)를 사용자 템플릿에 넣고, 서술 문장은 AI가 작성한다.
AI 호출이 불가능하면(권한·네트워크) 규칙 기반 초안 문장으로 같은 템플릿을 채우고 그 사실을 meta에 기록한다."""
import os, sys, json, threading, time, uuid, tempfile, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report'))
JOBS = {}; LOCK = threading.Lock(); GATE = threading.Semaphore(1)
MAX_BYTES = 12 * 1024 * 1024

def _run(jid, data):
    job = JOBS[jid]
    with GATE:
        try:
            import fill_report, ai_slots
            from pptx import Presentation
            d = tempfile.mkdtemp(prefix='rp-', dir='/tmp'); gen = os.path.join(d, 'gen.pptx'); out = os.path.join(d, 'out.pptx')
            open(gen, 'wb').write(data)
            job['status'] = 'writing'; job['step'] = '분석 데이터에서 서술 칸을 추리는 중'
            draft = fill_report.slots_of(Presentation(gen))
            meta = {'slots': len(draft), 'ai': False}
            ai = None
            if os.environ.get('REPORT_AI', '1') == '1':
                try:
                    job['step'] = 'AI가 근거 자료 안에서 문장을 작성하는 중'
                    ai, rc = ai_slots.write_slots(draft, ai_slots.facts_text(gen))
                    meta.update({'ai': True, 'model': rc['model'], 'rounds': len(rc['rounds']), 'fallback_slots': len(rc['fallback_to_draft']), 'response_ids': [r['response_id'] for r in rc['rounds']], 'rules_sha256': rc['rounds'][0].get('rules_sha256')})
                except Exception as e:   # 비밀·토큰을 담지 않도록 요약만 기록
                    meta['ai_error'] = (type(e).__name__ + ': ' + str(e))[:300]
            job['step'] = '템플릿에 넣는 중'
            fill_report.fill(gen, out, ai)
            job['file'] = open(out, 'rb').read(); job['meta'] = meta; job['status'] = 'done'; job['step'] = '완료'
        except Exception as e:
            job['status'] = 'error'; job['error'] = (type(e).__name__ + ': ' + str(e))[:300]; traceback.print_exc()

UPLOADS = {}   # id -> {'t0':..., 'parts': {i: bytes}}
def _gc():
    now = time.time()
    for k in [k for k, v in JOBS.items() if now - v['t0'] > 1800]: JOBS.pop(k, None)
    for k in [k for k, v in UPLOADS.items() if now - v['t0'] > 900]: UPLOADS.pop(k, None)

def new_upload():
    with LOCK:
        _gc(); uid = uuid.uuid4().hex[:12]; UPLOADS[uid] = {'t0': time.time(), 'parts': {}}
    return uid

def put_chunk(uid, i, data):
    u = UPLOADS.get(uid)
    if not u or len(data) > 128 * 1024 or not (0 <= i < 200): return False
    u['parts'][i] = data; return True

def start_upload(uid, n):
    """조각 n개(0..n-1)를 이어 붙여 작업을 시작한다. 포털 앞단 WAF의 요청 본문 한도(128KB)에 맞춰 조각으로 받는다."""
    u = UPLOADS.pop(uid, None)
    if not u or set(u['parts']) != set(range(n)): return None, 'missing parts'
    data = b''.join(u['parts'][i] for i in range(n))
    if len(data) > MAX_BYTES or data[:2] != b'PK': return None, 'bad file'
    return start(data)

def start(data):
    if len(data) > MAX_BYTES: return None, 'too large'
    with LOCK:
        _gc(); jid = uuid.uuid4().hex[:12]; JOBS[jid] = {'status': 'queued', 'step': '대기 중', 't0': time.time()}
    threading.Thread(target=_run, args=(jid, data), daemon=True).start()
    return jid, None

def status(jid):
    j = JOBS.get(jid)
    if not j: return None
    return {k: v for k, v in j.items() if k not in ('file',)} | {'id': jid, 'sec': round(time.time() - j['t0'])}
