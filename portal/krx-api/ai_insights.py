#!/usr/bin/env python3
"""데이터 흐름 화면의 'AI 분석' 단계: 사이트 Gold 집계 값을 읽어 Foundry(gpt-6.1-sol, 신규 fdry-cems-prd-krc-02)가 인사이트를 작성한다.
- 모델은 전달한 FACTS의 숫자만 쓸 수 있고, 근거 없는 숫자가 나오면 한 번 재작성 후에도 틀리면 실패로 응답한다(규칙 기반 대체·다른 모델 대체 없음).
- 인증: 컨테이너 앱 관리 ID(키 없음). 호출 대상은 사설 연결(PE)만."""
import os, json, re, time, hashlib, urllib.request, urllib.parse, urllib.error, threading
PROJECT = os.environ.get('AI_PROJECT', 'https://fdry-cems-prd-krc-02.services.ai.azure.com/api/projects/proj-cems-prd-krc-02')
MODEL = os.environ.get('AI_MODEL', 'gpt-6-1-sol')
BASES = {'KR-01': 'https://ca-cems-prd-krc-central-ingest.calmwave-0ea519ed.koreacentral.azurecontainerapps.io',
         'JP-01': 'https://ca-cems-prd-jpe-central-ingest.nicebeach-02cb1974.japaneast.azurecontainerapps.io',
         'SG-01': 'https://ca-cems-prd-sea-central-ingest.mangodune-813514ad.southeastasia.azurecontainerapps.io'}
OP = urllib.request.build_opener(urllib.request.ProxyHandler({})); CACHE = {}; LOCK = threading.Lock()
def req(url, tok=None, payload=None, timeout=60):
    h = {'Accept': 'application/json'}
    if tok: h['Authorization'] = 'Bearer ' + tok
    if payload is not None: h['Content-Type'] = 'application/json'
    try: return json.loads(OP.open(urllib.request.Request(url, data=payload, headers=h), timeout=timeout).read())
    except urllib.error.HTTPError as e: raise RuntimeError(f'HTTP {e.code}: {e.read()[:300]!r}')
def token():
    q = os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode({'resource': 'https://ai.azure.com', 'api-version': '2019-08-01'})
    return json.loads(OP.open(urllib.request.Request(q, headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}), timeout=20).read())['access_token']
def respond(tok, prompt, max_tokens=4000):
    pl = {'model': MODEL, 'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}], 'max_output_tokens': max_tokens, 'store': False, 'stream': False, 'tools': [], 'tool_choice': 'none'}
    r = req(PROJECT + '/openai/v1/responses', tok, json.dumps(pl, ensure_ascii=False).encode(), timeout=120)
    return ''.join(c.get('text', '') for o in r.get('output', []) if o.get('type') == 'message' for c in o.get('content', [])), r
def ping():
    t0 = time.time(); txt, r = respond(token(), '한국어로 "응답 확인"이라고만 답하세요.', 200)
    return {'model_deployment': MODEL, 'response_model': r.get('model'), 'text': txt.strip()[:80], 'status': r.get('status'), 'latency_ms': int((time.time() - t0) * 1000), 'usage': r.get('usage')}
def facts_of(site, gd):
    en = gd.get('energy_hourly') or []
    if not en: raise RuntimeError('gold has no hourly rows yet')
    peak = max(en, key=lambda r: r['avg_demand_kw']); dem = sum(r['avg_demand_kw'] for r in en); s1 = sum(r['scope1_kg'] for r in en); s2 = sum(r['scope2_kg'] for r in en); tot = gd.get('totals') or {}
    f = {'site': site, 'hours': len(en), 'peak_hour_utc': f"{peak['date']} {int(peak['hour']):02d}", 'peak_demand_kw': round(peak['avg_demand_kw']), 'avg_demand_kw': round(dem / len(en)),
         'solar_kwh': round(tot.get('solar_kwh', 0)), 'solar_share_pct': round(tot.get('solar_kwh', 0) / max(1, dem) * 100, 1), 'grid_kwh': round(tot.get('grid_kwh', 0)),
         'co2_kg': round(s1 + s2), 'scope1_kg': round(s1), 'scope2_kg': round(s2), 'scope1_share_pct': round(s1 / max(1, s1 + s2) * 100)}
    eq = sorted(gd.get('equipment') or [], key=lambda e: e['run_ratio'])
    if eq: f['lowest_run_equipment'] = eq[0]['equip']; f['lowest_run_ratio_pct'] = round(eq[0]['run_ratio'] * 100)
    return f
def nums(t): return {n.replace(',', '').rstrip('.') for n in re.findall(r'\d[\d,]*\.?\d*', t)}
STYLE = ('당신은 철강·화학 공장의 탄소·에너지 비용 분석가입니다. 아래 FACTS(시간별 Gold 집계)만 근거로 한국어 존댓말 인사이트 4개를 작성합니다. '
         '규칙: 1) FACTS에 없는 숫자·사실·인과를 만들지 않습니다(숫자는 FACTS 값을 그대로 인용). 2) 각 항목은 title(12자 이내), body(2문장 이내, 조치 제안 포함), basis(근거 FACTS 키 목록)입니다. '
         '3) 합성 모의 자료이므로 확정 표현을 피하고 "추정/후보"로 씁니다. 4) 출력은 JSON 객체 {"insights":[...]} 하나만, 설명·코드블록 금지.')
def insights(site):
    if site not in BASES: raise RuntimeError('unknown site')
    with LOCK:
        c = CACHE.get(site)
        if c and time.time() - c['t'] < 600: return c['v']
    gd = req(BASES[site] + f'/v1/sites/{site}/gold', timeout=20)
    if gd.get('error'): raise RuntimeError('gold not ready: ' + str(gd['error']))
    f = facts_of(site, gd); tok = token(); allowed = nums(json.dumps(f, ensure_ascii=False)); fb = ''; t0 = time.time(); rounds = []
    for att in range(2):
        prompt = STYLE + '\n' + (fb + '\n' if fb else '') + 'FACTS=' + json.dumps(f, ensure_ascii=False)
        txt, r = respond(tok, prompt); m = re.search(r'\{.*\}', txt, re.S)
        try: items = json.loads(m.group(0))['insights']
        except Exception: rounds.append('parse-fail'); fb = '직전 출력이 JSON이 아니었습니다. 지시 형식만 출력하세요.'; continue
        bad = sorted(n for n in nums(json.dumps(items, ensure_ascii=False)) if n not in allowed and len(n) > 1)
        rounds.append({'bad_numbers': bad})
        if not bad: break
        fb = '직전 출력에 FACTS에 없는 숫자가 있습니다: ' + ', '.join(bad) + '. FACTS의 값만 쓰세요.'
    else: raise RuntimeError('AI output failed numeric grounding check: ' + json.dumps(rounds, ensure_ascii=False)[:200])
    v = {'site': site, 'generated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'deployment': MODEL, 'response_model': r.get('model'), 'latency_ms': int((time.time() - t0) * 1000),
         'facts': f, 'insights': items[:6], 'receipt': {'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'response_id': r.get('id'), 'rounds': rounds, 'usage': r.get('usage')}}
    with LOCK: CACHE[site] = {'t': time.time(), 'v': v}
    return v
