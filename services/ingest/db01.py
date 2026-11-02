"""DB01(ingest) 접수 메타데이터 기록 — 원문은 SQL에 두지 않고 Blob(Bronze)에 두며 SQL에는 접수·식별·대사 메타데이터만 남긴다(S01 설계 04·06절).
한 접수 배치마다 한 트랜잭션으로 IngestionBatch(LANDED) + IngestionOutbox(PENDING) + IngestionAudit(해시 체인)를 기록한다. 실패하면 예외를 올려 호출 쪽이 ACK하지 않게 한다.
관리 ID 토큰(Entra 전용 서버). env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID. 시험용: DB_FAKE=1(메모리 기록), DB_FAKE_FAIL_FILE(파일이 있으면 실패)."""
import os, json, time, uuid, hashlib, threading, urllib.request, urllib.parse

REGISTRY = {'KR-01': 'src-kr01-vm01', 'KR-02': 'src-kr02-vm01', 'KR-03': 'src-kr03-vm01', 'KR-04': 'src-kr04-vm01', 'KR-05': 'src-kr05-vm01', 'JP-01': 'src-jp01-vm01', 'JP-02': 'src-jp02-vm01', 'JP-03': 'src-jp03-vm01', 'JP-04': 'src-jp04-vm01', 'SG-01': 'src-sg01-vm01', 'SG-02': 'src-sg02-vm01', 'SG-03': 'src-sg03-vm01'}


class Fake:
    def __init__(self): self.rows = []; self.q = []; self.lock = threading.Lock()
    def record(self, **kw):
        if os.environ.get('DB_FAKE_FAIL_FILE') and os.path.exists(os.environ['DB_FAKE_FAIL_FILE']): raise RuntimeError('fake db down')
        with self.lock: self.rows.append(kw); return str(uuid.uuid4())
    def quarantine(self, **kw):
        with self.lock: self.q.append(kw)
    def stats(self): return dict(kind='fake', batches=len(self.rows), quarantined=len(self.q))


