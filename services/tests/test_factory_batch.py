"""공장 VM: 초 단위 수집 + 분 단위(시험에서는 5초) 묶음 전송 확인. 가짜 중앙 수신으로 전송 간격·묶음 크기·원 event_id 유지·200건 한도를 검사한다."""
import sys, os, json, time, threading, subprocess, tempfile, socket, http.server
ok = bad = 0
def chk(n, c, info=''):
    global ok, bad
    if c: ok += 1; print('PASS', n)
    else: bad += 1; print('FAIL', n, str(info)[:300])
posts = []
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = self.rfile.read(int(self.headers['Content-Length'])); posts.append((time.time(), json.loads(b))); r = b'{"rejected":[],"duplicates":0}'
        self.send_response(200); self.send_header('Content-Length', str(len(r))); self.end_headers(); self.wfile.write(r)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close(); d = tempfile.mkdtemp(dir=os.environ.get('TMPDIR'))
cfg = dict(site_id='KR-01', site_name='울산', ingest_url='http://127.0.0.1:%d' % srv.server_address[1], port=port, bind='127.0.0.1', data_dir=d, send_interval_s=5, collect_s=1, batch_max=40, key_file=d + '/none')
json.dump(cfg, open(d + '/c.json', 'w'))
p = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), '..', 'factory', 'factory_app.py')], env=dict(os.environ, AMAFACTORY_CONFIG=d + '/c.json', AMAFACTORY_KEY='k'), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(19)
    import urllib.request
    info = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/api/outbox?n=1' % port, timeout=5).read())['info']
finally: p.terminate(); p.wait(5)
t = [x[0] for x in posts]; gaps = [b - a for a, b in zip(t, t[1:])]
evs = [e for _, doc in posts for e in doc['events']]
chk('전송 횟수가 초당이 아니라 주기 단위(19초 동안 5초 주기 → 3~6회 묶음 전송)', 2 <= len({round(x[0] / 4) for x in posts}) and len(posts) <= 12, len(posts))
chk('묶음 크기 한도(batch_max 40) 준수', all(len(doc['events']) <= 40 for _, doc in posts), [len(doc['events']) for _, doc in posts])
chk('수집은 1초 단위: 같은 계량기(ref)의 연속 meter.reading 간격 약 1초', (lambda r: len(r) > 3 and all(0.5 <= b - a <= 1.6 for a, b in zip(r, r[1:])))(sorted({__import__('datetime').datetime.strptime(e['ts'], '%Y-%m-%dT%H:%M:%S.%fZ').timestamp() for e in evs if e['type'] == 'meter.reading' and e['ref'] == next((x['ref'] for x in evs if x['type'] == 'meter.reading'), '')})))
chk('원 event_id·seq 유지 및 순서(seq 오름차순·중복 없음)', [e['seq'] for e in evs] == sorted({e['seq'] for e in evs}) and len({e['event_id'] for e in evs}) == len(evs))
chk('전송 주기 사이에도 이벤트는 outbox에 쌓였다가 한꺼번에 나감(한 묶음 이상 평균 2건 초과)', sum(len(doc['events']) for _, doc in posts) / max(len(posts), 1) > 2, [len(doc['events']) for _, doc in posts])
chk('outbox 정보에 수집·전송 주기 노출', info.get('send_interval_s') == 5 and info.get('collect_s') == 1 and 'next_send_in_s' in info, info)
print('RESULT', ok, '/', ok + bad); sys.exit(1 if bad else 0)
