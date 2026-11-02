#!/usr/bin/env python3
"""DB 초기화 작업: 관리 ID 토큰으로 SQL(Entra 전용)에 접속해 DDL과 앱별 최소 권한을 적용한다. 결과는 표준 출력(작업 로그)과 종료 코드로 남긴다.
env: SQL_SERVER, SQL_DB, AZURE_CLIENT_ID, GRANTS(JSON: [{"name": UAMI 이름, "grants": ["GRANT ..."]}])"""
import os, sys, json, re, time, urllib.request, urllib.parse, ssl
import pytds, certifi
SRV, DB = os.environ['SQL_SERVER'], os.environ['SQL_DB']
def token():
    q = os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode({'resource': 'https://database.windows.net/', 'api-version': '2019-08-01', 'client_id': os.environ['AZURE_CLIENT_ID']})
    return json.loads(urllib.request.urlopen(urllib.request.Request(q, headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=20).read())['access_token']
def connect():
    return pytds.connect(SRV, DB, port=1433, access_token_callable=token, cafile=certifi.where(), autocommit=True, login_timeout=30, timeout=60)
def batches(sql): return [b.strip() for b in re.split(r'^\s*GO\s*$', sql, flags=re.M) if b.strip()]
def run(cur, sql, label):
    for i, b in enumerate(batches(sql)):
        try: cur.execute(b); print('OK  ', label, i, flush=True)
        except Exception as e: print('FAIL', label, i, type(e).__name__, str(e)[:300], flush=True); raise
t0 = time.time()
with connect() as c:
    cur = c.cursor(); cur.execute('SELECT SUSER_SNAME(), DB_NAME()'); print('connected as', cur.fetchone(), flush=True)
    run(cur, open('/app/' + os.environ.get('DDL_FILE', 'db01_ingest.sql'), encoding='utf-8').read(), 'ddl')
    for g in json.loads(os.environ.get('GRANTS', '[]')):
        run(cur, open('/app/grants.sql.tpl', encoding='utf-8').read().replace('{n}', g['name']).replace('{cid}', g['cid']).replace('{g}', '\nGO\n'.join(g['grants'])), 'grant-' + g['name'])
    cur.execute("SELECT t.name, (SELECT COUNT(*) FROM sys.columns c WHERE c.object_id=t.object_id) FROM sys.tables t ORDER BY t.name"); print('tables', cur.fetchall(), flush=True)
    if os.environ.get('DDL_FILE', 'db01_ingest.sql') == 'db01_ingest.sql': cur.execute('SELECT sourceId, plantId, mode, status FROM dbo.SourceRegistry'); print('registry', cur.fetchall(), flush=True)
    else:
        if os.environ.get('DDL_FILE') == 'db02_carbon.sql':
            for t in ('MethodologyVersion', 'FactorVersionRef'): cur.execute('SELECT COUNT(*) FROM dbo.' + t); print('seed', t, cur.fetchone(), flush=True)
print('DBINIT-DONE', round(time.time() - t0, 1), flush=True)
