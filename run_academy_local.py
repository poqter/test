"""One-command local prototype. Python standard library only, bound to loopback.

Not a production HTTP server. No cloud APIs and no database. Keep this process
open during the trial. Streamlit deployment uses academy_app.py instead.
"""
from __future__ import annotations
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
from pathlib import Path
import argparse, json, secrets, threading, time, webbrowser, mimetypes
from hwarang_academy.service import AppState, handle
from hwarang_academy.content import ROOT, SCENARIOS, MODES, validate_content

STATES={}; LOCK=threading.RLock(); TOKEN=secrets.token_urlsafe(32)
FRONT=ROOT/'frontend'; MAX_BODY=16384; TTL=2*60*60

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass  # Do not log transcripts/tokens.
    def send(self,status,data,content_type='application/json; charset=utf-8'):
        self.send_response(status);self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urlsplit(self.path).path
        allowed={'/':'index.html','/index.html':'index.html','/styles.css':'styles.css','/app.js':'app.js'}
        if path not in allowed:self.send(404,b'Not found','text/plain');return
        p=FRONT/allowed[path];self.send(200,p.read_bytes(),mimetypes.guess_type(p.name)[0]+'; charset=utf-8')
    def do_POST(self):
        if urlsplit(self.path).path!='/api/action':self.send(404,b'{}');return
        if not secrets.compare_digest(self.headers.get('X-Hwarang-Local',''),TOKEN):self.send(403,b'{}');return
        origin=self.headers.get('Origin');expected=f'http://127.0.0.1:{self.server.server_port}'
        if origin and origin!=expected:self.send(403,b'{}');return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=MAX_BODY:raise ValueError('request size')
            body=json.loads(self.rfile.read(size));sid=body['session']
            if not isinstance(sid,str) or len(sid)>80:raise ValueError('session')
            with LOCK:
                now=time.monotonic()
                for old in list(STATES):
                    if now-STATES[old][0]>TTL:del STATES[old]
                if sid not in STATES:
                    if len(STATES)>=32:raise ValueError('local session limit')
                    selected=body.get('scenario') or 'C07-S01';mode=body.get('mode') or 'GUIDE'
                    if selected not in SCENARIOS:selected='C07-S01'
                    if mode not in MODES:mode='GUIDE'
                    STATES[sid]=(now,AppState(independent=body.get('view')=='simulator',selection=selected,mode=mode))
                app=STATES[sid][1];STATES[sid]=(now,app)
                result=handle(app,body['action']);result['base_url']=expected+'/'
            self.send(200,json.dumps(result,ensure_ascii=False).encode())
        except (KeyError,TypeError,ValueError):self.send(400,b'{"error":"Invalid request"}')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    validate_content()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}/#access={TOKEN}'
    print('Hwarang Academy local preview\n'+url+'\nCtrl+C to stop. No files or cloud services are used.',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();STATES.clear()
if __name__=='__main__':main()
