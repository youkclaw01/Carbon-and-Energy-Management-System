#!/usr/bin/env python3
"""topo-api — Azure 리소스 구성도(읽기 전용). Azure Resource Graph로 구독의 리소스·상태를 읽어 노드/관계(온톨로지 그래프)로 돌려주고,
같은 컨테이너가 구성도 웹페이지(static/index.html)를 제공한다. 쓰기 호출 없음(Reader 역할만 필요).
env: SUBSCRIPTIONS(쉼표 구분), AZURE_CLIENT_ID(UAMI), APPROVAL_URL(로그인 토큰 확인용 approval-api 주소), CACHE_TTL(초, 기본 60), PORT. 시험: TOPO_FAKE=<fixture.json>.
인가: /api/graph는 승인 서비스의 /v1/auth/me로 토큰을 확인하고 관리자(admin) 권한이 있을 때만 응답한다. 페이지 파일 자체에는 데이터가 없다."""
try:   # Application Insights 텔레메트리(연결 문자열이 없으면 아무 것도 하지 않음)
    import aitel; aitel.install()
except Exception: pass
import os, re, sys, json, time, hashlib, threading, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
VERSION = 'topo-api/1.11'; HERE = os.path.dirname(os.path.abspath(__file__))
STATS = dict(requests=0, errors=0, started=time.time(), last_err=None, graphs=0, step='idle', ms={})
SUBS = [s for s in os.environ.get('SUBSCRIPTIONS', '00000000-0000-0000-0000-000000000000').split(',') if s]
TTL = int(os.environ.get('CACHE_TTL', '60'))
QUERY = ("resources | extend st = coalesce(tostring(properties.extended.instanceView.powerState.code), tostring(properties.runningStatus), "
         "tostring(properties.operationalState), tostring(properties.provisioningState)) "
         "| project id, name, type, location, resourceGroup, subscriptionId, kind, sku = tostring(sku.name), st, tags, props = properties")
RG_QUERY = "resourcecontainers | where type == 'microsoft.resources/subscriptions/resourcegroups' | project id, name, location, subscriptionId"
CATS = [('compute', ('microsoft.compute', 'microsoft.app', 'microsoft.containerservice', 'microsoft.web', 'microsoft.containerinstance', 'microsoft.automation')),
        ('network', ('microsoft.network', 'microsoft.cdn')),
        ('data', ('microsoft.sql', 'microsoft.storage', 'microsoft.servicebus', 'microsoft.eventhub', 'microsoft.devices', 'microsoft.dbfor', 'microsoft.documentdb', 'microsoft.search')),
        ('security', ('microsoft.keyvault', 'microsoft.managedidentity', 'microsoft.authorization', 'microsoft.security')),
        ('ai', ('microsoft.cognitiveservices', 'microsoft.machinelearning')),
        ('monitor', ('microsoft.insights', 'microsoft.operationalinsights', 'microsoft.alertsmanagement', 'microsoft.monitor', 'microsoft.portal')),
        ('mgmt', ('microsoft.resources', 'microsoft.containerregistry', 'microsoft.communication', 'microsoft.cost', 'microsoft.consumption'))]
ID_RE = re.compile(r'/subscriptions/[0-9a-f\-]{36}/resourcegroups/[a-z0-9._\-()]+/providers/[a-z0-9.]+(?:/[a-z0-9._\-()@]+)+')

def category(t):
    t = (t or '').lower()
    for c, pre in CATS:
        if t.startswith(pre): return c
    return 'other'
