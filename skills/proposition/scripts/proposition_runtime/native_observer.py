"""Local native-activity viewer available before a prospect run exists.

Only public activity comes from the owned host adapter. HTTP cannot dispatch an
agent, change a profile, approve a task or inject an execution event.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
from pathlib import Path
import secrets
import time
from urllib.parse import parse_qs, urlsplit

ASSETS = Path(__file__).resolve().parents[2]/'resources/observer'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, data, kind='application/json; charset=utf-8'):
        raw = data if isinstance(data, bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers();self.wfile.write(raw)

    def local(self):
        expected='127.0.0.1:'+str(self.server.server_port)
        return (self.headers.get('Host')==expected
                and self.headers.get('Origin','http://'+expected)=='http://'+expected
                and self.headers.get('Sec-Fetch-Site')!='cross-site')

    def authorized(self):
        return self.local() and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token)

    def do_GET(self):
        if not self.local():
            return self.reply(403,{'error':'Local origin required'})
        parsed=urlsplit(self.path)
        if parsed.path=='/api/activity':
            if not self.authorized():
                return self.reply(403,{'error':'Session required'})
            query=parse_qs(parsed.query)
            try:
                if set(query)-{'after'} or any(len(v)!=1 for v in query.values()):raise ValueError()
                after=int(query.get('after',['0'])[0])
                if after<0 or after>self.server.feed.cursor:raise ValueError()
                result=self.server.feed.snapshot(after=after)
                result['observed_at']=time.time()
                result['ui_ready_at']=self.server.ui_ready_at
                return self.reply(200,result)
            except (ValueError,TypeError):
                return self.reply(400,{'error':'Invalid activity cursor'})
        if parsed.path=='/api/ready':
            if not self.authorized():return self.reply(403,{'error':'Session required'})
            return self.reply(200,{'observer_ready':True,'ui_ready_at':self.server.ui_ready_at,
                                  'native_source_connected':self.server.feed.connected})
        file=self.server.assets.get(parsed.path)
        if not file or file.is_symlink() or not file.is_file():
            return self.reply(404,{'error':'Not found'})
        kind=mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        if file.suffix=='.js':kind='text/javascript'
        self.reply(200,file.read_bytes(),kind+('; charset=utf-8' if file.suffix in ('.html','.js','.css') else ''))

    def do_POST(self):
        if urlsplit(self.path).path!='/api/ui-ready' or not self.authorized():
            return self.reply(403,{'error':'No execution endpoint'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:raise ValueError()
            data=json.loads(self.rfile.read(length))
            if data!={'view':'native-public-activity','version':1}:raise ValueError()
            if self.server.ui_ready_at is None:self.server.ui_ready_at=time.time()
            self.reply(200,{'ui_ready_at':self.server.ui_ready_at})
        except (ValueError,TypeError):
            self.reply(400,{'error':'Invalid UI acknowledgement'})


def make_server(feed, *, port=0):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    server.token=secrets.token_hex(32)
    server.feed=feed;server.ui_ready_at=None;server.assets={}
    for p in ASSETS.rglob('*'):
        if p.is_file() and not p.is_symlink() and p.suffix in {'.html','.css','.js','.svg','.woff2','.png','.jpg','.txt'}:
            server.assets['/'+p.relative_to(ASSETS).as_posix()]=p
    server.assets['/']=ASSETS/'index.html'
    return server
