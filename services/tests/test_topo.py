"""topo-api 시험: 관계 추출·분류·상태·인가·엔드포인트(고정 자료). 실행: python3 tests/test_topo.py"""
import os, sys, json, threading, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'topoapi'))
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'topoapi')
os.environ['TOPO_FAKE'] = os.path.join(D, 'testdata', 'fixture.json'); os.environ['TOPO_FAKE_AUTH'] = 'ADMINTOKEN'; os.environ['PORT'] = '0'
import topo_app as T
OK = 0; TOT = 0
def chk(n, c, d=''):
    global OK, TOT; TOT += 1; OK += bool(c); print(('PASS ' if c else 'FAIL ') + n + ('' if c else ' :: ' + str(d)[:200]))
fx = json.load(open(os.environ['TOPO_FAKE'], encoding='utf-8')); g = T.build_graph(fx['rows'], fx['rgs'])
by = {n['name']: n for n in g['nodes']}; E = {(x['s'].split('/')[-1], x['t'].split('/')[-1]) for x in g['edges']}
chk('노드 7개·리소스 그룹 4개(빈 그룹 포함, 노드가 없는 rg-z는 제외)', g['counts'] == dict(nodes=7, groups=4), g['counts'])
chk('하위(subnet) ID는 상위 vnet으로 환원: nic→vnet', ('nic-1', 'vnet-1') in E, E)
chk('vm→nic', ('vm-1', 'nic-1') in E)
chk('컨테이너 앱→관리 ID, 앱→스토리지(하위 경로 환원)', ('ca-1', 'id-1') in E and ('ca-1', 'st1') in E, E)
chk('알 수 없는 대상(rg-z)·자기 참조는 관계를 만들지 않음', len(E) == 4 and not any(a == b for a, b in E), E)
K = {(x['s'].split('/')[-1], x['t'].split('/')[-1]): x for x in g['edges']}
chk('NIC→VNet 관계는 net 종류이고 서브넷 이름(s1)을 보존', K[('nic-1', 'vnet-1')]['k'] == 'net' and K[('nic-1', 'vnet-1')].get('sub') == 's1', K[('nic-1', 'vnet-1')])
chk('노드에 서브넷 위치 기록: nic·vm이 vnet-1/s1', by['nic-1'].get('sub') == 's1' and by['vm-1'].get('sub') == 's1' and by['vm-1']['vnet'].endswith('vnet-1'), (by['nic-1'].get('sub'), by['vm-1'].get('sub')))
chk('서비스 분류: 컨테이너 앱 ca-1은 규칙에 없으면 빈 값, calc-api는 탄소 산정, plant-web은 웹·포털', by['ca-1']['svc'] == '' and T.service_of('microsoft.app/containerapps', 'ca-cems-prd-krc-calc-api', 'calc-api') == '탄소 산정' and T.service_of('microsoft.app/containerapps', 'ca-cems-prd-krc-plant-web', 'plant-web') == '웹·포털' and T.service_of('microsoft.network/virtualnetworks', 'x', '') == '')
S0 = '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-x/providers/'
rows2 = [dict(id=S0 + 'Microsoft.Storage/storageAccounts/stamaprdkrc01', name='stamaprdkrc01', type='microsoft.storage/storageaccounts', location='koreacentral', resourceGroup='rg-x', st='Succeeded', props={}),
         dict(id=S0 + 'Microsoft.App/containerApps/ca-a', name='ca-a', type='microsoft.app/containerapps', location='koreacentral', resourceGroup='rg-x', st='Running', props={'template': {'containers': [{'env': [{'name': 'STORE', 'value': 'https://stamaprdkrc01.blob.core.windows.net'}]}]}})]
