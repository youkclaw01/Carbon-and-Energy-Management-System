#!/usr/bin/env python3
"""AMA 지역 메달리온 정제 작업. 같은 지역 저장소 안에서만 동작한다(자료의 지역 밖 이동 없음).
  bronze : 수신 앱이 받은 원본 이벤트(NDJSON, 추가 전용·불변)            bronze/<site>/<date>.ndjson
  silver : 검증·형 변환·중복 제거한 종류별 Parquet, 불량은 격리            silver/<type>/date=YYYY-MM-DD/part-<run>.parquet, silver/_quarantine/
  gold   : 시간·일 단위 집계 Parquet + 수신 앱이 읽는 요약 JSON            gold/<table>/date=YYYY-MM-DD/data.parquet, gold/api/<site>/summary.json
상태: silver/_state/watermark.json(블롭별 읽은 위치), gold/_meta/run-<시각>.json(계보·건수). 동시 실행은 silver/_state/lock.json 으로 막는다.
인증은 관리 ID(IDENTITY_ENDPOINT) 또는 로컬 시험용 모의 저장소."""
import os, sys, json, time, io, re, hashlib, uuid, urllib.request, urllib.error, datetime as dt, collections
import xml.etree.ElementTree as ET
import pyarrow as pa, pyarrow.parquet as pq
STORE = os.environ['STORE_URL'].rstrip('/'); RUN = time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-' + uuid.uuid4().hex[:6]; T0 = time.time()
_TOK = {'v': None, 'exp': 0}
def token():
    if _TOK['v'] and _TOK['exp'] - time.time() > 300: return _TOK['v']
    ep, hd = os.environ.get('IDENTITY_ENDPOINT'), os.environ.get('IDENTITY_HEADER')
    url = ep + '?resource=https://storage.azure.com/&api-version=2019-08-01' + ('&client_id=' + os.environ['AZURE_CLIENT_ID'] if os.environ.get('AZURE_CLIENT_ID') else '')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'X-IDENTITY-HEADER': hd}), timeout=10) as r: d = json.loads(r.read())
    _TOK['v'] = d['access_token']; _TOK['exp'] = float(d.get('expires_on', time.time() + 3000)); return _TOK['v']
