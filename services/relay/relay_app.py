#!/usr/bin/env python3
"""ingest-relay — DB01 IngestionOutbox(PENDING)를 읽어 Service Bus 큐 sbq-landed로 EV01 초안 이벤트를 보낸다(S01 설계 06절).
- at-least-once: SENT는 broker가 수락(201)한 뒤에만 기록하고, 같은 eventId는 MessageId로 중복 제거 가능하게 보낸다. SENT는 downstream 완료가 아니다.
- 실패는 지수 백오프(최대 300초), 8회 실패 시 FAILED(자동 폐기 없음, 조회 가능). SENDING에서 멈춘 행은 60초 뒤 다시 집어 간다.
- 인증: 관리 ID(키 없음). env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, SB_NAMESPACE, SB_QUEUE, PORT. 시험용: RELAY_FAKE=1(메모리 저장소·싱크), FAKE_SINK_FAIL_FILE."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, json, time, uuid, threading, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
STATS = dict(sent=0, failed=0, retried=0, last_ok=None, last_err=None, started=time.time(), loop=0)
MAX_ATTEMPT = 8


def _imds(resource):
    q = {'resource': resource, 'api-version': '2019-08-01'}
    if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
    rq = urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']})
    return json.loads(urllib.request.urlopen(rq, timeout=15).read())['access_token']


class SqlStore:
    def __init__(self):
        import pytds, certifi
        self.pytds, self.cafile = pytds, certifi.where(); self.conn = None; self.srv, self.db = os.environ['SQL_SERVER'], os.environ['SQL_DB']
    def _c(self):
        if self.conn is None: self.conn = self.pytds.connect(self.srv, self.db, port=1433, access_token_callable=lambda: _imds('https://database.windows.net/'), cafile=self.cafile, autocommit=True, login_timeout=20, timeout=30)
        return self.conn
    def _run(self, fn):
        try: return fn(self._c().cursor())
        except Exception:
            try: self.conn.close()
            except Exception: pass
            self.conn = None; raise
    def claim(self, n=50):
        def f(cur):
            cur.execute("UPDATE TOP (%d) dbo.IngestionOutbox SET deliveryState='SENDING', attempt=attempt+1, nextAttemptAt=DATEADD(second,60,SYSUTCDATETIME()) OUTPUT inserted.eventId, inserted.batchId, inserted.type, inserted.schemaVersion, inserted.digest, inserted.payloadRef, inserted.attempt, inserted.createdAt WHERE (deliveryState='PENDING' AND nextAttemptAt<=SYSUTCDATETIME()) OR (deliveryState='SENDING' AND nextAttemptAt<=SYSUTCDATETIME())" % n)
            rows = cur.fetchall(); out = []
            for r in rows:
                cur.execute("SELECT b.sourceId, b.epoch, b.firstSeq, b.lastSeq, b.eventCount, b.mode, b.environmentId, b.sourceRegistryVersion, b.receivedAt, s.plantId FROM dbo.IngestionBatch b JOIN dbo.SourceRegistry s ON s.sourceId=b.sourceId WHERE b.batchId=%s", (str(r[1]),)); b = cur.fetchone()
                out.append(dict(eventId=str(r[0]), batchId=str(r[1]), type=r[2], schemaVersion=r[3], digest=r[4], payloadRef=r[5], attempt=r[6], created=str(r[7]), batch=dict(sourceId=b[0], epoch=b[1], firstSeq=b[2], lastSeq=b[3], eventCount=b[4], mode=b[5], environmentId=b[6], sourceRegistryVersion=b[7], receivedAt=str(b[8]), plantId=b[9]) if b else None))
            return out
        return self._run(f)
    def mark_sent(self, eid): self._run(lambda cur: cur.execute("UPDATE dbo.IngestionOutbox SET deliveryState='SENT', sentAt=SYSUTCDATETIME() WHERE eventId=%s AND deliveryState='SENDING'", (eid,)))
    def mark_retry(self, eid, attempt):
        if attempt >= MAX_ATTEMPT: self._run(lambda cur: cur.execute("UPDATE dbo.IngestionOutbox SET deliveryState='FAILED' WHERE eventId=%s", (eid,))); return 'FAILED'
        d = min(300, 2 ** attempt); self._run(lambda cur: cur.execute("UPDATE dbo.IngestionOutbox SET deliveryState='PENDING', nextAttemptAt=DATEADD(second,%d,SYSUTCDATETIME()) WHERE eventId=%%s" % d, (eid,))); return 'PENDING'
    def counts(self):
        def f(cur): cur.execute("SELECT deliveryState, COUNT(*) FROM dbo.IngestionOutbox GROUP BY deliveryState"); return {r[0]: r[1] for r in cur.fetchall()}
        return self._run(f)


class FakeStore:
    def __init__(self): self.rows = {}; self.lock = threading.Lock()
    def add(self, n=1):
        for _ in range(n):
            e = str(uuid.uuid4()); self.rows[e] = dict(eventId=e, batchId=str(uuid.uuid4()), type='ingestion.landed', schemaVersion='ev01-draft.1', digest='d' * 64, payloadRef='ref', attempt=0, created='t', state='PENDING', next=0, batch=dict(sourceId='src-kr01-vm01', plantId='KR-01', epoch='E', firstSeq=1, lastSeq=2, eventCount=2, mode='SIMULATED', environmentId='prd', sourceRegistryVersion=1, receivedAt='t'))
    def claim(self, n=50):
        out = []
        for r in self.rows.values():
            if r['state'] in ('PENDING', 'SENDING') and r['next'] <= time.time() and len(out) < n: r['state'] = 'SENDING'; r['attempt'] += 1; r['next'] = time.time() + 60; out.append(dict(r))
        return out
    def mark_sent(self, e): self.rows[e]['state'] = 'SENT'
    def mark_retry(self, e, a):
        r = self.rows[e]
        if a >= MAX_ATTEMPT: r['state'] = 'FAILED'; return 'FAILED'
        r['state'] = 'PENDING'; r['next'] = time.time() + min(300, 2 ** a) * (0 if os.environ.get('FAKE_NO_BACKOFF') else 1); return 'PENDING'
    def counts(self):
        c = {}
        for r in self.rows.values(): c[r['state']] = c.get(r['state'], 0) + 1
        return c


class SbSink:
    def __init__(self): self.url = 'https://%s.servicebus.windows.net/%s/messages' % (os.environ['SB_NAMESPACE'], os.environ['SB_QUEUE'])
    def send(self, msg):
        body = json.dumps(msg, ensure_ascii=False).encode()
        rq = urllib.request.Request(self.url, data=body, method='POST', headers={'Authorization': 'Bearer ' + _imds('https://servicebus.azure.net'), 'Content-Type': 'application/json', 'BrokerProperties': json.dumps({'MessageId': msg['eventId'], 'CorrelationId': msg['correlationId'], 'Label': msg['type']})})
        urllib.request.urlopen(rq, timeout=20).read()


class FakeSink:
    def __init__(self): self.msgs = []
    def send(self, msg):
        f = os.environ.get('FAKE_SINK_FAIL_FILE')
        if f and os.path.exists(f): raise RuntimeError('fake sink down')
        self.msgs.append(msg)


def envelope(r):
    b = r['batch'] or {}
    return dict(eventId=r['eventId'], type=r['type'], schemaVersion=r['schemaVersion'], source='S01', country='KR', time=r['created'], correlationId=r['batchId'], causationId=r['batchId'], dataRef=r['payloadRef'], digest=r['digest'],
                data=dict(batchId=r['batchId'], sourceId=b.get('sourceId'), plantId=b.get('plantId'), epoch=b.get('epoch'), firstSeq=b.get('firstSeq'), lastSeq=b.get('lastSeq'), eventCount=b.get('eventCount'), mode=b.get('mode'), environmentId=b.get('environmentId'), sourceRegistryVersion=b.get('sourceRegistryVersion'), receivedAt=b.get('receivedAt')))


def step(store, sink):
    rows = store.claim(50)
    for r in rows:
        try: sink.send(envelope(r)); store.mark_sent(r['eventId']); STATS['sent'] += 1; STATS['last_ok'] = time.time()
        except Exception as e:
            STATS['last_err'] = (type(e).__name__ + ': ' + str(e))[:160]; STATS['retried'] += 1
            if store.mark_retry(r['eventId'], r['attempt']) == 'FAILED': STATS['failed'] += 1
    return len(rows)


def main():
    fake = bool(os.environ.get('RELAY_FAKE')); store = FakeStore() if fake else SqlStore(); sink = FakeSink() if fake else SbSink(); G['store'], G['sink'] = store, sink
    def loop():
        while True:
            try: STATS['loop'] += 1; n = step(store, sink)
            except Exception as e: STATS['last_err'] = ('loop ' + type(e).__name__ + ': ' + str(e))[:160]; n = 0; time.sleep(3)
            time.sleep(0.5 if n else 2)
    threading.Thread(target=loop, daemon=True).start()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == '/healthz': out = {'ok': True}
            elif self.path == '/v1/relay/stats':
                try: c = G['store'].counts()
                except Exception as e: c = {'error': type(e).__name__}
                out = dict(STATS, outbox=c, uptime_s=int(time.time() - STATS['started']))
            elif self.path == '/v1/relay/fake/add' and fake: G['store'].add(int(1)); out = {'ok': True}
            elif self.path == '/v1/relay/fake/sink' and fake: out = {'n': len(G['sink'].msgs), 'ids': [m['eventId'] for m in G['sink'].msgs]}
            else: self.send_response(404); self.end_headers(); return
            b = json.dumps(out, default=str).encode(); self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()


G = {}
if __name__ == '__main__': main()