SHORT = dict(virtualmachines='VM', networkinterfaces='NIC', virtualnetworks='VN', containerapps='CA', managedenvironments='CE', storageaccounts='ST', servers='SQL', databases='DB',
             vaults='KV', userassignedidentities='ID', publicipaddresses='IP', networksecuritygroups='NSG', routetables='RT', loadbalancers='LB', applicationgateways='AGW',
             azurefirewalls='FW', firewallpolicies='FWP', privateendpoints='PE', privatednszones='PDZ', dnszones='DNS', natgateways='NAT', bastionhosts='BAS', virtualwans='VWAN',
             virtualhubs='VHUB', vpngateways='VPN', namespaces='NS', registries='ACR', accounts='AI', workspaces='LAW', components='AI', actiongroups='AG', metricalerts='MA',
             activitylogalerts='ALR', scheduledqueryrules='SQR', automationaccounts='AA', runbooks='RB', disks='DSK', extensions='EXT', iothubs='IOT', searchservices='SRCH',
             frontdoors='AFD', profiles='AFD', budgets='BUD', jobs='JOB', locks='LCK', sites='WEB', serverfarms='ASP', emailservices='ACS', communicationservices='ACS', domains='DOM',
             privatelinkservices='PLS', ipgroups='IPG', networkwatchers='NW', connections='CN', virtualnetworkgateways='VNG', localnetworkgateways='LNG', snapshots='SNP', images='IMG')
def short(t):
    last = (t or '').split('/')[-1].lower()
    return SHORT.get(last) or (last[:3].upper() if last else '?')
def state_class(st):
    s = (st or '').lower().replace('powerstate/', '')
    if not s: return 'none'
    if s in ('succeeded', 'running', 'available', 'online', 'active', 'ready', 'provisioned', 'enabled', 'approved', 'started'): return 'ok'
    if any(k in s for k in ('updat', 'creat', 'start', 'provision', 'pending', 'scal', 'deleting', 'stopping', 'deallocating')): return 'warn'
    if any(k in s for k in ('fail', 'error', 'stopped', 'deallocated', 'disabled', 'cancel', 'unavailable', 'degrad', 'rejected')): return 'bad'
    return 'none'
def resolve(found, known):
    parts = found.split('/')
    for i in range(len(parts), 7, -1):
        c = '/'.join(parts[:i])
        if c in known: return c
    return None
SUBNET_RE = re.compile(r'/subnets/([a-z0-9._\-]+)')
PLACE_TYPES = ('microsoft.network/networkinterfaces', 'microsoft.network/privateendpoints', 'microsoft.app/managedenvironments', 'microsoft.network/applicationgateways',
               'microsoft.network/azurefirewalls', 'microsoft.network/bastionhosts', 'microsoft.network/virtualnetworkgateways', 'microsoft.web/serverfarms', 'microsoft.containerinstance/containergroups')
def extract_edges(rows):
    """속성 안의 다른 리소스 ID를 찾아 관계로 만든다(하위 ID는 가장 가까운 상위 리소스로 환원, 서브넷 이름은 sub로 보존). 알 수 없는 대상은 만들지 않는다.
    종류(k): net=서브넷에 놓임, pe=프라이빗 엔드포인트→대상, peer=VNet 피어링, ref=그 밖의 ID 참조."""
    known = {r['id'].lower(): r['id'] for r in rows}; typ = {r['id'].lower(): (r.get('type') or '').lower() for r in rows}; seen = {}; out = []
    for r in rows:
        me = r['id'].lower(); text = json.dumps(r.get('props') or {}, ensure_ascii=False).lower()
        for m in ID_RE.findall(text):
            t = resolve(m, known)
            if not t or t == me or me.startswith(t + '/') or t.startswith(me + '/'): continue
            sub = None
            if typ[t] == 'microsoft.network/virtualnetworks':
                sm = SUBNET_RE.search(m[len(t):]); sub = sm.group(1) if sm else None
            if sub and typ[me] in ('microsoft.network/virtualnetworks',): sub = None
            k = 'ref'
            if sub and typ[me] in PLACE_TYPES: k = 'net'
            elif typ[me] == 'microsoft.network/virtualnetworks' and typ[t] == 'microsoft.network/virtualnetworks': k = 'peer'
            elif typ[me] == 'microsoft.network/privateendpoints': k = 'pe'
            key = (me, t, k)
            if key in seen:
                continue
            seen[key] = 1; e = dict(s=known[me], t=known[t], k=k)
            if sub: e['sub'] = sub
            out.append(e)
    return out
