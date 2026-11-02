"""저장 후 ACK + DB01 메타데이터 시험(로컬): 저장소가 살아 있으면 저장 뒤 200, 저장소가 죽으면 503이며 메모리에 반영하지 않고, 복구 후 같은 event_id 재전송은 정확히 한 번만 저장된다.
usage: test_landing.py   (모의 Blob과 수신 앱을 자식 프로세스로 띄우고 스스로 종료한다)"""
import sys, os, json, time, hmac, hashlib, uuid, subprocess, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); NS = uuid.UUID('6f1c5d0a-3b7e-4e4e-9a52-0a11fac70001'); KEY = 'testkey-0123456789abcdef-testkey-0123456789abcdef'; SITE = 'KR-01'; BP, IP = 8821, 8822; res = []
def start_blob(): return subprocess.Popen([sys.executable, os.path.join(HERE, 'mock_blob.py'), str(BP)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
env = dict(os.environ, PORT=str(IP), STORE_URL=f'http://127.0.0.1:{BP}', IDENTITY_ENDPOINT=f'http://127.0.0.1:{BP}/msi', IDENTITY_HEADER='x', DB_FAKE='1', DB_FAKE_FAIL_FILE=os.path.join(HERE, '.dbfail'), FACTORY_KEYS=json.dumps({'tk1': {'key': KEY, 'site': SITE}}))
blob = start_blob(); time.sleep(1); app = subprocess.Popen([sys.executable, os.path.join(ROOT, 'ingest', 'ingest_app.py')], cwd=os.path.join(ROOT, 'ingest'), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(2)
def post(events, ep):
    body = json.dumps({'site_id': SITE, 'epoch': ep, 'events': events}).encode(); ts = str(int(time.time())); sig = hmac.new(KEY.encode(), ts.encode() + b'.' + body, hashlib.sha256).hexdigest()
    rq = urllib.request.Request(f'http://127.0.0.1:{IP}/v1/events', data=body, method='POST', headers={'Content-Type': 'application/json', 'X-AMA-Site': SITE, 'X-AMA-Key-Id': 'tk1', 'X-AMA-Timestamp': ts, 'X-AMA-Signature': sig})
    try:
        with urllib.request.urlopen(rq, timeout=30) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')
def ev(seq, ep): return dict(schema='ama.factory.v1', event_id=str(uuid.uuid5(NS, f'{SITE}|{ep}|{seq}')), site_id=SITE, epoch=ep, seq=seq, ts='2026-10-30T00:00:%02d.000Z' % (seq % 60), type='heartbeat', ref='LTEST', payload={'uptime_s': seq})
def get(p): return json.loads(urllib.request.urlopen(f'http://127.0.0.1:{IP}{p}', timeout=10).read())
def lines():
    try: raw = urllib.request.urlopen(f'http://127.0.0.1:{BP}/bronze/{SITE}/' + time.strftime('%Y-%m-%d', time.gmtime()) + '.ndjson', timeout=5).read().decode()
    except Exception: return None
    return [l for l in raw.split('\n') if l]
def chk(n, ok, info=''): res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n, info)
try:
    ep = 'L' + str(int(time.time()))
    c, d = post([ev(1, ep), ev(2, ep), ev(3, ep)], ep); L = lines(); chk('저장소 정상: 200이며 3줄이 저장된 뒤 ACK', c == 200 and d['accepted'] == 3 and L is not None and len(L) == 3, (c, d.get('accepted'), L and len(L)))
    blob.terminate(); blob.wait(); time.sleep(0.5)
    c, d = post([ev(4, ep), ev(5, ep)], ep); q = get(f'/v1/sites/{SITE}/quality'); chk('저장소 장애: 503(재시도 가능)이며 메모리에 반영하지 않음', c == 503 and d.get('retryable') is True and q['last_seq'] == 3 and q['received'] == 3, (c, d, q['last_seq'], q['received']))
    blob = start_blob(); time.sleep(1)
    c, d = post([ev(4, ep), ev(5, ep)], ep); L = lines(); chk('복구 후 같은 event_id 재전송은 200이며 저장', c == 200 and d['accepted'] == 2, (c, d.get('accepted')))
    c, d = post([ev(4, ep), ev(5, ep)], ep); L2 = lines(); chk('한 번 더 재전송은 중복이며 저장소 줄 수 불변', c == 200 and d['duplicates'] == 2 and d['accepted'] == 0 and L2 is not None, (d.get('duplicates'), L2 and len(L2)))
    q = get(f'/v1/sites/{SITE}/quality'); chk('결측 0, 수신 5건', q['missing'] == 0 and q['received'] == 5, (q['missing'], q['received']))
    ids = [json.loads(x)['event_id'] for x in (L2 or [])]; chk('저장소에는 새 모의 Blob 기준 복구 후 2줄만 있고 중복 event_id 없음', len(ids) == len(set(ids)), len(ids))
    open(os.path.join(HERE, '.dbfail'), 'w').close()
    ep2 = ep + 'd'; c, d = post([ev(1, ep2), ev(2, ep2)], ep2); q = get(f'/v1/sites/{SITE}/quality'); st = get('/v1/stats')
    chk('DB01 장애: 503(metadata store unavailable)이며 메모리 미반영', c == 503 and d.get('error') == 'metadata store unavailable' and q['epoch'] == ep and st['db_errors'] == 1, (c, d.get('error'), q['epoch'] == ep))
    os.remove(os.path.join(HERE, '.dbfail'))
    c, d = post([ev(1, ep2), ev(2, ep2)], ep2); st = get('/v1/stats'); chk('DB01 복구 후 재전송 200, 배치 메타데이터 정확히 기록', c == 200 and d['accepted'] == 2 and st['db']['batches'] >= 1, (c, d.get('accepted'), st['db']))
    n = st['db']['batches']; post([ev(1, ep2), ev(2, ep2)], ep2); st = get('/v1/stats'); chk('같은 재전송(중복)은 새 배치 행을 만들지 않음', st['db']['batches'] == n, (n, st['db']['batches']))
    # 격리: 허용되지 않은 종류·같은 ID 다른 내용은 응답에 거절 이유가 있고 DB01에 QUARANTINED로 기록된다(원문은 공장 outbox 보관)
    bad = ev(9, ep2); bad['type'] = 'evil.type'; conf = ev(1, ep2); conf['payload'] = {'uptime_s': 12345}
    c, d = post([bad, conf], ep2); st = get('/v1/stats'); chk('격리: 거절 이유 2건 응답 + DB01 QUARANTINED 1행(이유별 요약)', c == 200 and len(d['rejected']) == 2 and st['db']['quarantined'] == 1 and d['accepted'] == 0, (c, [x['reason'] for x in d['rejected']], st['db']))
    # 재시작 복원: 저장분을 끝 구간(HEAD+Range)으로 읽어 SEEN을 복원하면 재시작 뒤 재전송은 중복 처리되어 Bronze가 늘지 않는다
    n_before = len(lines() or []); app.terminate(); app.wait(); app = subprocess.Popen([sys.executable, os.path.join(ROOT, 'ingest', 'ingest_app.py')], cwd=os.path.join(ROOT, 'ingest'), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(2.5)
    st = get('/v1/stats'); chk('재시작 후 저장분 복원(restored>0, 복원 오류 없음)', st['store']['restored'] > 0 and not (st['store']['last_err'] or '').startswith('restore'), (st['store']['restored'], st['store']['last_err']))
    c, d = post([ev(1, ep2), ev(2, ep2)], ep2); chk('재시작 뒤 재전송은 중복(복원된 event_id)이며 Bronze 줄 수 불변', c == 200 and d['duplicates'] == 2 and d['accepted'] == 0 and len(lines() or []) == n_before, (d.get('duplicates'), n_before, len(lines() or [])))
finally:
    try: os.remove(os.path.join(HERE, '.dbfail'))
    except OSError: pass
    app.terminate(); blob.terminate(); app.wait(); blob.wait()
print('RESULT', sum(res), '/', len(res)); sys.exit(0 if all(res) else 1)
