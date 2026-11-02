#!/usr/bin/env python3
"""로컬 개발용: site/ 정적 파일을 8766에서 제공하고 /api/krx/* 는 127.0.0.1:8791(KRX API 서비스)로 전달한다."""
import http.server, socketserver, urllib.request, os
os.chdir('/srv/ama/workspace/ama-web-v2/site')
class H(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith('/api/report'):
            n = int(self.headers.get('Content-Length', '0') or 0); body = self.rfile.read(n)
            try:
                rq = urllib.request.Request('http://127.0.0.1:8791' + self.path, data=body, method='POST', headers={'Content-Type': 'application/octet-stream'})
                with urllib.request.urlopen(rq, timeout=60) as r:
                    b = r.read(); self.send_response(r.status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
            except Exception:
                self.send_response(502); self.end_headers()
            return
        self.send_response(404); self.end_headers()
    def do_GET(self):
        if self.path.startswith('/api/plant/') or self.path.startswith('/plant-vm/'):     # 로컬 시험: 중앙 수신(8801)·공장 앱(8802)
            tgt = 'http://127.0.0.1:8801/' + self.path[len('/api/plant/'):] if self.path.startswith('/api/plant/') else 'http://127.0.0.1:8802/' + self.path.split('/', 3)[3]
            try:
                with urllib.request.urlopen(tgt, timeout=10) as r:
                    b = r.read(); self.send_response(r.status); self.send_header('Content-Type', r.headers.get('Content-Type', 'application/json')); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
            except Exception:
                self.send_response(502); self.end_headers()
            return
        if self.path.startswith('/api/krx') or self.path.startswith('/api/report'):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8791' + self.path, timeout=20) as r:
                    b = r.read(); self.send_response(r.status); self.send_header('Content-Type', r.headers.get('Content-Type', 'application/json')); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
            except Exception:
                self.send_response(502); self.end_headers()
            return
        return super().do_GET()
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer(('127.0.0.1', 8766), H).serve_forever()