DEP_SRC = ('microsoft.app/containerapps', 'microsoft.app/jobs', 'microsoft.web/sites', 'microsoft.compute/virtualmachines')
DEP_DST = ('microsoft.sql/', 'microsoft.storage/', 'microsoft.servicebus/', 'microsoft.keyvault/', 'microsoft.containerregistry/', 'microsoft.search/', 'microsoft.cognitiveservices/', 'microsoft.devices/', 'microsoft.eventhub/', 'microsoft.communication/', 'microsoft.dbfor', 'microsoft.operationalinsights/', 'microsoft.insights/components', 'microsoft.app/containerapps')
def name_deps(rows, have):
    """앱 환경 변수 등 속성 문자열에 다른 서비스 이름(예: 스토리지 계정·SQL 서버·서비스 버스)이 들어 있으면 호출 의존으로 본다(데이터 흐름 후보, 실제 호출 증거는 아님)."""
    names = {}
    for r in rows:
        t = (r.get('type') or '').lower(); n = (r.get('name') or '').lower()
        if t.startswith(DEP_DST) and len(n) >= 8 and t.count('/') == 1: names[n] = r['id']
    out = []
    for r in rows:
        if (r.get('type') or '').lower() not in DEP_SRC: continue
        text = json.dumps((r.get('props') or {}).get('template') or r.get('props') or {}, ensure_ascii=False).lower()
        for n, tid in names.items():
            if tid != r['id'] and n in text and (r['id'].lower(), tid.lower()) not in have: out.append(dict(s=r['id'], t=tid, k='dep'))
    return out
