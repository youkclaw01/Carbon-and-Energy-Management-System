"""수집 품질(seq 결측·늦은 도착·에포크) 시험. usage: test_quality.py <base_url> <key_id> <key> <site>  — 실제 이벤트로 통계에 반영되므로 운영 사이트에 쓰지 말고 로컬/시험 수신 앱에서 실행한다."""
import sys, json, time, hmac, hashlib, uuid, urllib.request, urllib.error
base, kid, key, site = sys.argv[1:5]; NS = uuid.UUID('6f1c5d0a-3b7e-4e4e-9a52-0a11fac70001'); res = []
def post(events, ep):
    body = json.dumps({'site_id': site, 'epoch': ep, 'events': events}).encode(); ts = str(int(time.time())); sig = hmac.new(key.encode(), ts.encode() + b'.' + body, hashlib.sha256).hexdigest()
    rq = urllib.request.Request(base + '/v1/events', data=body, method='POST', headers={'Content-Type': 'application/json', 'X-AMA-Site': site, 'X-AMA-Key-Id': kid, 'X-AMA-Timestamp': ts, 'X-AMA-Signature': sig})
    with urllib.request.urlopen(rq, timeout=15) as r: return json.loads(r.read())
def ev(seq, ep):
    return dict(schema='ama.factory.v1', event_id=str(uuid.uuid5(NS, f'{site}|{ep}|{seq}')), site_id=site, epoch=ep, seq=seq, ts='2026-10-30T00:00:%02d.000Z' % (seq % 60), type='heartbeat', ref='QTEST', payload={'uptime_s': seq})
def q(): return json.loads(urllib.request.urlopen(base + f'/v1/sites/{site}/quality', timeout=10).read())
def chk(n, ok, info=''): res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n, info)
ep = 'Q' + str(int(time.time()))
post([ev(i, ep) for i in (1, 2, 3, 4, 5)], ep); d = q(); chk('연속 5건은 결측 0', d['missing'] == 0 and d['epoch'] == ep and d['last_seq'] == 5, {k: d[k] for k in ('missing', 'gaps', 'late')})
post([ev(i, ep) for i in (9, 10)], ep); d = q(); chk('6~8 건너뛰면 결측 3건·구간 [6,8]', d['missing'] == 3 and d['gaps'] == [[6, 8]], {k: d[k] for k in ('missing', 'gaps', 'late')})
post([ev(7, ep)], ep); d = q(); chk('7이 늦게 도착하면 결측 2건으로 줄고 구간이 둘로 갈림, late=1', d['missing'] == 2 and d['gaps'] == [[6, 6], [8, 8]] and d['late'] == 1, {k: d[k] for k in ('missing', 'gaps', 'late')})
r = post([ev(7, ep)], ep); d = q(); chk('같은 7 재전송은 중복이며 late 증가 없음', r['duplicates'] == 1 and d['late'] == 1 and d['missing'] == 2, r)
post([ev(6, ep), ev(8, ep)], ep); d = q(); chk('6·8 재전송으로 결측 0', d['missing'] == 0 and d['gap_count'] == 0 and d['late'] == 3, {k: d[k] for k in ('missing', 'gaps', 'late')})
ep2 = ep + 'b'; post([ev(1, ep2)], ep2); d = q(); chk('에포크가 바뀌면 새로 시작하고 이전 에포크 요약 보존', d['epoch'] == ep2 and d['epochs'] >= 1 and d['prev_epoch'] and d['prev_epoch']['epoch'] == ep and d['prev_epoch']['last_seq'] == 10, d['prev_epoch'])
b = json.loads(urllib.request.urlopen(base + '/v1/sites', timeout=10).read())['sites']; chk('사이트 목록에 quality 요약 포함', all('quality' in x for x in b))
print('RESULT', sum(res), '/', len(res)); sys.exit(0 if all(res) else 1)
