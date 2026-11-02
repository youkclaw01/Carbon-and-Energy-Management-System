"""중앙 수신 검증/멱등/거절 시험. usage: test_ingest.py <base_url> <key_id> <key> <site>   (키는 출력하지 않는다)"""
import sys, json, time, hmac, hashlib, uuid, urllib.request, urllib.error
base, kid, key, site = sys.argv[1:5]; NS = uuid.UUID('6f1c5d0a-3b7e-4e4e-9a52-0a11fac70001'); res = []
def post(events, key_=key, kid_=kid, ts=None, site_=site):
    body = json.dumps({'site_id': site_, 'epoch': 'T', 'events': events}).encode(); ts = str(ts or int(time.time()))
    sig = hmac.new(key_.encode(), ts.encode() + b'.' + body, hashlib.sha256).hexdigest()
    rq = urllib.request.Request(base + '/v1/events', data=body, method='POST', headers={'Content-Type': 'application/json', 'X-AMA-Site': site_, 'X-AMA-Key-Id': kid_, 'X-AMA-Timestamp': ts, 'X-AMA-Signature': sig})
    try:
        with urllib.request.urlopen(rq, timeout=15) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')
def ev(seq, typ='heartbeat', payload=None, site_=site, ep='T'):
    return dict(schema='ama.factory.v1', event_id=str(uuid.uuid5(NS, f'{site_}|{ep}|{seq}')), site_id=site_, epoch=ep, seq=seq, ts=time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()) + '.000Z', type=typ, ref='SELFTEST', payload=payload or {'uptime_s': 1}, source={'vm': 'test', 'mode': 'SIMULATED'})
def chk(name, ok, info=''): res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + name, info)
b = int(time.time()) % 10**7 * 10
c, d = post([ev(b), ev(b + 1)]); chk('정상 수신 2건', c == 200 and d['accepted'] == 2, d)
c, d = post([ev(b), ev(b + 1)]); chk('재전송은 중복 처리', c == 200 and d['accepted'] == 0 and d['duplicates'] == 2, d)
e = ev(b); e['payload'] = {'uptime_s': 999}; c, d = post([e]); chk('같은 ID 다른 내용은 conflict', c == 200 and d['rejected'] and d['rejected'][0]['reason'] == 'conflict', d)
c, d = post([ev(b + 2)], key_='x' * 64); chk('잘못된 서명 401', c == 401, d)
c, d = post([ev(b + 3)], kid_='nope'); chk('모르는 키 ID 401', c == 401, d)
c, d = post([ev(b + 4)], ts=int(time.time()) - 900); chk('오래된 타임스탬프 401', c == 401, d)
x = ev(b + 5); x['event_id'] = str(uuid.uuid4()); c, d = post([x]); chk('event_id 위조 거절', c == 200 and d['rejected'] and d['rejected'][0]['reason'] == 'event_id mismatch', d)
c, d = post([ev(b + 6, typ='evil.type')]); chk('허용 안 된 종류 거절', c == 200 and d['rejected'] and d['rejected'][0]['reason'] == 'type not allowed', d)
c, d = post([ev(b + 7, site_='XX-99')], ); chk('다른 공장 이벤트 거절', c == 200 and d['rejected'], d)
c, d = post([ev(b + 8, payload={'a': 'x' * 5000})]); chk('payload 크기 초과 거절', c == 200 and d['rejected'] and d['rejected'][0]['reason'] == 'payload', d)
c, d = post([ev(b + 9 + i) for i in range(201)]); chk('배치 200건 초과 400', c == 400, d)
c, d = post([], site_='XX-99'); chk('키와 다른 site 400', c == 400, d)
print('RESULT', sum(res), '/', len(res)); sys.exit(0 if all(res) else 1)