def lb_edges(rows):
    """로드밸런서·게이트웨이의 백엔드 연결(k='lb', 방향=앞단→뒷단). 속성에 리소스 ID가 없어 extract_edges가 못 잇는 관계를 구조로 해석한다.
    ① ACA 환경 내부 로드밸런서(capp-svc-lb): 환경의 관리 리소스 그룹(infrastructureResourceGroup)에 있다 → 그 환경, 그리고 환경 안에서 ingress.external=true인 앱.
    ② 애플리케이션 게이트웨이: 요청 라우팅 규칙의 리스너(호스트명)→백엔드 풀 주소(FQDN)→같은 FQDN의 컨테이너 앱, 그 앱이 속한 환경의 내부 LB. 해석하지 못한 풀 주소는 연결을 만들지 않는다."""
    T = lambda r: (r.get('type') or '').lower()
    envs = {}; apps = []; fq = {}; out = {}
    for r in rows:
        if T(r) == 'microsoft.app/managedenvironments': envs[r['id'].lower()] = r
        elif T(r) == 'microsoft.app/containerapps':
            p = r.get('props') or {}; ing = (p.get('configuration') or {}).get('ingress') or {}; env = (p.get('environmentId') or p.get('managedEnvironmentId') or '').lower()
            apps.append((r, ing, env))
            if ing.get('fqdn'): fq[str(ing['fqdn']).lower()] = (r, ing, env)
    infra = {((e.get('props') or {}).get('infrastructureResourceGroup') or '').lower(): e for e in envs.values() if (e.get('props') or {}).get('infrastructureResourceGroup')}
    lb_of_env = {}
    for r in rows:
        if T(r) == 'microsoft.network/loadbalancers':
            e = infra.get((r.get('resourceGroup') or '').lower())
            if e: lb_of_env[e['id'].lower()] = r
    def add(a, b, note):
        k = (a['id'], b['id'])
        if k in out: out[k]['note'] = (out[k]['note'] + ' / ' + note)[:300] if note not in out[k]['note'] else out[k]['note']
        else: out[k] = dict(s=a['id'], t=b['id'], k='lb', note=note[:300])
    for env_id, lb in lb_of_env.items():
        env = envs[env_id]; ip = (env.get('props') or {}).get('staticIp') or ''
        add(lb, env, '환경 내부 로드밸런서(프런트 IP %s)가 이 컨테이너 앱 환경으로 들어오는 요청을 받는다' % ip)
        for r, ing, e in apps:
            if e == env_id and ing.get('external') is True: add(lb, r, 'ACA ingress 외부 수신(환경 내부 LB 경유) · 대상 포트 %s · %s' % (ing.get('targetPort', '–'), ing.get('fqdn', '')))
    for g in rows:
        if T(g) != 'microsoft.network/applicationgateways': continue
        p = g.get('props') or {}; name = lambda x: (x or {}).get('id', '').split('/')[-1].lower()
        pools = {(x.get('name') or '').lower(): x for x in p.get('backendAddressPools') or []}; ls = {(x.get('name') or '').lower(): x for x in p.get('httpListeners') or []}
        st = {(x.get('name') or '').lower(): x for x in p.get('backendHttpSettingsCollection') or []}; pb = {(x.get('name') or '').lower(): x for x in p.get('probes') or []}
        maps = {(x.get('name') or '').lower(): x for x in p.get('urlPathMaps') or []}; use = {}   # 풀 이름 → {리스너 호스트, 설정}
        def mark(pool, lname, setn, path=''):
            if not pool: return
            u = use.setdefault(pool, dict(hosts=[], set=set(), path=set()))
            lp = (ls.get(lname) or {}).get('properties') or {}; hs = lp.get('hostNames') or ([lp['hostName']] if lp.get('hostName') else [])
            for h in hs:
                if h not in u['hosts']: u['hosts'].append(h)
            if setn: u['set'].add(setn)
            if path: u['path'].add(path)
        for ru in p.get('requestRoutingRules') or []:
            rp = ru.get('properties') or {}; ln = name(rp.get('httpListener'))
            if rp.get('backendAddressPool'): mark(name(rp['backendAddressPool']), ln, name(rp.get('backendHttpSettings')))
            pm = maps.get(name(rp.get('urlPathMap'))) or {}
            if pm:
                pp = pm.get('properties') or {}; mark(name(pp.get('defaultBackendAddressPool')), ln, name(pp.get('defaultBackendHttpSettings')))
                for pr in pp.get('pathRules') or []:
                    q = pr.get('properties') or {}; mark(name(q.get('backendAddressPool')), ln, name(q.get('backendHttpSettings')), ','.join(q.get('paths') or []))
        for pn, u in use.items():
            pool = pools.get(pn)
            if not pool: continue
            sn = sorted(u['set'])[0] if u['set'] else ''; sp = (st.get(sn) or {}).get('properties') or {}; probe = ((pb.get(name(sp.get('probe'))) or {}).get('properties') or {}).get('path') or ''
            note = '리스너 %s → 백엔드 풀 %s%s%s' % (', '.join(u['hosts']) or '–', pool.get('name'), (' · %s :%s' % (sp.get('protocol'), sp.get('port'))) if sp else '', (' · 프로브 ' + probe) if probe else '')
            for b in (pool.get('properties') or {}).get('backendAddresses') or []:
                f = str(b.get('fqdn') or '').lower(); hit = fq.get(f)
                if not hit: continue
                r, ing, env = hit; add(g, r, note + ' · 풀 주소 ' + f)
                lb = lb_of_env.get(env)
                if lb: add(g, lb, note + ' → 앱 환경의 내부 LB로 전달')
    return list(out.values())
def unit_of(r):
    tg = r.get('tags') or {}
    if tg.get('unit'): return str(tg['unit'])
    m = re.match(r'^(?:ca|caj|id|log|appi)-ama-(?:prd|dev)-(?:krc|jpe|sea)-(.+?)(?:-\d+)?$', (r.get('name') or '').lower())
    return m.group(1) if m else ''