g2 = T.build_graph(rows2, []); D = [(x['s'].split('/')[-1], x['t'].split('/')[-1], x['k']) for x in g2['edges']]
chk('앱 설정 문자열의 스토리지 계정 이름 → 호출 의존(dep) 관계', ('ca-a', 'stamaprdkrc01', 'dep') in D, D)
chk('ARG 응답 종류: dep 관계는 설정 문자열에서만 만들고 짧은 이름(8자 미만)은 무시', not any(x['k'] == 'dep' for x in g['edges']), [x for x in g['edges'] if x['k'] == 'dep'])
chk('분류: vm=compute, vnet=network, st=data, id=security, dns=network', [by[k]['cat'] for k in ('vm-1', 'vnet-1', 'st1', 'id-1', 'example.com')] == ['compute', 'network', 'data', 'security', 'network'])
chk('상태 분류: running/Succeeded=ok, 없음=none', by['vm-1']['sc'] == 'ok' and by['vnet-1']['sc'] == 'ok' and by['example.com']['sc'] == 'none')
chk('상태 분류: Failed/deallocated=bad, Updating=warn', T.state_class('Failed') == 'bad' and T.state_class('PowerState/deallocated') == 'bad' and T.state_class('Updating') == 'warn')
chk('위치 없으면 global·소문자', by['example.com']['location'] == 'global' and by['st1']['location'] == 'japaneast')
chk('약어(vm=VM, containerApps=CA)', by['vm-1']['short'] == 'VM' and by['ca-1']['short'] == 'CA' and by['vnet-1']['short'] == 'VN', (by['vm-1']['short'], by['ca-1']['short']))
chk('응답에 속성 원문(props)이 없음(노출 최소화)', all('props' not in n for n in g['nodes']))
srv = T.ThreadingHTTPServer(('127.0.0.1', 0), T.H); port = srv.server_address[1]; threading.Thread(target=srv.serve_forever, daemon=True).start()
def call(path, tok=None):
    r = urllib.request.Request('http://127.0.0.1:%d%s' % (port, path), headers=({'Authorization': 'Bearer ' + tok} if tok else {}))
    try:
        x = urllib.request.urlopen(r, timeout=10); return x.status, x.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
c, b = call('/api/graph'); chk('토큰 없이 /api/graph 401', c == 401, c)
c, b = call('/api/graph', 'x' * 30 + 'NOPE'); chk('관리자가 아닌 토큰 403', c == 403, c)
c, b = call('/api/graph', 'y' * 30 + 'ADMINTOKEN'); chk('관리자 토큰 200·노드 7', c == 200 and json.loads(b)['counts']['nodes'] == 7, c)
g3 = T.build_graph(rows2 + [dict(id=S0 + 'Microsoft.App/containerApps/ca-b', name='ca-b', type='microsoft.app/containerapps', location='koreacentral', resourceGroup='rg-x', st='Running', props={})], [])
g3 = T.merge_observed(g3, [dict(Caller='ca-a', Target='ca-b.internal.env.koreacentral.azurecontainerapps.io', calls=10, fails=2, avgMs=100), dict(Caller='ca-a', Target='ca-b.internal.env.koreacentral.azurecontainerapps.io:443', calls=30, fails=0, avgMs=200),
                           dict(Caller='ca-a', Target='stamaprdkrc01.blob.core.windows.net', calls=5, fails=0, avgMs=20), dict(Caller='ca-a', Target='unknown-host.example.com', calls=7, fails=0, avgMs=5), dict(Caller='nobody', Target='ca-b.x', calls=1, fails=0, avgMs=1)])