class Sql:
    def __init__(self):
        import pytds, certifi
        self.pytds, self.cafile = pytds, certifi.where(); self.lock = threading.Lock(); self.conn = None; self.reg = {}; self.prev = None
        self.srv, self.db = os.environ['SQL_SERVER'], os.environ['SQL_DB']; self.ok = 0; self.err = 0; self.last_err = None; self.last_ok = None

    def _token(self):
        q = {'resource': 'https://database.windows.net/', 'api-version': '2019-08-01'}
        if os.environ.get('AZURE_CLIENT_ID'): q['client_id'] = os.environ['AZURE_CLIENT_ID']
        rq = urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']})
        return json.loads(urllib.request.urlopen(rq, timeout=15).read())['access_token']

    def _connect(self):
        self.conn = self.pytds.connect(self.srv, self.db, port=1433, access_token_callable=self._token, cafile=self.cafile, autocommit=False, login_timeout=20, timeout=30)
        cur = self.conn.cursor(); cur.execute("SELECT sourceId, registryVersion, mode, environmentId, status FROM dbo.SourceRegistry")
        self.reg = {r[0]: dict(v=r[1], mode=r[2], env=r[3], status=r[4]) for r in cur.fetchall()}; self.conn.commit()
        cur.execute("SELECT TOP 1 recordHash FROM dbo.IngestionAudit ORDER BY auditId DESC"); r = cur.fetchone(); self.prev = r[0] if r else None; self.conn.commit()

    def record(self, sid, epoch, first, last, count, dup, rej, req_digest, raw_digest, raw_ref, last_ts, now, trace=None):
        src = REGISTRY.get(sid)
        with self.lock:
            try:
                if self.conn is None: self._connect()
                r = self.reg.get(src)
                if not r or r['status'] != 'ACTIVE': raise RuntimeError('source not registered/active: %s' % src)
                batch = str(uuid.uuid4()); ev = str(uuid.uuid4()); ts = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now)) + '.%03d' % int((now % 1) * 1000)
                et = (last_ts or '').replace('T', ' ').rstrip('Z')[:23] or ts
                sev = '%s:%d-%d:%s' % (epoch, first, last, raw_digest[:12])
                rec = hashlib.sha256(('%s|%s|%s|%s|%s' % (self.prev or '', 'INGEST_LANDED', src, batch, raw_digest)).encode()).hexdigest()
                cur = self.conn.cursor()
                cur.execute("INSERT INTO dbo.IngestionBatch(batchId, sourceId, sourceEventId, requestDigest, digestVersion, rawDigest, schemaVersion, epoch, firstSeq, lastSeq, eventCount, duplicateCount, rejectedCount, eventTime, receivedAt, environmentId, mode, sourceRegistryVersion, rawRef, status) VALUES (%s,%s,%s,%s,1,%s,'ama.factory.v1',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'LANDED')",
                            (batch, src, sev, req_digest, raw_digest, epoch, first, last, count, dup, rej, et, ts, r['env'], r['mode'], r['v'], raw_ref))
                cur.execute("INSERT INTO dbo.IngestionOutbox(eventId, batchId, type, schemaVersion, digest, payloadRef) VALUES (%s,%s,'ingestion.landed','ev01-draft.1',%s,%s)", (ev, batch, raw_digest, raw_ref))
                cur.execute("INSERT INTO dbo.IngestionAudit(actor, action, sourceId, batchId, afterVersion, reason, traceId, at, previousHash, recordHash) VALUES ('central-ingest','INGEST_LANDED',%s,%s,1,NULL,%s,%s,%s,%s)", (src, batch, trace, ts, self.prev, rec))
                self.conn.commit(); self.prev = rec; self.ok += 1; self.last_ok = time.time(); return batch
            except Exception as e:
                self.err += 1; self.last_err = (type(e).__name__ + ': ' + str(e))[:160]
                try: self.conn.rollback()
                except Exception: pass
                try: self.conn.close()
                except Exception: pass
                self.conn = None; raise


    def quarantine(self, sid, epoch, first, last, count, reason, req_digest, ids_digest, now, trace=None):
        """검증 실패·충돌 이벤트를 QUARANTINED 접수 행으로 남긴다(원문은 공장 outbox에 남아 있고 여기에는 이유·범위·건수만). 실패해도 ACK를 막지 않는다(호출 쪽이 예외를 삼킨다)."""
        src = REGISTRY.get(sid)
        with self.lock:
            try:
                if self.conn is None: self._connect()
                r = self.reg.get(src)
                if not r: raise RuntimeError('source not registered: %s' % src)
                batch = str(uuid.uuid4()); ts = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now)) + '.%03d' % int((now % 1) * 1000); sev = '%s:%d-%d:q%s' % (epoch, first, last, ids_digest[:12])
                rec = hashlib.sha256(('%s|%s|%s|%s|%s' % (self.prev or '', 'INGEST_QUARANTINED', src, batch, ids_digest)).encode()).hexdigest(); cur = self.conn.cursor()
                cur.execute("INSERT INTO dbo.IngestionBatch(batchId, sourceId, sourceEventId, requestDigest, digestVersion, rawDigest, schemaVersion, epoch, firstSeq, lastSeq, eventCount, duplicateCount, rejectedCount, eventTime, receivedAt, environmentId, mode, sourceRegistryVersion, rawRef, status, reasonCode) VALUES (%s,%s,%s,%s,1,%s,'ama.factory.v1',%s,%s,%s,0,0,%s,NULL,%s,%s,%s,%s,NULL,'QUARANTINED',%s)",
                            (batch, src, sev, req_digest, ids_digest, epoch, first, last, count, ts, r['env'], r['mode'], r['v'], reason[:64]))
                cur.execute("INSERT INTO dbo.IngestionAudit(actor, action, sourceId, batchId, afterVersion, reason, traceId, at, previousHash, recordHash) VALUES ('central-ingest','INGEST_QUARANTINED',%s,%s,1,%s,%s,%s,%s,%s)", (src, batch, reason[:200], trace, ts, self.prev, rec))
                self.conn.commit(); self.prev = rec; self.q_ok = getattr(self, 'q_ok', 0) + 1
            except Exception as e:
                self.err += 1; self.last_err = ('quarantine ' + type(e).__name__ + ': ' + str(e))[:160]
                try: self.conn.rollback()
                except Exception: pass
                try: self.conn.close()
                except Exception: pass
                self.conn = None; raise

    def stats(self): return dict(kind='sql', quarantined=getattr(self, 'q_ok', 0), ok=self.ok, errors=self.err, last_err=self.last_err, last_ok=self.last_ok)


def make():
    if os.environ.get('DB_FAKE'): return Fake()
    if os.environ.get('SQL_SERVER'): return Sql()
    return None
