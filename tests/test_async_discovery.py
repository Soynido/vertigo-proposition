"""Async collector contracts on local fixtures; no external network."""
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime import discovery
from test_discovery import FixtureHandler


class AsyncDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(FixtureHandler,directory=str(Path(__file__).parent/'fixtures/site')))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name).resolve()/'out'

    async def test_telemetry_span_contains_awaited_work_and_cancellation(self):
        from proposition_runtime import telemetry
        root=Path(self.tmp.name)/'trace';root.mkdir()
        @telemetry.traced('navigation.visit')
        async def work():
            await asyncio.sleep(.01)
            raise asyncio.CancelledError()
        with telemetry.TraceRecorder(root):
            with self.assertRaises(asyncio.CancelledError): await work()
        events=[json.loads(line) for line in next((root/'telemetry').glob('*.jsonl')).read_text().splitlines()]
        self.assertEqual('CANCELLED',events[-1]['status'])
        self.assertGreater(events[-1]['monotonic_ns']-events[0]['monotonic_ns'],5_000_000)

    async def test_sync_wrapper_refuses_active_loop_before_dns(self):
        with patch.object(discovery,'_url',side_effect=AssertionError('DNS must not start')):
            with self.assertRaisesRegex(RuntimeError,'acollect'):
                discovery.collect(self.base,self.out,allow_local=True)
            with self.assertRaisesRegex(RuntimeError,'acontinue_collect'):
                discovery.continue_collect(self.out/'absent.json',self.out/'next')

    async def test_run_execution_settings_reach_the_task_without_profile_pollution(self):
        from proposition_runtime import state,execution,cli
        from datetime import datetime,timezone
        config={'concurrency':2,'panel_scan':'batch','image_wait_policy':'terminal_aware','proof_storage':'content_addressed','max_host_tasks':1}
        root=Path(self.tmp.name).resolve()/'runs'
        run=state.init_run('https://example.test/',root,execution_config=config)
        ordinary=state.init_run('https://example.test/',root)
        self.assertEqual(ordinary['profile'],run['profile'])
        self.assertEqual(config,run['metadata']['execution']['config'])
        host={'schema_version':'1.0','observed_at':datetime.now(timezone.utc).isoformat(),'host_kind':'fixture','capabilities':[{'id':'browser','status':'AVAILABLE'}]}
        plan=execution.ready_tasks(run['root'],host)['ready'][0]
        self.assertTrue(all(plan['input_parameters'][key]==value for key,value in config.items()))
        self.assertEqual('config.json',str(cli.parser().parse_args(['init','https://example.test/','--execution-config','config.json']).execution_config))
        before=list(root.iterdir())
        with self.assertRaises(ValueError): state.init_run('https://example.test/',root,execution_config={**config,'concurrency':3})
        self.assertEqual(before,list(root.iterdir()))

    async def test_cli_forwards_explicit_concurrency(self):
        from proposition_runtime import cli
        import subprocess
        result=await asyncio.to_thread(subprocess.run,[sys.executable,str(Path(discovery.__file__).parent.parent/'proposition.py'),'collect','--help'],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertIn('--concurrency',result.stdout)

    async def test_async_api_validates_options_before_browser(self):
        for concurrency in (0,3,True,8):
            with self.subTest(concurrency=concurrency),self.assertRaisesRegex(ValueError,'concurrency'):
                await discovery.acollect(self.base,self.out,allow_local=True,concurrency=concurrency)

    async def test_two_viewports_are_isolated_with_real_routes_and_proofs(self):
        report=await discovery.acollect(self.base+'/desktop.html',self.out,allow_local=True,max_pages=1,concurrency=2,panel_scan='batch')
        self.assertEqual(['desktop','mobile'],[p['viewport'] for p in report['pages']])
        self.assertTrue(all(p['status']=='captured' for p in report['pages']),report)
        self.assertEqual(2,report['execution']['peak_visits'])
        self.assertTrue(all(e.get('screenshot_path') for p in report['pages'] for e in p['evidence']))
        self.assertEqual(report,json.loads((self.out/'discovery.json').read_text()))

    async def test_four_visits_have_one_browser_fresh_contexts_and_page_local_redirects(self):
        from playwright.async_api import Browser, BrowserContext
        from proposition_runtime import async_discovery
        from http.server import SimpleHTTPRequestHandler
        web=Path(self.tmp.name).resolve()/'web';web.mkdir()
        (web/'index.html').write_text('<a href="/to-a">A</a><a href="/to-b">B</a>')
        for name in ('a','b'): (web/(name+'.html')).write_text('<h1>'+name+'</h1>')
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                if self.path in ('/to-a','/to-b'):
                    self.send_response(302);self.send_header('Location','/'+self.path[-1]+'.html');self.end_headers()
                else: super().do_GET()
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(web)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        new=Browser.new_context;close=BrowserContext.close;launch=async_discovery.alaunch_browser
        active=set();contexts=set();peak=0;launches=0;resolver_threads=[]
        original_url=discovery._url
        def check_url(*args,**kwargs):
            if kwargs.get('resolve',True): resolver_threads.append(threading.get_ident())
            return original_url(*args,**kwargs)
        async def create(browser,*args,**kwargs):
            nonlocal peak
            context=await new(browser,*args,**kwargs)
            contexts.add(id(context));active.add(id(context));peak=max(peak,len(active));return context
        async def cleanup(context,*args,**kwargs):
            try: return await close(context,*args,**kwargs)
            finally: active.discard(id(context))
        async def start(*args,**kwargs):
            nonlocal launches
            launches+=1;return await launch(*args,**kwargs)
        with patch.object(Browser,'new_context',create),patch.object(BrowserContext,'close',cleanup),patch.object(async_discovery,'alaunch_browser',start),patch.object(discovery,'_url',check_url):
            report=await discovery.acollect(f'http://127.0.0.1:{server.server_port}/index.html',self.out,allow_local=True,max_pages=3,concurrency=4,panel_scan='batch')
        self.assertEqual(1,launches);self.assertEqual(6,len(contexts));self.assertEqual(set(),active)
        self.assertGreater(peak,1);self.assertLessEqual(peak,4)
        self.assertTrue(resolver_threads);self.assertNotIn(threading.get_ident(),resolver_threads)
        self.assertEqual(['desktop','mobile']*3,[p['viewport'] for p in report['pages']])
        for page in report['pages'][2:]:
            expected=page['requested_url'][-1]+'.html'
            self.assertTrue(page['final_url'].endswith(expected),page)
            self.assertTrue(all(item['to'].endswith(expected) for item in page['redirects']),page)
        self.assertTrue(all(p['status']=='captured' for p in report['pages']),report)

    async def test_one_failed_visit_does_not_discard_its_successful_peer(self):
        from playwright.async_api import Page
        goto=Page.goto
        async def navigate(page,*args,**kwargs):
            if page.viewport_size['width']==390: raise TimeoutError('fixture mobile failure')
            return await goto(page,*args,**kwargs)
        with patch.object(Page,'goto',navigate):
            report=await discovery.acollect(self.base+'/desktop.html',self.out,allow_local=True,max_pages=1,concurrency=2,panel_scan='batch')
        self.assertEqual(['captured','error'],[p['status'] for p in report['pages']])
        self.assertEqual(['mobile'],[item['viewport'] for item in report['coverage']['pending_states']])
        self.assertTrue(report['sources'])

    async def test_continuation_proofs_are_checked_before_dns(self):
        prior={'schema_version':'2.0','sources':[{'id':'s','artifacts':[{'path':'missing.txt','bytes':1,'sha256':'0'*64}]}]}
        p=Path(self.tmp.name).resolve()/'prior.json';p.write_text(json.dumps(prior))
        with patch.object(discovery.socket,'getaddrinfo',side_effect=AssertionError('DNS before proof check')):
            with self.assertRaisesRegex(ValueError,'proof'):
                await discovery.acontinue_collect(p,self.out,allow_local=True)

    async def test_cancellation_keeps_success_and_resumes_missing_view_only(self):
        from proposition_runtime import async_navigation
        original=async_navigation.explore
        desktop_done=asyncio.Event()
        async def explore(page,record,*args,**kwargs):
            if record['viewport']=='desktop':
                await original(page,record,*args,**kwargs);desktop_done.set()
            else:
                await asyncio.Event().wait()
        with patch.object(async_navigation,'explore',explore):
            task=asyncio.create_task(discovery.acollect(self.base+'/desktop.html',self.out,allow_local=True,max_pages=1,concurrency=2,panel_scan='batch'))
            await asyncio.wait_for(desktop_done.wait(),20)
            await asyncio.sleep(.1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        report=json.loads((self.out/'discovery.json').read_text())
        self.assertEqual('captured',report['pages'][0]['status'])
        self.assertEqual(['mobile'],[p['viewport'] for p in report['coverage']['pending_states']])
        self.assertTrue(report['sources'])
        resumed=await discovery.acontinue_collect(self.out/'discovery.json',Path(self.tmp.name).resolve()/'resume',allow_local=True,max_pages=1,panel_scan='batch')
        self.assertEqual(['mobile'],[p['viewport'] for p in resumed['pages']])
        self.assertFalse(resumed['coverage']['pending_states'])

if __name__=='__main__': unittest.main()
