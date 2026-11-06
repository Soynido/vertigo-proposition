"""Real bounded browser/CLI fixture: entities, media and PDF share one origin."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json,os
from pathlib import Path
import subprocess,sys,tempfile,threading,unittest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime import state,discovery_evidence as de

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

class DiscoveryScopeRuntimeTests(unittest.TestCase):
    def test_actual_installed_cli_keeps_resource_inventory_and_uses_sourced_entity_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();site=root/'site';site.mkdir();(site/'other').mkdir()
            (site/'index.html').write_text('<!doctype html><html><body><h1>Current Hotel</h1><a href="/service.html">Our service</a><a href="/other/">Other Hotel in another city</a><a href="/photo.png">Photo</a><a href="/brochure.pdf">Brochure</a></body></html>')
            (site/'service.html').write_text('<!doctype html><h1>Our service at Current Hotel</h1>')
            (site/'other/index.html').write_text('<!doctype html><h1>Other Hotel</h1>')
            Image.new('RGB',(30,30),'blue').save(site/'photo.png')
            from pypdf import PdfWriter
            pdf=PdfWriter();pdf.add_blank_page(width=100,height=100)
            with (site/'brochure.pdf').open('wb') as out:pdf.write(out)
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(site)))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/'
                run=state.init_run(url,root/'runs',delivery_format='web');runroot=Path(run['root'])
                launcher=os.environ.get('PROPOSITION_TEST_INSTALLED_LAUNCHER',str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'))
                def cli(*args):
                    p=subprocess.run([sys.executable,launcher,*map(str,args)],capture_output=True,text=True,timeout=45)
                    self.assertIn(p.returncode,(0,2),p.stdout[-1000:]+p.stderr[-500:]);return json.loads(p.stdout)
                first=runroot/'research/first'
                report=cli('collect',url,'--run-dir',runroot,'--output',first,'--allow-local-fixture','--max-pages',1)
                self.assertEqual(2,report['execution']['concurrency'])
                self.assertEqual('batch',report['navigation_policy']['panel_scan'])
                de.register(runroot,first/'discovery.json')
                source=next(s for s in report['sources'] if s['viewport']=='desktop')
                scope=runroot/'scope.json';scope.write_text(json.dumps({'version':1,'client_entity':'Current Hotel',
                    'destinations':[{'url':url+'other/','kind':'other_entity','entity_name':'Other Hotel',
                        'source_id':source['id'].removeprefix('source:'),'quote':'Other Hotel in another city',
                        'reason':'A separately named establishment in another city.'}]}))
                cli('discovery','scope',runroot,'--report',scope)
                second=runroot/'research/second'
                resumed=cli('collect','--frontier',first/'discovery.json','--run-dir',runroot,'--output',second,'--allow-local-fixture','--max-pages',4)
                self.assertEqual([url+'service.html'],resumed['coverage']['attempted_urls'])
                self.assertIn(url+'photo.png',resumed['coverage']['discovered_urls'])
                self.assertIn(url+'brochure.pdf',resumed['coverage']['discovered_urls'])
                de.register(runroot,second/'discovery.json')
                result=cli('discovery','scope',runroot,'--report',scope)
                self.assertEqual('PASS',result['status'],result.get('issues'))
                self.assertEqual('BLOCKED',de.inspect_channels(state.load_run(runroot))['status'])
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