def blob(method, cont, path, data=None, hdr=None, timeout=60):
    h = {'Authorization': 'Bearer ' + token(), 'x-ms-version': '2023-11-03', 'x-ms-date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}; h.update(hdr or {})
    return urllib.request.urlopen(urllib.request.Request(f'{STORE}/{cont}{path}', data=data, method=method, headers=h), timeout=timeout)
def put_block(cont, name, data, ctype='application/octet-stream'):
    blob('PUT', cont, '/' + name, data, {'x-ms-blob-type': 'BlockBlob', 'Content-Type': ctype}).read()
def get_bytes(cont, name, rng=None):
    try:
        with blob('GET', cont, '/' + name, None, {'Range': rng} if rng else None) as r: return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (404, 416): return None
        raise
def list_blobs(cont, prefix=''):
    out, marker = [], ''
    while True:
        with blob('GET', cont, '?restype=container&comp=list&prefix=%s%s' % (urllib.request.quote(prefix, safe=''), '&marker=' + marker if marker else '')) as r: root = ET.fromstring(r.read())
        for b in root.iter('Blob'):
            out.append((b.findtext('Name'), int(b.find('Properties').findtext('Content-Length') or 0)))
        marker = root.findtext('NextMarker') or ''
        if not marker: return out
def get_json(cont, name, default=None):
    b = get_bytes(cont, name); return json.loads(b) if b else default
# ---- 잠금(동시 실행 방지) ----
def lock():
    cur = get_json('silver', '_state/lock.json')
    if cur and cur.get('until', 0) > time.time(): return False
    put_block('silver', '_state/lock.json', json.dumps({'run': RUN, 'until': time.time() + 540}).encode(), 'application/json'); time.sleep(1)
    return (get_json('silver', '_state/lock.json') or {}).get('run') == RUN
def unlock(): put_block('silver', '_state/lock.json', json.dumps({'run': RUN, 'until': 0}).encode(), 'application/json')
# ---- silver 스키마 ----
TS = pa.timestamp('ms', tz='UTC'); F = pa.float64(); S = pa.string(); I = pa.int64()
BASE = [('ts', TS), ('site', S), ('epoch', S), ('seq', I), ('event_id', S), ('recv_ts', TS)]
SCHEMA = {
 'meter.reading': ('meter_reading', [('equip', S), ('kw', F), ('kwh_total', F), ('state', S)], ['equip', 'kw']),
 'energy.flow': ('energy_flow', [(k, F) for k in ('demand', 'grid', 'solar', 'ppa', 'batt', 'soc', 'co2_kg_h', 'scope1', 'scope2', 'whr_kw', 'gas_nm3h', 'water_m3h')], ['demand', 'grid']),
 'process.state': ('process_state', [('equip', S), ('line', S), ('state', S), ('speed', F), ('temp', F), ('pressure', F), ('fault', S)], ['state']),
 'production.counter': ('production_counter', [('line', S), ('wo', S), ('product', S), ('done', F), ('scrap', F), ('target', F), ('unit', S), ('status', S)], ['wo', 'done']),
 'production.workorder': ('production_workorder', [('line', S), ('wo', S), ('product', S), ('action', S), ('qty', F), ('scrap', F), ('target', F), ('unit', S), ('batch', S)], ['wo', 'action']),
 'alarm.event': ('alarm_event', [('equip', S), ('alarm_id', S), ('code', S), ('msg', S), ('sev', S), ('action', S)], ['alarm_id', 'action']),
 'shipment.dispatched': ('shipment', [('line', S), ('shipment', S), ('product', S), ('qty', F), ('unit', S), ('dest', S)], ['shipment']),
 'heartbeat': ('heartbeat', [('uptime_s', I), ('outbox_pending', I), ('rss_mb', F), ('load1', F)], ['uptime_s']),
}
RULES = {'kw': (0, 5000), 'soc': (0, 100), 'demand': (0, 20000), 'grid': (0, 20000), 'temp': (-50, 1500), 'done': (0, 1e9)}
STATES = {'RUN', 'IDLE', 'FAULT', 'CHANGEOVER'}
def ts_ms(s): return dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc).timestamp() * 1000 + float('0' + s[19:-1]) * 1000 if len(s) > 20 else dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc).timestamp() * 1000
def validate(ev):
    """→ (행 dict, None) 또는 (None, 사유)"""
    t = ev.get('type'); sp = SCHEMA.get(t)
    if not sp: return None, 'unknown type'
    name, cols, req = sp; p = ev.get('payload') or {}; row = {}
    try: row['ts'] = int(ts_ms(ev['ts']))
    except Exception: return None, 'bad ts'
    if row['ts'] > (time.time() + 3600) * 1000 or row['ts'] < 1577836800000: return None, 'ts out of range'
    row.update(site=ev['site_id'], epoch=str(ev['epoch']), seq=int(ev['seq']), event_id=ev['event_id'], recv_ts=int(float(ev.get('_recv', time.time())) * 1000))
    if t in ('process.state', 'production.counter', 'production.workorder', 'alarm.event', 'shipment.dispatched'): row['line' if t in ('production.counter', 'production.workorder', 'shipment.dispatched') else 'equip'] = ev.get('ref')
    if t == 'process.state': row['equip'] = ev.get('ref')
    if t == 'meter.reading' and 'equip' not in p: p = dict(p, equip=(ev.get('ref') or '')[2:])
    for k in req:
        if p.get(k) is None and row.get(k) is None: return None, 'missing ' + k
    for k, ty in cols:
        v = p.get(k, row.get(k))
        if v is not None:
            try: v = float(v) if ty == F else (int(v) if ty == I else str(v))
            except Exception: return None, 'bad type ' + k
            if k in RULES and not (RULES[k][0] <= v <= RULES[k][1]): return None, 'out of range ' + k
        row[k] = v
    if t == 'process.state' and row.get('state') not in STATES: return None, 'bad state'
    return (name, row), None
def table(name, rows):
    spec = next(v for v in SCHEMA.values() if v[0] == name); sch = pa.schema(BASE + spec[1])
    return pa.Table.from_pylist([{f.name: r.get(f.name) for f in sch} for r in rows], schema=sch)
