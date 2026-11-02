"""ingest-api 시험(메모리 저장소): 목록 페이징(커서)·단건·오류 코드·쓰기 거절."""
import sys, os, json, time, subprocess, urllib.request, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); PORT = 8841; res = []
app = subprocess.Popen([sys.executable, os.path.join(ROOT, 'ingestapi', 'ingest_api.py')], env=dict(os.environ, API_FAKE='1', PORT=str(PORT)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.2)
def g(p, m='GET'):
    rq = urllib.request.Request(f'http://127.0.0.1:{PORT}{p}', method=m, data=b'{}' if m != 'GET' else None)
    try:
        with urllib.request.urlopen(rq, timeout=5) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')
def chk(n, ok, info=''): res.append(bool(ok)); print(('PASS ' if ok else 'FAIL ') + n, info)
try:
    c, d = g('/v1/ingestions?limit=10'); ids = [x['batchId'] for x in d['items']]; chk('첫 쪽 10건·nextCursor', c == 200 and len(ids) == 10 and d['nextCursor'], (c, len(ids)))
    c, d2 = g('/v1/ingestions?limit=10&cursor=' + d['nextCursor']); ids2 = [x['batchId'] for x in d2['items']]; chk('둘째 쪽 10건, 겹침 없음, 시간 내림차순', c == 200 and len(ids2) == 10 and not set(ids) & set(ids2) and d['items'][-1]['receivedAt'] >= d2['items'][0]['receivedAt'])
    c, d3 = g('/v1/ingestions?limit=10&cursor=' + d2['nextCursor']); chk('마지막 쪽 5건, nextCursor 없음, 합계 25건 중복 없음', c == 200 and len(d3['items']) == 5 and d3['nextCursor'] is None and len(set(ids + ids2 + [x['batchId'] for x in d3['items']])) == 25)
    c, d = g('/v1/ingestions/' + ids[0]); chk('단건 조회 200·필드(mode·rawDigest·status)', c == 200 and d['batchId'] == ids[0] and d['mode'] == 'SIMULATED' and d['status'] == 'LANDED' and 'rawDigest' in d)
    c, d = g('/v1/ingestions/00000000-0000-0000-0000-000000000001'); chk('없는 batch는 404 NOT_FOUND', c == 404 and d['code'] == 'NOT_FOUND' and d['retryable'] is False)
    c, d = g('/v1/ingestions/abc'); chk('형식 오류 400 BAD_ID', c == 400 and d['code'] == 'BAD_ID')
    c, d = g('/v1/ingestions?cursor=zzz'); chk('커서 오류 400 BAD_CURSOR', c == 400 and d['code'] == 'BAD_CURSOR')
    c, d = g('/v1/ingestions?limit=abc'); chk('limit 오류 400 BAD_LIMIT', c == 400 and d['code'] == 'BAD_LIMIT')
    c, d = g('/v1/ingestions', 'POST'); chk('쓰기(POST)는 405', c == 405)
    c, d = g('/v1/ingestions/summary'); chk('요약 200', c == 200 and d['items'][0]['batches'] == 25)
    c, d = g('/v1/sources?plantId=KR-01'); chk('source mode 조회(소유 API) 200·SIMULATED·ACTIVE', c == 200 and d['items'][0]['mode'] == 'SIMULATED' and d['items'][0]['status'] == 'ACTIVE' and 'boundPrincipal' not in d['items'][0])
finally:
    app.terminate(); app.wait()
print('RESULT', sum(res), '/', len(res)); sys.exit(0 if all(res) else 1)
