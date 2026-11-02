"""relay 시험(메모리 저장소·싱크): 정상 전송 → 싱크 장애 시 PENDING 유지·재시도 → 복구 후 중복 없이 SENT."""
import sys, os, json, time, subprocess, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); PORT = 8831; FF = os.path.join(HERE, '.sinkfail'); res = []
env = dict(os.environ, RELAY_FAKE='1', FAKE_NO_BACKOFF='1', FAKE_SINK_FAIL_FILE=FF, PORT=str(PORT))
app = subprocess.Popen([sys.executable, os.path.join(ROOT, 'relay', 'relay_app.py')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.5)
g = lambda p: json.loads(urllib.request.urlopen(f'http://127.0.0.1:{PORT}{p}', timeout=5).read())
def chk(n, ok, info=''): res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n, info)
try:
    for _ in range(3): g('/v1/relay/fake/add')
    time.sleep(3.5); s = g('/v1/relay/stats'); k = g('/v1/relay/fake/sink'); chk('정상: 3건 전송·SENT 3', k['n'] == 3 and s['outbox'].get('SENT') == 3, (k['n'], s['outbox']))
    open(FF, 'w').close()
    for _ in range(2): g('/v1/relay/fake/add')
    time.sleep(4); s = g('/v1/relay/stats'); k = g('/v1/relay/fake/sink'); chk('싱크 장애: 새 2건은 전송 안 되고 PENDING/SENDING 유지, 재시도 기록', k['n'] == 3 and s['outbox'].get('SENT') == 3 and s['retried'] > 0 and s['outbox'].get('FAILED') is None, (k['n'], s['outbox'], s['retried']))
    os.remove(FF); time.sleep(5); s = g('/v1/relay/stats'); k = g('/v1/relay/fake/sink'); chk('복구: 총 5건 SENT, 싱크에 중복 eventId 없음', s['outbox'].get('SENT') == 5 and k['n'] == len(set(k['ids'])) == 5, (s['outbox'], k['n'], len(set(k['ids']))))
finally:
    app.terminate(); app.wait()
    try: os.remove(FF)
    except OSError: pass
print('RESULT', sum(res), '/', len(res)); sys.exit(0 if all(res) else 1)
