#!/usr/bin/env python3
"""ingest-api — DB01 접수 메타데이터 조회(읽기 전용). S01 설계 5.2: GET /v1/ingestions, GET /v1/ingestions/{batchId}.
반환: 접수 메타데이터(상태·순번 범위·건수·mode·원문 위치 참조·다이제스트). 원문 본문·SAS URL은 반환하지 않는다. 404는 존재하지 않을 때만. 오류는 {code, retryable, correlationId}.
한계: 사용자·워크로드 인가(grant 확인, ingestions.read)는 S07 권한 원장 구축 전이라 구현하지 않았다 → 내부 전용 노출·GET만 허용.
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, PORT. 시험용 API_FAKE=1."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, json, time, uuid, base64, threading, urllib.request, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
COLS = "b.batchId, b.sourceId, s.plantId, b.sourceEventId, b.status, b.eventCount, b.duplicateCount, b.rejectedCount, b.firstSeq, b.lastSeq, b.epoch, b.eventTime, b.receivedAt, b.mode, b.environmentId, b.sourceRegistryVersion, b.rawRef, b.rawDigest, b.schemaVersion, b.reasonCode, b.rowVersion"
KEYS = ['batchId', 'sourceId', 'plantId', 'sourceEventId', 'status', 'eventCount', 'duplicateCount', 'rejectedCount', 'firstSeq', 'lastSeq', 'epoch', 'eventTime', 'receivedAt', 'mode', 'environmentId', 'sourceRegistryVersion', 'rawRef', 'rawDigest', 'schemaVersion', 'reasonCode', 'rowVersion']
STATS = dict(requests=0, errors=0, started=time.time())


def _iso(v): return v.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (v.microsecond // 1000) if hasattr(v, 'strftime') else v
def row(r):
    d = dict(zip(KEYS, r)); d['batchId'] = str(d['batchId']); d['eventTime'] = _iso(d['eventTime']); d['receivedAt'] = _iso(d['receivedAt']); return d


class Sql:
    def __init__(self):
        import pytds, certifi
        self.pytds, self.cafile, self.conn, self.lock = pytds, certifi.where(), None, threading.Lock(); self.srv, self.db = os.environ['SQL_SERVER'], os.environ['SQL_DB']
    def _tok(self):
        q = {'resource': 'https://database.windows.net/', 'api-version': '2019-08-01'}
        if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
        return json.loads(urllib.request.urlopen(urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=15).read())['access_token']
    def q(self, sql, params=()):
        with self.lock:      # pytds 연결은 스레드 안전하지 않아 질의를 직렬화한다. 연결 오류는 재연결 후 한 번 더 시도한다
            try: return self._q(sql, params)
            except Exception: time.sleep(0.3); return self._q(sql, params)
    def _q(self, sql, params=()):
        try:
            if self.conn is None: self.conn = self.pytds.connect(self.srv, self.db, port=1433, access_token_callable=self._tok, cafile=self.cafile, autocommit=True, login_timeout=20, timeout=30)
            cur = self.conn.cursor(); cur.execute(sql, params); return cur.fetchall()
        except Exception:
            try: self.conn.close()
            except Exception: pass
            self.conn = None; raise
    def get(self, bid): r = self.q("SELECT " + COLS + " FROM dbo.IngestionBatch b JOIN dbo.SourceRegistry s ON s.sourceId=b.sourceId WHERE b.batchId=%s", (bid,)); return row(r[0]) if r else None
    def list(self, plant, ps, pe, cur_at, cur_id, limit):
        w, p = [], []
        if plant: w.append('s.plantId=%s'); p.append(plant)
        if ps: w.append('b.receivedAt>=%s'); p.append(ps)
        if pe: w.append('b.receivedAt<%s'); p.append(pe)
        if cur_at: w.append('(b.receivedAt<%s OR (b.receivedAt=%s AND b.batchId<%s))'); p += [cur_at, cur_at, cur_id]
        sql = "SELECT TOP (%d) " % (limit + 1) + COLS + " FROM dbo.IngestionBatch b JOIN dbo.SourceRegistry s ON s.sourceId=b.sourceId" + (' WHERE ' + ' AND '.join(w) if w else '') + " ORDER BY b.receivedAt DESC, b.batchId DESC"
        return [row(r) for r in self.q(sql, tuple(p))]
    def summary(self, plant):
        r = self.q("SELECT b.status, COUNT(*), COALESCE(SUM(b.eventCount),0), MAX(b.receivedAt) FROM dbo.IngestionBatch b JOIN dbo.SourceRegistry s ON s.sourceId=b.sourceId" + (" WHERE s.plantId=%s" if plant else "") + " GROUP BY b.status", (plant,) if plant else ())
        return [dict(status=x[0], batches=x[1], events=x[2], lastReceivedAt=_iso(x[3])) for x in r]


    def sources(self, plant):
        r = self.q("SELECT sourceId, plantId, sourceKind, environmentId, mode, status, registryVersion FROM dbo.SourceRegistry" + (" WHERE plantId=%s" if plant else "") + " ORDER BY sourceId", (plant,) if plant else ())
        return [dict(sourceId=x[0], plantId=x[1], sourceKind=x[2], environmentId=x[3], mode=x[4], status=x[5], registryVersion=x[6]) for x in r]


class Fake:
    def __init__(self, n=25):
        self.rows = []
        for i in range(n): self.rows.append(dict(batchId=str(uuid.uuid5(uuid.NAMESPACE_DNS, 'b%d' % i)), sourceId='src-kr01-vm01', plantId='KR-01', sourceEventId='E:%d-%d:x' % (i * 10, i * 10 + 9), status='LANDED', eventCount=10, duplicateCount=0, rejectedCount=0, firstSeq=i * 10, lastSeq=i * 10 + 9, epoch='E', eventTime=None, receivedAt='2026-10-30T10:%02d:%02d.000Z' % (i // 60, i % 60), mode='SIMULATED', environmentId='prd', sourceRegistryVersion=1, rawRef='ref', rawDigest='d' * 64, schemaVersion='ama.factory.v1', reasonCode=None, rowVersion=1))
        self.rows.sort(key=lambda r: (r['receivedAt'], r['batchId']), reverse=True)
    def get(self, bid): return next((r for r in self.rows if r['batchId'] == bid), None)
    def list(self, plant, ps, pe, cur_at, cur_id, limit):
        rs = [r for r in self.rows if (not plant or r['plantId'] == plant) and (not cur_at or (r['receivedAt'], r['batchId']) < (cur_at, cur_id))]; return rs[:limit + 1]
    def sources(self, plant): return [dict(sourceId='src-kr01-vm01', plantId='KR-01', sourceKind='FACTORY_VM', environmentId='prod', mode='SIMULATED', status='ACTIVE', registryVersion=1)]
    def summary(self, plant): return [dict(status='LANDED', batches=len(self.rows), events=sum(r['eventCount'] for r in self.rows), lastReceivedAt=self.rows[0]['receivedAt'])]


def enc(at, bid): return base64.urlsafe_b64encode(json.dumps([at, bid]).encode()).decode()
def dec(c):
    try: a, b = json.loads(base64.urlsafe_b64decode(c.encode())); uuid.UUID(b); return str(a), b
    except Exception: raise ValueError('cursor')


def handle(db, path, cid):
    u = urlparse(path); q = {k: v[0] for k, v in parse_qs(u.query).items()}; parts = [x for x in u.path.split('/') if x]
    if u.path == '/healthz': return 200, {'ok': True}
    if parts == ['v1', 'sources']: return 200, {'items': db.sources(q.get('plantId'))}      # S02 등 소비 서비스가 source mode를 소유 API로 확인한다(요청 값 불신)
    if parts == ['v1', 'ingestions', 'summary']: return 200, {'items': db.summary(q.get('plantId'))}
    if len(parts) == 3 and parts[:2] == ['v1', 'ingestions']:
        try: uuid.UUID(parts[2])
        except ValueError: return 400, {'code': 'BAD_ID', 'retryable': False, 'correlationId': cid}
        r = db.get(parts[2]); return (200, r) if r else (404, {'code': 'NOT_FOUND', 'retryable': False, 'correlationId': cid})
    if parts == ['v1', 'ingestions']:
        try: limit = max(1, min(200, int(q.get('limit', '50'))))
        except ValueError: return 400, {'code': 'BAD_LIMIT', 'field': 'limit', 'retryable': False, 'correlationId': cid}
        try: ca, ci = dec(q['cursor']) if q.get('cursor') else (None, None)
        except ValueError: return 400, {'code': 'BAD_CURSOR', 'field': 'cursor', 'retryable': False, 'correlationId': cid}
        rows = db.list(q.get('plantId'), q.get('periodStart'), q.get('periodEnd'), ca, ci, limit); more = len(rows) > limit; rows = rows[:limit]
        return 200, {'items': rows, 'nextCursor': enc(rows[-1]['receivedAt'], rows[-1]['batchId']) if more and rows else None}
    return 404, {'code': 'NOT_FOUND', 'retryable': False, 'correlationId': cid}


def main():
    db = Fake() if os.environ.get('API_FAKE') else Sql()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, c, o):
            b = json.dumps(o, default=str, ensure_ascii=False).encode(); self.send_response(c); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            STATS['requests'] += 1; cid = self.headers.get('X-Correlation-Id') or str(uuid.uuid4())
            try: c, o = handle(db, self.path, cid)
            except Exception as e: STATS['errors'] += 1; c, o = 503, {'code': 'STORE_UNAVAILABLE', 'retryable': True, 'correlationId': cid}
            self._send(c, o)
        def _no(self): self._send(405, {'code': 'METHOD_NOT_ALLOWED', 'retryable': False})
        do_POST = do_PUT = do_DELETE = do_PATCH = _no
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()


if __name__ == '__main__': main()
