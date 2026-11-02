"""aitel 시험: 가짜 수집 서버에 A→B 호출을 보내 Request/RemoteDependency 봉투·상관 ID·역할 이름·제외 규칙을 확인한다."""
import os, sys, json, time, threading, subprocess, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
HERE = os.path.dirname(os.path.abspath(__file__)); COMMON = os.path.join(HERE, '..', 'common'); RES = []; GOT = []
def chk(n, ok, d=''): RES.append(ok); print('PASS' if ok else 'FAIL', n, '' if ok else '::' + str(d)[:300])
class Ing(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        b = self.rfile.read(int(self.headers.get('Content-Length') or 0)); GOT.extend(json.loads(b)); r = json.dumps({'itemsReceived': 1, 'itemsAccepted': len(json.loads(b)), 'errors': []}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(r))); self.end_headers(); self.wfile.write(r)
ing = HTTPServer(('127.0.0.1', 0), Ing); threading.Thread(target=ing.serve_forever, daemon=True).start()
APP = '''
import sys, os, json
sys.path.insert(0, %r)
import aitel; aitel.install()
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith('/call'):
            peer = os.environ['PEER']; 
            with urllib.request.urlopen(peer + '/leaf?secret=1', timeout=5) as r: body = r.read()
            code = 200
        elif self.path == '/health': body = b'ok'; code = 200
        elif self.path == '/boom': body = b'x'; code = 500
        else: body = b'leaf'; code = 200
        self.send_response(code); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
ThreadingHTTPServer(('127.0.0.1', int(os.environ['PORT'])), H).serve_forever()
''' % COMMON
def start(role, port, peer=''):
    env = dict(os.environ, APPLICATIONINSIGHTS_CONNECTION_STRING='InstrumentationKey=11111111-2222-3333-4444-555555555555;IngestionEndpoint=http://127.0.0.1:%d/;LiveEndpoint=x' % ing.server_port, CONTAINER_APP_NAME=role, PORT=str(port), PEER=peer)
    p = subprocess.Popen([sys.executable, '-c', APP], env=env); time.sleep(1.2); return p
pa = start('ca-test-a', 18301, 'http://127.0.0.1:18302'); pb = start('ca-test-b', 18302)
try:
    urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:18301/call', headers={'X-Correlation-Id': 'op-abc123'}), timeout=5).read()
    urllib.request.urlopen('http://127.0.0.1:18301/health', timeout=5).read()
    try: urllib.request.urlopen('http://127.0.0.1:18302/boom', timeout=5)
    except Exception: pass
    time.sleep(7)
finally:
    pa.terminate(); pb.terminate()
req = [e for e in GOT if e['data']['baseType'] == 'RequestData']; dep = [e for e in GOT if e['data']['baseType'] == 'RemoteDependencyData']
bd = lambda e: e['data']['baseData']
chk('요청 봉투 수집(A /call, B /leaf, B /boom)', len(req) == 3, [(e['tags']['ai.cloud.role'], bd(e)['name'], bd(e)['responseCode']) for e in req])
chk('/health는 기록하지 않음', not any(bd(e)['name'].endswith('/health') for e in req))
a_req = [e for e in req if e['tags']['ai.cloud.role'] == 'ca-test-a' and bd(e)['name'] == 'GET /call'][0]
chk('A 요청: 들어온 X-Correlation-Id가 작업 ID', a_req['tags']['ai.operation.id'] == 'op-abc123', a_req['tags'])
chk('A→B 의존 호출 기록(type HTTP, 대상 host:port, 경로만·쿼리 제외)', len(dep) == 1 and bd(dep[0])['type'] == 'HTTP' and bd(dep[0])['target'] == '127.0.0.1:18302' and 'secret' not in json.dumps(dep[0]) and bd(dep[0])['name'] == 'GET /leaf', dep)
chk('의존 호출의 역할은 호출한 쪽(A), 작업 ID 동일', dep[0]['tags']['ai.cloud.role'] == 'ca-test-a' and dep[0]['tags']['ai.operation.id'] == 'op-abc123')
b_leaf = [e for e in req if e['tags']['ai.cloud.role'] == 'ca-test-b' and bd(e)['name'] == 'GET /leaf'][0]
chk('B 요청이 A의 의존 호출에 이어짐(operation.id 동일, parentId=의존 ID)', b_leaf['tags']['ai.operation.id'] == 'op-abc123' and b_leaf['tags'].get('ai.operation.parentId') == bd(dep[0])['id'], b_leaf['tags'])
boom = [e for e in req if bd(e)['name'] == 'GET /boom'][0]
chk('500 응답은 success=false', bd(boom)['success'] is False and bd(boom)['responseCode'] == '500')
chk('iKey·시간·지속시간 형식', all(e['iKey'] == '11111111-2222-3333-4444-555555555555' and e['time'].endswith('Z') and len(bd(e)['duration']) == 12 for e in GOT))
# 연결 문자열이 없으면 아무 것도 하지 않음
r = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0,%r); import aitel, urllib.request; print(aitel.install(), urllib.request.OpenerDirector.open.__name__)' % COMMON], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != 'APPLICATIONINSIGHTS_CONNECTION_STRING'})
chk('연결 문자열이 없으면 비활성(훅 미설치)', r.stdout.split() == ['False', 'open'], r.stdout + r.stderr)
print('RESULT', sum(RES), '/', len(RES))