SERVICE_RULES = [('웹·포털', r'(web-v2|portal-bff|plant-web|plant-bff|krx-api|^web$)'), ('중앙 수신·조회', r'(central|cingest|cquery)'), ('수집·정규화', r'(ingest|normalizer|medallion|dbinit)'),
                 ('탄소 산정', r'(calc)'), ('시뮬레이션·계획', r'(plan|sim-?prov)'), ('조달·포지션', r'(proc)'), ('승인·허가', r'(approval|notif|permit|release)'), ('제한 실행', r'(exec)'),
                 ('증빙', r'(evid)'), ('수출·공시', r'(export|expsend|fp|footprint)'), ('워크플로', r'(workflow|wf)'), ('AI 에이전트', r'(agent|honcho|searchinit)')]
SVC_TYPES = ('microsoft.app/containerapps', 'microsoft.app/jobs', 'microsoft.managedidentity/userassignedidentities')
def service_of(t, name, unit):
    if t not in SVC_TYPES: return ''
    key = (unit or '').lower() or re.sub(r'^(?:ca|caj|id)-ama-(?:prd|dev)-(?:krc|jpe|sea)-', '', (name or '').lower())
    key2 = re.sub(r'^(?:ca|caj|id)-ama-(?:prd|dev)-(?:krc|jpe|sea)-', '', (name or '').lower())
    for label, rx in SERVICE_RULES:
        if re.search(rx, key2) or re.search(rx, key): return label
    return ''
def build_graph(rows, rgs):
    edges = extract_edges(rows); have = {(e['s'].lower(), e['t'].lower()) for e in edges}; edges += name_deps(rows, have); edges += lb_edges(rows)
    nodes = []
    for r in rows:
        p = r.get('props') or {}; t = (r.get('type') or '').lower()
        n = dict(id=r['id'], name=r['name'], type=t, short=short(r.get('type')), cat=category(r.get('type')), location=(r.get('location') or 'global').lower(), rg=(r.get('resourceGroup') or '').lower(),
                 state=r.get('st') or '', sc=state_class(r.get('st')), kind=r.get('kind') or '', sku=r.get('sku') or '', tags=r.get('tags') or {}, unit=unit_of(r))
        n['svc'] = service_of(t, r['name'], n['unit'])
        if t == 'microsoft.app/containerapps': n['ext'] = bool(((p.get('configuration') or {}).get('ingress') or {}).get('external'))
        if t == 'microsoft.network/virtualnetworks':
            n['cidr'] = ((p.get('addressSpace') or {}).get('addressPrefixes')) or []
            n['subnets'] = [dict(name=(x.get('name') or '').lower(), prefix=(x.get('properties') or {}).get('addressPrefix') or ','.join((x.get('properties') or {}).get('addressPrefixes') or []),
                                 nsg=((((x.get('properties') or {}).get('networkSecurityGroup') or {}).get('id')) or '').split('/')[-1], rt=((((x.get('properties') or {}).get('routeTable') or {}).get('id')) or '').split('/')[-1]) for x in (p.get('subnets') or [])]
        nodes.append(n)
    byid = {n['id']: n for n in nodes}
    for e in edges:   # 서브넷에 놓인 리소스: 직접 연결(net)을 우선, VM은 NIC의 서브넷을 따른다
        if e['k'] == 'net' and e['s'] in byid and 'sub' not in byid[e['s']]: byid[e['s']].update(vnet=e['t'], sub=e['sub'])
    for e in edges:
        if e['k'] == 'ref' and e['s'] in byid and byid[e['s']]['type'] == 'microsoft.compute/virtualmachines' and e['t'] in byid and 'sub' in byid[e['t']] and 'sub' not in byid[e['s']]:
            byid[e['s']].update(vnet=byid[e['t']]['vnet'], sub=byid[e['t']]['sub'])
    for e in edges:   # 컨테이너 앱·잡은 소속 환경(managedEnvironment)의 서브넷에 놓인 것으로 본다
        sn = byid.get(e['s']); tn = byid.get(e['t'])
        if e['k'] == 'ref' and sn and tn and sn['type'] in ('microsoft.app/containerapps', 'microsoft.app/jobs') and tn['type'] == 'microsoft.app/managedenvironments' and tn.get('sub') and 'sub' not in sn:
            sn.update(vnet=tn['vnet'], sub=tn['sub'], via='env')
    groups = {}
    for g in rgs: groups[g['name'].lower()] = dict(name=g['name'], location=(g.get('location') or '').lower())
    for n in nodes:
        groups.setdefault(n['rg'], dict(name=n['rg'], location=n['location']))
    return dict(generatedAt=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), subscriptions=SUBS, nodes=nodes, groups=sorted(groups.values(), key=lambda g: g['name']),
                edges=edges, counts=dict(nodes=len(nodes), groups=len(groups)))