def to_parquet(tb): b = io.BytesIO(); pq.write_table(tb, b, compression='snappy'); return b.getvalue()
def from_parquet(b): return pq.read_table(io.BytesIO(b))
# ---- bronze → silver ----
def run_silver(meta):
    wm = get_json('silver', '_state/watermark.json', {}); new = {}; rows = collections.defaultdict(list); quar = []; seen = set(); n_in = 0
    for name, size in list_blobs('bronze', ''):
        if not name.endswith('.ndjson'): continue
        off = wm.get(name, 0)
        if size <= off: continue
        data = get_bytes('bronze', name, 'bytes=%d-%d' % (off, min(size - 1, off + 64 * 1024 * 1024 - 1))) or b''; cut = data.rfind(b'\n') + 1      # 줄이 끝난 곳까지만
        data = data[:cut]; new[name] = off + cut
        for ln in data.decode('utf-8', 'replace').split('\n'):
            if not ln.strip(): continue
            n_in += 1
            try: ev = json.loads(ln)
            except Exception: quar.append({'raw': ln[:500], 'reason': 'bad json', 'bronze': name}); continue
            if ev.get('event_id') in seen: continue
            seen.add(ev.get('event_id')); r, why = validate(ev)
            if why: quar.append({'event_id': ev.get('event_id'), 'type': ev.get('type'), 'reason': why, 'bronze': name}); continue
            rows[r[0]].append(r[1])
    days = set(); wrote = {}
    for nm, rs in rows.items():
        by = collections.defaultdict(list)
        for r in rs: by[dt.datetime.fromtimestamp(r['ts'] / 1000, dt.timezone.utc).strftime('%Y-%m-%d')].append(r)
        for d, rr in by.items():
            put_block('silver', f'{nm}/date={d}/part-{RUN}.parquet', to_parquet(table(nm, rr))); days.add(d); wrote[nm] = wrote.get(nm, 0) + len(rr)
    if quar: put_block('silver', f'_quarantine/date={time.strftime("%Y-%m-%d", time.gmtime())}/part-{RUN}.ndjson', ('\n'.join(json.dumps(q, ensure_ascii=False) for q in quar) + '\n').encode())
    wm.update(new); put_block('silver', '_state/watermark.json', json.dumps(wm).encode(), 'application/json')
    meta['bronze'] = dict(lines=n_in, offsets=new); meta['silver'] = dict(rows=wrote, quarantined=len(quar)); return days
# ---- silver → gold ----
def read_silver(nm, day):
    tbs = [from_parquet(get_bytes('silver', b)) for b, _ in list_blobs('silver', f'{nm}/date={day}/') if b.endswith('.parquet')]
    if not tbs: return []
    tb = pa.concat_tables(tbs)
    for col in ('ts', 'recv_ts'):      # 시간대 정보가 없는 최소 컨테이너(tzdata 없음)에서도 읽히도록 정수(ms)로 바꾼다
        i = tb.schema.get_field_index(col)
        if i >= 0: tb = tb.set_column(i, col, tb.column(col).cast(pa.int64()))
    return tb.to_pylist()
def hour_of(ts_): return ts_.hour if hasattr(ts_, 'hour') else dt.datetime.fromtimestamp(ts_ / 1000, dt.timezone.utc).hour
def gold_day(day, meta):
    ef = read_silver('energy_flow', day); mr = read_silver('meter_reading', day); ps = read_silver('process_state', day); pw = read_silver('production_workorder', day); ae = read_silver('alarm_event', day); out = {}
    tab = collections.defaultdict(dict)
    # energy_hourly
    g = collections.defaultdict(list)
    for r in ef: g[(r['site'], hour_of(r['ts']))].append(r)
    en = []
    for (s, h), rs in sorted(g.items()):
        rs.sort(key=lambda x: x['ts']); n = len(rs); avg = lambda k: sum((x[k] or 0) for x in rs) / n; dtv = 5 / 3600.0
        en.append(dict(site=s, date=day, hour=h, samples=n, avg_demand_kw=avg('demand'), max_demand_kw=max(x['demand'] or 0 for x in rs), grid_kwh=sum(x['grid'] or 0 for x in rs) * dtv, solar_kwh=sum(x['solar'] or 0 for x in rs) * dtv, ppa_kwh=sum(x['ppa'] or 0 for x in rs) * dtv, co2_kg=sum(x['co2_kg_h'] or 0 for x in rs) * dtv, scope1_kg=sum(x['scope1'] or 0 for x in rs) * dtv, scope2_kg=sum(x['scope2'] or 0 for x in rs) * dtv, avg_soc=avg('soc')))
    out['energy_hourly'] = en
    # equipment_hourly
    g = collections.defaultdict(list)
    for r in ps: g[(r['site'], hour_of(r['ts']), r['equip'])].append(r)
    km = collections.defaultdict(list)
    for r in mr: km[(r['site'], hour_of(r['ts']), r['equip'])].append(r)
    eq = []
    for (s, h, e), rs in sorted(g.items()):
        m = km.get((s, h, e), []); eq.append(dict(site=s, date=day, hour=h, equip=e, samples=len(rs), run_ratio=sum(1 for x in rs if x['state'] == 'RUN') / len(rs), fault_ratio=sum(1 for x in rs if x['state'] == 'FAULT') / len(rs), avg_temp=sum(x['temp'] or 0 for x in rs) / len(rs), avg_kw=(sum(x['kw'] or 0 for x in m) / len(m)) if m else None, kwh=(max(x['kwh_total'] for x in m) - min(x['kwh_total'] for x in m)) if m else None))
    out['equipment_hourly'] = eq
    # production_hourly (완료된 작업지시)
    g = collections.defaultdict(list)
    for r in pw:
        if r['action'] == 'COMPLETED': g[(r['site'], hour_of(r['ts']), r['line'])].append(r)
    pr = [dict(site=s, date=day, hour=h, line=l, completed_wo=len(rs), qty=sum(x['qty'] or 0 for x in rs), scrap=sum(x['scrap'] or 0 for x in rs), scrap_rate=(sum(x['scrap'] or 0 for x in rs) / max(1.0, sum((x['qty'] or 0) + (x['scrap'] or 0) for x in rs)))) for (s, h, l), rs in sorted(g.items())]
    out['production_hourly'] = pr
    # alarm_daily
    g = collections.defaultdict(lambda: [0, 0])
    for r in ae: g[(r['site'], r['sev'])][0 if r['action'] == 'RAISED' else 1] += 1
    out['alarm_daily'] = [dict(site=s, date=day, sev=v, raised=a[0], cleared=a[1]) for (s, v), a in sorted(g.items())]
    for nm, rs in out.items():
        if rs: put_block('gold', f'{nm}/date={day}/data.parquet', to_parquet(pa.Table.from_pylist(rs)))
    meta.setdefault('gold', {})[day] = {k: len(v) for k, v in out.items()}; return out
