"""Blob append 최소 모의(로컬 시험 전용): 토큰·생성·appendblock·목록·Range 읽기."""
import json, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
BL = {}
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def send(self, c, b=b'', h=None):
        self.send_response(c); self.send_header('Content-Length', str(len(b)))
        for k, v in (h or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/msi': return self.send(200, json.dumps({'access_token': 'tok', 'expires_on': '9999999999'}).encode())
        if 'comp=list' in u.query:
            cont = u.path.strip('/'); pre = re.search(r'prefix=([^&]*)', u.query); pre = (__import__('urllib.parse').parse.unquote(pre.group(1)) if pre else '')
            if 'delimiter' not in u.query: return self.send(200, ('<EnumerationResults><Blobs>' + ''.join('<Blob><Name>%s</Name><Properties><Content-Length>%d</Content-Length></Properties></Blob>' % (k[len(cont) + 1:], len(v)) for k, v in sorted(BL.items()) if k.startswith(cont + '/') and k[len(cont) + 1:].startswith(pre)) + '</Blobs></EnumerationResults>').encode())
            names = sorted({k.split('/')[1] for k in BL if k.startswith(cont + '/') and '/' in k[len(cont) + 1:]}); return self.send(200, ('<EnumerationResults><Blobs>' + ''.join('<BlobPrefix><Name>%s/</Name></BlobPrefix>' % n for n in names) + '</Blobs></EnumerationResults>').encode())
        k = u.path.lstrip('/')
        if k not in BL: return self.send(404)
        b = bytes(BL[k]); r = self.headers.get('Range')
        if r:
            m = re.match(r'bytes=(\d*)-(\d*)', r); a, z = m.group(1), m.group(2)
            if a == '': b = b[-int(z):]
            else:
                a = int(a)
                if a >= len(b): return self.send(416)
                b = b[a:int(z) + 1 if z else None]
        self.send(200, b)
    def do_HEAD(self):
        k = urlparse(self.path).path.lstrip('/')
        if k not in BL: return self.send(404)
        self.send_response(200); self.send_header('Content-Length', str(len(BL[k]))); self.end_headers()
    def do_PUT(self):
        u = urlparse(self.path); n = int(self.headers.get('Content-Length', '0')); body = self.rfile.read(n); k = u.path.lstrip('/')
        if 'comp=appendblock' in u.query:
            if k not in BL: return self.send(404)
            BL[k] += body; return self.send(201)
        if self.headers.get('x-ms-blob-type') == 'BlockBlob': BL[k] = bytearray(body); return self.send(201)
        if k in BL: return self.send(409)
        BL[k] = bytearray(); self.send(201)
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8810), H).serve_forever()