def arm_token():
    STATS['step'] = 'token'
    q = dict([('api-version', '2019-08-01'), ('resource', 'https://management.azure.com/')] + ([('client_id', os.environ['AZURE_CLIENT_ID'])] if os.environ.get('AZURE_CLIENT_ID') else []))
    r = urllib.request.Request(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), headers={'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']})
    t0 = time.time(); tok = json.loads(urllib.request.urlopen(r, timeout=10).read())['access_token']; STATS['ms']['token'] = int((time.time() - t0) * 1000); return tok
def arg(query, tok):
    STATS['step'] = 'arg'; rows, skip = [], None; t0 = time.time()
    for _ in range(40):
        body = dict(subscriptions=SUBS, query=query, options=dict(resultFormat='objectArray', **{'$top': 1000}))
        if skip: body['options']['$skipToken'] = skip
        for attempt in range(3):
            try:
                r = urllib.request.Request('https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2022-10-01', data=json.dumps(body).encode(),
                                           headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, method='POST')
                d = json.loads(urllib.request.urlopen(r, timeout=25).read()); STATS['ms']['arg'] = int((time.time() - t0) * 1000); break
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and attempt < 2: time.sleep(2 ** attempt); continue
                raise
        rows += d.get('data') or []; skip = d.get('$skipToken')
        if not skip: return rows
    raise RuntimeError('ARG 페이지가 너무 많습니다(상한 40쪽)')
OBS_WINDOW = os.environ.get('OBS_WINDOW', 'P1D')
OBS_KQL = "AppDependencies | summarize calls=count(), fails=countif(Success == false), avgMs=round(avg(DurationMs), 0) by Caller=AppRoleName, Target=Target, Type=DependencyType"
OBS_APPS_KQL = "AppRequests | summarize calls=count(), fails=countif(Success == false), avgMs=round(avg(DurationMs), 0), instances=dcount(AppRoleInstance) by App=AppRoleName"
def law_query(tok, kql=None):
    """Application Insights(작업 영역 기반)의 AppDependencies를 ARM 질의 API로 읽는다(작업 영역 Log Analytics Reader 필요, 읽기 전용)."""
    STATS['step'] = 'law'; t0 = time.time()
    r = urllib.request.Request('https://management.azure.com' + os.environ['LAW_ID'] + '/query?api-version=2017-10-01', data=json.dumps(dict(query=kql or OBS_KQL, timespan=OBS_WINDOW)).encode(),
                               headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, method='POST')
    d = json.loads(urllib.request.urlopen(r, timeout=25).read()); STATS['ms']['law'] = int((time.time() - t0) * 1000)
    t = (d.get('tables') or [{}])[0]; cols = [c['name'] for c in t.get('columns', [])]
    return [dict(zip(cols, row)) for row in t.get('rows', [])]