def gold_api(day_tables, meta):
    """수신 앱이 읽는 사이트별 요약(최근 48시간). 오늘·어제 gold에서 만든다."""
    sites = {}
    for day, tb in day_tables.items():
        for r in tb.get('energy_hourly', []): sites.setdefault(r['site'], {}).setdefault('energy', []).append(r)
        for r in tb.get('equipment_hourly', []): sites.setdefault(r['site'], {}).setdefault('equip', []).append(r)
        for r in tb.get('production_hourly', []): sites.setdefault(r['site'], {}).setdefault('prod', []).append(r)
        for r in tb.get('alarm_daily', []): sites.setdefault(r['site'], {}).setdefault('alarm', []).append(r)
    for s, d in sites.items():
        en = sorted(d.get('energy', []), key=lambda r: (r['date'], r['hour']))[-48:]; eqs = collections.defaultdict(lambda: [0, 0.0, 0.0])
        for r in d.get('equip', []): a = eqs[r['equip']]; a[0] += 1; a[1] += r['run_ratio']; a[2] += r['kwh'] or 0
        doc = dict(site=s, generated=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=RUN, layers=dict(bronze='bronze/%s/<date>.ndjson' % s, silver='silver/<type>/date=*/part-*.parquet', gold='gold/<table>/date=*/data.parquet'),
                   energy_hourly=[{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in en], totals=dict(grid_kwh=round(sum(r['grid_kwh'] for r in en), 1), solar_kwh=round(sum(r['solar_kwh'] for r in en), 1), co2_kg=round(sum(r['co2_kg'] for r in en), 1)),
                   equipment=[dict(equip=e, run_ratio=round(a[1] / a[0], 3), kwh=round(a[2], 1)) for e, a in sorted(eqs.items())], production=sorted(d.get('prod', []), key=lambda r: (r['date'], r['hour']))[-24:], alarms=d.get('alarm', []))
        put_block('gold', f'api/{s}/summary.json', json.dumps(doc, ensure_ascii=False, default=str).encode(), 'application/json')
    meta['gold_api'] = sorted(sites)
def main():
    meta = dict(run=RUN, started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    if not lock(): print('SKIP: 다른 실행이 진행 중'); return 0
    try:
        days = run_silver(meta); tabs = {}
        today = time.strftime('%Y-%m-%d', time.gmtime()); yest = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 86400))
        for d in sorted(days | {today}): tabs[d] = gold_day(d, meta)
        if yest not in tabs: tabs[yest] = gold_day(yest, meta)
        gold_api(tabs, meta); meta['seconds'] = round(time.time() - T0, 1); meta['ok'] = True
        put_block('gold', f'_meta/run-{RUN}.json', json.dumps(meta, ensure_ascii=False, default=str).encode(), 'application/json'); print('OK', json.dumps({k: meta[k] for k in ('silver', 'seconds')}, ensure_ascii=False, default=str)); return 0
    except Exception as e:
        print('FAIL', type(e).__name__, str(e)[:300]); meta['ok'] = False; meta['error'] = str(e)[:300]
        try: put_block('gold', f'_meta/run-{RUN}.json', json.dumps(meta, default=str).encode(), 'application/json')
        except Exception: pass
        return 1
    finally: unlock()
if __name__ == '__main__': sys.exit(main())
