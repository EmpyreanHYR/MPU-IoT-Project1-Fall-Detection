"""Persistent private outbox plus token-protected access to the local dashboard."""
import argparse
import hmac
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, ProxyHandler, build_opener
from urllib.error import HTTPError, URLError
from edge_runtime import Store

HTTP = build_opener(ProxyHandler({}))


def make_server(store, host, port, token, dashboard_url='http://127.0.0.1:18300'):
    if not token: raise ValueError('Device token is required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def reply(self, code, payload, content_type='application/json'):
            data=payload if isinstance(payload,bytes) else json.dumps(payload,separators=(',',':')).encode()
            self.send_response(code);self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
        def authorized(self):
            if not hmac.compare_digest(self.headers.get('X-Device-Token',''),token):
                self.reply(401,{'error':'invalid device token'});return False
            return True
        def do_GET(self):
            if not self.authorized():return
            if self.path=='/records':self.reply(200,{'records':store.pending(),**store.stats()})
            elif self.path=='/health':self.reply(200,{'service':'persistent edge outbox',**store.stats()})
            elif self.path in ('/dashboard/status','/dashboard/preview'):
                suffix='/api/status' if self.path.endswith('status') else '/preview.jpg'
                try:
                    with HTTP.open(Request(dashboard_url+suffix),timeout=3) as response:
                        data=response.read(256001)
                        if len(data)>256000:raise ValueError('oversized response')
                        if suffix.endswith('.jpg'):
                            if not data.startswith(b'\xff\xd8'):raise ValueError('invalid preview')
                            self.reply(200,data,'image/jpeg')
                        else:self.reply(200,json.loads(data))
                except (HTTPError,URLError,OSError,ValueError):self.reply(503,{'error':'local dashboard unavailable'})
            else:self.reply(404,{'error':'not found'})
        def do_POST(self):
            if not self.authorized():return
            if self.path!='/ack':self.reply(404,{'error':'not found'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<5000:raise ValueError
                count=store.acknowledge(json.loads(self.rfile.read(size)).get('record_ids'))
                self.reply(200,{'acknowledged':count})
            except (ValueError,AttributeError):self.reply(400,{'error':'invalid acknowledgement'})
    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',default='data/edge.sqlite3')
    parser.add_argument('--bind',default=os.environ.get('FALLGUARD_RELAY_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=18082)
    parser.add_argument('--dashboard-url',default='http://127.0.0.1:18300')
    args=parser.parse_args()
    server=make_server(Store(args.database),args.bind,args.port,os.environ['FALLGUARD_INGEST_TOKEN'],args.dashboard_url)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    stop.wait();server.shutdown();server.server_close()

if __name__=='__main__':main()