O = {(x['s'].split('/')[-1], x['t'].split('/')[-1]): x for x in g3['edges'] if x['k'] == 'obs'}
chk('관측 호출은 obs 관계로 합침(같은 호출자·대상은 합산, 포트·FQDN 무시)', O[('ca-a', 'ca-b')]['calls'] == 40 and O[('ca-a', 'ca-b')]['fails'] == 2 and O[('ca-a', 'ca-b')]['avgMs'] == 175, O)
chk('저장소 계정 이름 대상도 연결, 모르는 호출자·모르는 대상은 선을 만들지 않음', ('ca-a', 'stamaprdkrc01') in O and len(O) == 2 and g3['observed']['unmatched'][0][0] == 'unknown-host.example.com', (list(O), g3['observed']))
# --- LB·게이트웨이 백엔드 연결(k='lb') ---
SB = '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/'
def RW(rg, prov, typ, name, props, loc='koreacentral'): return dict(id=SB + rg + '/providers/' + prov + '/' + typ + '/' + name, name=name, type=(prov + '/' + typ).lower(), location=loc, resourceGroup=rg, st='Succeeded', props=props)
ENV1 = RW('rg-w', 'Microsoft.App', 'managedEnvironments', 'cae-was', dict(infrastructureResourceGroup='rg-w-infra', staticIp='10.1.2.3', defaultDomain='dom-a.koreacentral.azurecontainerapps.io'))
ENV2 = RW('rg-w', 'Microsoft.App', 'managedEnvironments', 'cae-web', dict(infrastructureResourceGroup='rg-web-infra', staticIp='10.1.9.9', defaultDomain='dom-b.koreacentral.azurecontainerapps.io'))
LB1 = RW('rg-w-infra', 'Microsoft.Network', 'loadBalancers', 'capp-svc-lb', dict(frontendIPConfigurations=[]))
LB2 = RW('rg-web-infra', 'Microsoft.Network', 'loadBalancers', 'capp-svc-lb', dict(frontendIPConfigurations=[]))
LBX = RW('rg-other', 'Microsoft.Network', 'loadBalancers', 'lb-plain', dict(frontendIPConfigurations=[]))
def APP(name, env, ext, fqdn, port=8080): return RW('rg-w', 'Microsoft.App', 'containerApps', name, dict(environmentId=env['id'], configuration=dict(ingress=dict(external=ext, fqdn=fqdn, targetPort=port))))
A1 = APP('ca-api', ENV1, True, 'ca-api.dom-a.koreacentral.azurecontainerapps.io'); A2 = APP('ca-inner', ENV1, False, 'ca-inner.internal.dom-a.koreacentral.azurecontainerapps.io'); A3 = APP('ca-portal', ENV2, True, 'ca-portal.dom-b.koreacentral.azurecontainerapps.io', 80)
A4 = RW('rg-w', 'Microsoft.App', 'containerApps', 'ca-noingress', dict(environmentId=ENV1['id'], configuration={}))
def ID(r): return dict(id=r['id'])
AGW = RW('rg-hub', 'Microsoft.Network', 'applicationGateways', 'agw-1', dict(
    httpListeners=[dict(name='l-ama', properties=dict(hostNames=['ama.example.com', 'ama2.example.com'])), dict(name='l-api', properties=dict(hostName='api.example.com'))],
    backendAddressPools=[dict(name='pool-portal', properties=dict(backendAddresses=[dict(fqdn='ca-portal.dom-b.koreacentral.azurecontainerapps.io'), dict(fqdn='unknown.example.org')])), dict(name='pool-api', properties=dict(backendAddresses=[dict(fqdn='CA-API.dom-a.koreacentral.azurecontainerapps.io')])), dict(name='pool-empty', properties=dict(backendAddresses=[]))],
    probes=[dict(name='pr1', properties=dict(path='/healthz'))],
    backendHttpSettingsCollection=[dict(name='bs1', properties=dict(protocol='Https', port=443, probe=dict(id='/x/probes/pr1')))],
    urlPathMaps=[dict(name='pm1', properties=dict(defaultBackendAddressPool=dict(id='/x/backendAddressPools/pool-api'), defaultBackendHttpSettings=dict(id='/x/backendHttpSettingsCollection/bs1'), pathRules=[]))],
    requestRoutingRules=[dict(name='r1', properties=dict(httpListener=dict(id='/x/httpListeners/l-ama'), backendAddressPool=dict(id='/x/backendAddressPools/pool-portal'), backendHttpSettings=dict(id='/x/backendHttpSettingsCollection/bs1'))), dict(name='r2', properties=dict(httpListener=dict(id='/x/httpListeners/l-api'), urlPathMap=dict(id='/x/urlPathMaps/pm1')))]))
