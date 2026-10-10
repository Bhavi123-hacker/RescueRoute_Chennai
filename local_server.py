import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from backend.app import api

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            self.respond(*api('GET',self.path.split('?')[0]))
        else:super().do_GET()
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=32768:raise ValueError()
            body=json.loads(self.rfile.read(length))
        except (ValueError,UnicodeError):self.respond(400,{'error':'Invalid JSON or oversized request.'});return
        self.respond(*api('POST',self.path,body))
    def respond(self,status,result):
        payload=json.dumps(result,allow_nan=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)))
        self.end_headers();self.wfile.write(payload)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8020);args=p.parse_args()
    print(f'RescueRoute Chennai: http://localhost:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(Path(__file__).parent/'frontend'))).serve_forever()