def merge_observed(g, rows, appstats=None):
    """텔레메트리로 관측된 호출을 'obs' 관계로 합친다. 호출자=앱 역할 이름(컨테이너 앱 이름), 대상=호스트의 첫 라벨이 리소스 이름과 같을 때만 연결(모르는 대상은 만들지 않음)."""
    apps = {n['name'].lower(): n['id'] for n in g['nodes'] if n['type'] == 'microsoft.app/containerapps'}; names = {}
    for n in g['nodes']:
        if n['type'].count('/') == 1: names.setdefault(n['name'].lower(), n['id'])
    agg = {}; miss = {}
    for r in rows:
        src = apps.get(str(r.get('Caller') or '').lower()); host = str(r.get('Target') or '').lower().split(':')[0]; label = host.split('.')[0]
        tgt = names.get(label)
        if not src or not tgt or src == tgt:
            if src and not tgt: miss[host] = miss.get(host, 0) + int(r.get('calls') or 0)
            continue
        a = agg.setdefault((src, tgt), dict(s=src, t=tgt, k='obs', calls=0, fails=0, _ms=0.0))
        c = int(r.get('calls') or 0); a['calls'] += c; a['fails'] += int(r.get('fails') or 0); a['_ms'] += float(r.get('avgMs') or 0) * c
    for a in agg.values():
        a['avgMs'] = int(a.pop('_ms') / a['calls']) if a['calls'] else 0; g['edges'].append(a)
    raw = [dict(Caller=str(r.get('Caller') or ''), Target=str(r.get('Target') or ''), Type=str(r.get('Type') or ''), calls=int(r.get('calls') or 0), fails=int(r.get('fails') or 0), avgMs=int(float(r.get('avgMs') or 0))) for r in rows][:400]
    ap = {str(a.get('App') or ''): dict(calls=int(a.get('calls') or 0), fails=int(a.get('fails') or 0), avgMs=int(float(a.get('avgMs') or 0)), instances=int(a.get('instances') or 0)) for a in (appstats or [])}
    g['observed'] = dict(table=raw, apps=ap, status='ok' if agg else 'empty', window=OBS_WINDOW, rows=len(rows), matched=len(agg), unmatched=sorted(miss.items(), key=lambda x: -x[1])[:5], at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    return g
CACHE = dict(at=0, data=None); LOCK = threading.Lock()
def get_graph(force=False):
    with LOCK:
        if not force and CACHE['data'] and time.time() - CACHE['at'] < TTL: return CACHE['data']
        if os.environ.get('TOPO_FAKE'):
            fx = json.load(open(os.environ['TOPO_FAKE'], encoding='utf-8')); g = build_graph(fx['rows'], fx.get('rgs', []))
            g = merge_observed(g, fx['obs'], fx.get('apps')) if fx.get('obs') is not None else dict(g, observed=dict(status='disabled'))
        else:
            tok = arm_token(); g = build_graph(arg(QUERY, tok), arg(RG_QUERY, tok))
            if os.environ.get('LAW_ID'):
                try: g = merge_observed(g, law_query(tok), law_query(tok, OBS_APPS_KQL))
                except Exception as e: g['observed'] = dict(status='unavailable', reason=(type(e).__name__ + (' %s' % e.code if hasattr(e, 'code') else ''))[:60]); STATS['last_err'] = 'law: ' + g['observed']['reason']
            else: g['observed'] = dict(status='disabled')
        STATS['graphs'] += 1; CACHE.update(at=time.time(), data=g); return g
AUTHC = {}
def authorized(headers):
    a = headers.get('Authorization') or ''
    if not a.startswith('Bearer ') or len(a) < 20: return 401
    k = hashlib.sha256(a.encode()).hexdigest()
    hit = AUTHC.get(k)
    if hit and time.time() - hit[0] < 30: return hit[1]
    if os.environ.get('TOPO_FAKE_AUTH'): code = 200 if a.endswith(os.environ['TOPO_FAKE_AUTH']) else 403
    else:
        try:
            STATS['step'] = 'auth'; t0 = time.time(); me = json.loads(urllib.request.urlopen(urllib.request.Request(os.environ['APPROVAL_URL'].rstrip('/') + '/v1/auth/me', headers={'Authorization': a}), timeout=8).read()); STATS['ms']['auth'] = int((time.time() - t0) * 1000)
            code = 200 if 'admin' in (me.get('grants') or []) else 403
        except urllib.error.HTTPError as e: code = 401 if e.code in (401, 403) else 503
        except Exception as e: code = 503; STATS['last_err'] = ('auth ' + type(e).__name__ + ': ' + str(e))[:200]
    AUTHC[k] = (time.time(), code); return code
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def send(self, code, body, ctype='application/json; charset=utf-8'):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(raw))); self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        STATS['requests'] += 1; u = urllib.parse.urlparse(self.path); p = u.path; qs = urllib.parse.parse_qs(u.query)
        try:
            if p in ('/healthz', '/health'): return self.send(200, dict(ok=True, version=VERSION, requests=STATS['requests'], errors=STATS['errors'], graphs=STATS['graphs'], lastErr=STATS['last_err'], step=STATS['step'], ms=STATS['ms']))
            if p in ('/', '/index.html'): return self.send(200, open(os.path.join(HERE, 'static', 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
            if p.startswith('/icons/'):   # Azure 공식 아이콘(정적 SVG, 파일명 화이트리스트: 영문 소문자·숫자·-)
                nm = p[7:]
                if re.fullmatch(r'[a-z0-9-]+\.svg|map\.json|NOTICE\.txt', nm) and os.path.isfile(os.path.join(HERE, 'static', 'icons', nm)):
                    raw = open(os.path.join(HERE, 'static', 'icons', nm), 'rb').read()
                    return self.send(200, raw, 'image/svg+xml' if nm.endswith('.svg') else 'application/json; charset=utf-8' if nm.endswith('.json') else 'text/plain; charset=utf-8')
                return self.send(404, dict(code='NOT_FOUND'))
            if p.startswith('/vendor/'):   # 배치 엔진 elkjs(EPL-2.0): 파일명 화이트리스트
                nm = p[8:]
                if nm in ('elk.bundled.js', 'ELK-LICENSE.md') and os.path.isfile(os.path.join(HERE, 'static', 'vendor', nm)):
                    return self.send(200, open(os.path.join(HERE, 'static', 'vendor', nm), 'rb').read(), 'text/javascript; charset=utf-8' if nm.endswith('.js') else 'text/markdown; charset=utf-8')
                return self.send(404, dict(code='NOT_FOUND'))
            if p == '/api/proposals':   # 아키텍처 개선 옵션(설계안) — 관리자 인증 필요
                code = authorized(self.headers)
                if code != 200: return self.send(code, dict(code={401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 503: 'AUTH_UNAVAILABLE'}.get(code, 'ERROR')))
                fp = os.path.join(HERE, 'static', 'proposals.json')
                if not os.path.isfile(fp): return self.send(404, dict(code='NOT_FOUND'))
                return self.send(200, json.load(open(fp, encoding='utf-8')))
            if p == '/api/graph':
                code = authorized(self.headers)
                if code != 200: return self.send(code, dict(code={401: 'UNAUTHORIZED', 403: 'FORBIDDEN', 503: 'AUTH_UNAVAILABLE'}.get(code, 'ERROR'), message={401: '로그인이 필요합니다.', 403: '관리자 권한이 필요합니다.'}.get(code, '로그인 확인 서비스를 사용할 수 없습니다.')))
                return self.send(200, get_graph(bool(qs.get('refresh'))))
            return self.send(404, dict(code='NOT_FOUND'))
        except Exception as e:
            STATS['errors'] += 1; STATS['last_err'] = (type(e).__name__ + ': ' + str(e))[:200]
            return self.send(502, dict(code='UPSTREAM_ERROR', message='Azure Resource Graph를 읽지 못했습니다. 이전 결과가 있으면 그대로 두고 잠시 후 다시 시도하세요.', detail=type(e).__name__))
if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), H).serve_forever()