LE = T.lb_edges([ENV1, ENV2, LB1, LB2, LBX, A1, A2, A3, A4, AGW]); LD = {(x['s'].split('/')[-1], x['t'].split('/')[-1]): x for x in LE}
chk('LB 연결: 모두 k=lb·note 있음', all(x['k'] == 'lb' and x['note'] for x in LE), LE[:1])
chk('ACA 환경 LB → 그 환경(관리 RG 일치)', ('capp-svc-lb', 'cae-was') in LD and ('capp-svc-lb', 'cae-web') in LD and '10.1.2.3' in LD[('capp-svc-lb', 'cae-was')]['note'])
chk('환경 LB → 환경 안 ingress.external=true 앱만(내부 전용·ingress 없는 앱 제외)', [t for (s, t) in LD if s == 'capp-svc-lb' and t.startswith('ca-')].count('ca-api') == 1 and ('capp-svc-lb', 'ca-inner') not in LD and ('capp-svc-lb', 'ca-noingress') not in LD)
chk('LB가 다른 환경의 앱과 섞이지 않음(요청 경로: LB1↛ca-portal)', len([1 for x in LE if x['s'] == LB1['id'] and x['t'] == A3['id']]) == 0 and len([1 for x in LE if x['s'] == LB2['id'] and x['t'] == A3['id']]) == 1)
chk('환경 LB가 아닌 일반 LB(lb-plain)는 추측 연결을 만들지 않음', not [1 for x in LE if x['s'] == LBX['id'] or x['t'] == LBX['id']])
chk('게이트웨이 → 풀 주소(FQDN, 대소문자 무시)와 같은 앱: 포털·API', ('agw-1', 'ca-portal') in LD and ('agw-1', 'ca-api') in LD)
chk('게이트웨이 → 그 앱 환경의 내부 LB(경로 한 단계 더)', LD.get(('agw-1', 'capp-svc-lb')) is not None and len([1 for x in LE if x['s'] == AGW['id'] and x['t'] == LB1['id']]) == 1 and len([1 for x in LE if x['s'] == AGW['id'] and x['t'] == LB2['id']]) == 1)
chk('note에 리스너 호스트·풀·설정·프로브가 들어감(여러 호스트 결합)', all(w in LD[('agw-1', 'ca-portal')]['note'] for w in ('ama.example.com, ama2.example.com', 'pool-portal', 'Https', '443', '/healthz')), LD[('agw-1', 'ca-portal')]['note'])
chk('경로 맵(urlPathMap)의 기본 풀도 해석(api.example.com → pool-api)', 'api.example.com' in LD[('agw-1', 'ca-api')]['note'] and 'pool-api' in LD[('agw-1', 'ca-api')]['note'])
chk('해석하지 못한 풀 주소(unknown.example.org)·빈 풀은 선을 만들지 않음', not [1 for x in LE if 'unknown' in x['note'] and x['t'] == AGW['id']] and not [x for x in LE if x['t'].endswith('unknown')])
chk('같은 쌍은 한 번만(중복 없음)', len(LE) == len({(x['s'], x['t']) for x in LE}), len(LE))
gL = T.build_graph([ENV1, ENV2, LB1, LB2, A1, A3, AGW], []); chk('그래프에 lb 관계가 들어가고 노드 ID와 일치', all(x['s'] in {n['id'] for n in gL['nodes']} and x['t'] in {n['id'] for n in gL['nodes']} for x in gL['edges'] if x['k'] == 'lb') and any(x['k'] == 'lb' for x in gL['edges']), gL['counts'])
import os as _os
c, b = call('/icons/virtual-networks.svg'); chk('공식 아이콘 SVG 제공(Virtual-Networks)', c == 200 and (b.decode() if isinstance(b, bytes) else b).lstrip().startswith('<svg'), (c, b[:30]))
c, b = call('/icons/../topo_app.py'); chk('아이콘 경로 이탈 차단', c == 404, c)
c, b = call('/icons/nope.svg'); chk('없는 아이콘 404', c == 404, c)
_mp = json.load(open(_os.path.join(_os.path.dirname(__file__), '..', 'topoapi', 'static', 'icons', 'map.json')))
chk('아이콘 매핑의 모든 파일이 존재', all(_os.path.isfile(_os.path.join(_os.path.dirname(__file__), '..', 'topoapi', 'static', 'icons', s + '.svg')) for s in _mp.values()), len(_mp))
c, b = call('/healthz'); chk('/healthz 200', c == 200 and json.loads(b)['version'].startswith('topo-api'), b[:80])
c, b = call('/'); chk('/ 페이지 제공(인증 없이, 데이터 없음)', c == 200 and b'<html' in b.lower() and b'00000000' not in b, c)
c, b = call('/vendor/elk.bundled.js'); chk('배치 엔진 파일 제공(JS)', c == 200 and len(b) > 500000, c)
c, b = call('/vendor/ELK-LICENSE.md'); chk('배치 엔진 라이선스 문서 제공', c == 200 and b'Eclipse Public License' in b.encode() if isinstance(b, str) else c == 200, c)
c, b = call('/vendor/../topo_app.py'); chk('vendor 경로 탈출 거부', c == 404, c)
c, b = call('/vendor/other.js'); chk('vendor 화이트리스트 외 거부', c == 404, c)
c, b = call('/api/proposals'); chk('/api/proposals 인증 없이 거부', c in (401, 403, 503), c)
import json as _j2; _pj = _j2.load(open(_os.path.join(_os.path.dirname(__file__), '..', 'topoapi', 'static', 'proposals.json'), encoding='utf-8')); chk('설계안 JSON: 옵션 8개·변형안 2개 이상', len(_pj['options']) == 8 and all(len(o['variants']) >= 2 for o in _pj['options']), len(_pj['options']))
c, b = call('/nope'); chk('없는 경로 404', c == 404, c)
print('RESULT', OK, '/', TOT); sys.exit(0 if OK == TOT else 1)
