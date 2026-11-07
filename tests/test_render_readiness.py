"""Real two-origin fixture: source navigation stays local, render assets are bounded."""
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import sys,tempfile,threading,unittest,json,time,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime.discovery import collect
from proposition_runtime.render_resources import _fetch

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/drip.js':
            try:
                for byte in b'HTTP/1.1 200 OK\r\nContent-Type: application/javascript\r\n\r\n':
                    self.connection.sendall(bytes([byte]));time.sleep(.2)
            except OSError:pass
        else:super().do_GET()

class RenderReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.web=self.root/'web';self.web.mkdir()
        self.cdn=self.root/'cdn';self.cdn.mkdir()
        self.cdn_url=self.serve(self.cdn);self.url=self.serve(self.web)
    def serve(self,directory):
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(directory)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:'+str(server.server_port)
    def test_external_render_script_and_style_unlock_real_content_and_menu(self):
        (self.cdn/'ready.js').write_text("setTimeout(()=>{document.querySelector('#loader').remove();document.querySelector('main').hidden=false},900)")
        (self.cdn/'style.css').write_text('main{background:rgb(12,34,56);color:white}')
        (self.web/'index.html').write_text('''<style>#loader{position:fixed;inset:0;background:white;z-index:99}</style>
<div id="loader">STUDIO</div><main hidden><h1>Real venue</h1><button aria-controls="menu" aria-expanded="false" onclick="const n=document.querySelector('#menu');n.hidden=!n.hidden;this.setAttribute('aria-expanded',String(!n.hidden))">Menu</button><nav id="menu" hidden><a href="#details">Details</a></nav></main>
<script async src="'''+self.cdn_url+'''/ready.js"></script><link rel="stylesheet" href="'''+self.cdn_url+'''/style.css">''')
        report=collect(self.url+'/index.html',self.root/'out',allow_local=True,max_pages=1,concurrency=2)
        self.assertTrue(all(p['status']=='captured' for p in report['pages']),[(p['status'],p.get('exploration')) for p in report['pages']])
        for p in report['pages']:
            self.assertTrue(p['interactions'])
            texts=[(self.root/'out'/v['text_path']).read_text() for v in p['evidence']]
            self.assertTrue(any('Real venue' in t for t in texts))
        self.assertTrue(report.get('render_resources'))
        self.assertTrue(all('body' not in v for v in report['render_resources']))
    def test_a_permanent_loader_cannot_be_called_complete_or_expand_the_crawl(self):
        (self.web/'index.html').write_text('<div id="loader" style="position:fixed;inset:0">Loading</div><main hidden><h1>Unseen</h1><a href="/other.html">Other</a></main>')
        (self.web/'other.html').write_text('<h1>Must not expand from unready DOM</h1>')
        report=collect(self.url+'/index.html',self.root/'out',allow_local=True,max_pages=2,concurrency=2)
        self.assertTrue(all(p['status']=='partial' for p in report['pages']),report['coverage'])
        self.assertTrue(all('render_not_ready' in p['exploration']['unresolved'] for p in report['pages']))
        self.assertEqual([self.url+'/index.html'],report['coverage']['attempted_urls'])

    def test_render_fetch_cannot_contact_local_services_without_fixture_opt_in(self):
        (self.cdn/'ready.js').write_text('document.title="must not run"')
        with self.assertRaisesRegex(ValueError,'Non-public'):_fetch(self.cdn_url+'/ready.js',False)

    def test_a_render_dependency_larger_than_the_limit_is_not_returned(self):
        (self.cdn/'large.js').write_bytes(b'x'*(4*1024*1024+1))
        with self.assertRaisesRegex(ValueError,'byte budget'):_fetch(self.cdn_url+'/large.js',True)

    def test_slow_headers_cannot_keep_a_resource_worker_or_its_process_alive(self):
        code='''import sys,asyncio\nfrom proposition_runtime.render_resources import RenderResources\nasync def main():\n try:await RenderResources(True).get(sys.argv[1],'script')\n except TimeoutError:print('BOUNDED_TIMEOUT',flush=True)\nasyncio.run(main())'''
        env=dict(__import__('os').environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
        try:r=subprocess.run([sys.executable,'-c',code,self.cdn_url+'/drip.js'],env=env,capture_output=True,text=True,timeout=8)
        except subprocess.TimeoutExpired:self.fail('Render worker prevented process exit past its deadline')
        self.assertEqual(0,r.returncode,r.stderr)
        self.assertIn('BOUNDED_TIMEOUT',r.stdout)

if __name__=='__main__':unittest.main()
