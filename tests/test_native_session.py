"""The installed startup entry, not a maintainer-only launch script."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
try:
    from proposition_runtime import native_session as ns
except ImportError:
    ns=None


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ns,'Canonical native startup entry is missing')
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name).resolve();(self.workspace/'.vertigo').mkdir()
        (self.workspace/'AGENTS.md').write_text('Entry')
        dest=self.workspace/'.agents/skills';dest.mkdir(parents=True)
        (dest/'proposition').mkdir();(dest/'proposition/SKILL.md').write_text('Principal')
        digest=hashlib.sha256(b'Principal').hexdigest()
        (dest/'.proposition-install.json').write_text(json.dumps({'files':{'proposition/SKILL.md':digest}}))
        (self.workspace/'.vertigo/setup.json').write_text(json.dumps({'host':'codex','skills_destination':str(dest)}))

    def test_input_inventory_includes_installed_files_and_all_instruction_ancestors(self):
        files=ns.input_inventory(self.workspace)
        self.assertIn(self.workspace/'AGENTS.md',files)
        self.assertIn(self.workspace/'.agents/skills/proposition/SKILL.md',files)
        (self.workspace/'.agents/skills/proposition/SKILL.md').write_text('Modified')
        with self.assertRaisesRegex(ValueError,'installation'):ns.input_inventory(self.workspace)

    def test_native_worker_identity_skips_bootstrap_but_not_an_unrelated_lane(self):
        folder=self.workspace/'.vertigo/native/session';folder.mkdir(parents=True)
        (folder/'launch.json').write_text(json.dumps({'thread_id':'worker','state':'TURN_INTENT'}))
        (self.workspace/'.vertigo/native/current.json').write_text(json.dumps({'session':str(folder)}))
        self.assertTrue(ns.is_worker(self.workspace,'worker'))
        self.assertFalse(ns.is_worker(self.workspace,'outer'))

    def test_opening_receipt_is_bound_to_session_owner_and_cannot_be_replaced(self):
        folder=self.workspace/'.vertigo/native/session';folder.mkdir(parents=True)
        (folder/'session.json').write_text(json.dumps({'owner_thread_id':'owner'}))
        payload=self.workspace/'panel.json';payload.write_text(json.dumps({'status':'queued','threadId':'wrong'}))
        with self.assertRaisesRegex(ValueError,'calling lane'):ns.register_open(folder,payload,'owner')
        payload.write_text(json.dumps({'status':'queued','threadId':'owner'}))
        result=ns.register_open(folder,payload,'owner');self.assertEqual('queued',result['status'])
        self.assertEqual(result,ns.register_open(folder,payload,'owner'))
        with self.assertRaisesRegex(ValueError,'calling lane'):ns.register_open(folder,payload,'wrong')

    def test_installed_launcher_exposes_context_before_any_run_is_initialized(self):
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result=subprocess.run([sys.executable,str(launcher),'native','context','--workspace',str(self.workspace)],
            capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertEqual('LAUNCHER',json.loads(result.stdout)['status'])

    def test_unknown_old_session_does_not_allow_a_new_dispatch(self):
        setup=self.workspace/'.vertigo/setup.json';data=json.loads(setup.read_text())
        data.update(status='PASS',installation='INSTALLED',native_observer={'enabled':True});setup.write_text(json.dumps(data))
        folder=self.workspace/'.vertigo/native/old';folder.mkdir(parents=True)
        (folder/'result.json').write_text(json.dumps({'status':'UNKNOWN_OUTCOME'}))
        (folder.parent/'current.json').write_text(json.dumps({'session':str(folder)}))
        real_popen=ns.subprocess.Popen
        def spawn(command,*args,**kwargs):
            if 'native' in command and 'serve' in command:raise AssertionError('duplicate dispatch')
            return real_popen(command,*args,**kwargs)
        with patch('proposition_runtime.native_setup.locate_codex_cli',return_value=sys.executable),patch.object(ns.subprocess,'Popen',side_effect=spawn):
            with self.assertRaisesRegex(ValueError,'unknown'):
                ns.prepare(self.workspace,'https://github.com/fixture/kit\nhttps://fixture.example/',
                    model='gpt-6-sol',effort='xhigh',caller='owner')

    def test_repeating_same_completed_request_returns_its_receipt_without_a_new_process(self):
        setup=self.workspace/'.vertigo/setup.json';data=json.loads(setup.read_text())
        data.update(status='PASS',installation='INSTALLED',native_observer={'enabled':True});setup.write_text(json.dumps(data))
        folder=self.workspace/'.vertigo/native/old';folder.mkdir(parents=True)
        prompt='https://github.com/fixture/kit\nhttps://fixture.example/'
        request={'workspace':str(self.workspace),'owner_thread_id':'owner','prompt':prompt,'model':'gpt-6-sol','effort':'xhigh',
                 'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ns.input_inventory(self.workspace)}}
        (folder/'request.json').write_text(json.dumps(request));(folder/'result.json').write_text(json.dumps({'status':'COMPLETED'}))
        (folder.parent/'current.json').write_text(json.dumps({'session':str(folder)}))
        real_popen=ns.subprocess.Popen
        def spawn(command,*args,**kwargs):
            if 'native' in command and 'serve' in command:raise AssertionError('duplicate dispatch')
            return real_popen(command,*args,**kwargs)
        with patch('proposition_runtime.native_setup.locate_codex_cli',return_value=sys.executable),patch.object(ns.subprocess,'Popen',side_effect=spawn):
            result=ns.prepare(self.workspace,prompt,model='gpt-6-sol',effort='xhigh',caller='owner')
        self.assertEqual('REPLAY',result['status'])
        self.assertEqual(str(folder),result['session'])


    def test_stop_marker_is_recorded_while_dispatch_lock_is_held(self):
        from proposition_runtime.transactions import run_lock
        folder=self.workspace/'.vertigo/native/session';folder.mkdir(parents=True)
        (folder/'request.json').write_text(json.dumps({'owner_thread_id':'owner'}))
        with run_lock(folder):
            result=ns.request_stop(folder,'owner')
        self.assertEqual('STOP_REQUESTED',result['status'])
        self.assertTrue((folder/'stop.json').is_file())

    def test_idle_child_with_no_terminal_evidence_cannot_complete_the_service(self):
        folder=self.workspace/'.vertigo/native/session';folder.mkdir(parents=True)
        (folder/'request.json').write_text(json.dumps({'workspace':str(self.workspace),
            'prompt':'https://github.com/fixture/kit\nhttps://fixture.example/','model':'gpt-6-sol','effort':'xhigh',
            'owner_thread_id':'owner','argv':['fixture'],'inputs':{str(self.workspace/'AGENTS.md'):hashlib.sha256(b'Entry').hexdigest()}}))
        (folder/'panel-open.json').write_text(json.dumps({'status':'queued','threadId':'owner'}))
        (folder/'close-view.json').write_text('{}')
        workspace=self.workspace
        class ProtocolHost:
            outcome_unknown=False;diagnostics=set()
            def __init__(self,**options):self.observe=options['on_notification'];self.connection=options['on_connection']
            def __enter__(self):self.connection(True);return self
            def __exit__(self,*args):self.connection(False)
            def request(self,method,params,**kwargs):
                if method=='account/read':return {'account':{'type':'chatgpt'}}
                if method=='model/list':return {'data':[{'model':'gpt-6-sol','supportedReasoningEfforts':[{'reasoningEffort':'xhigh'}]}]}
                if method=='thread/start':return {'thread':{'id':'root','status':{'type':'idle'}},'model':'gpt-6-sol','reasoningEffort':'xhigh','instructionSources':[str(workspace/'AGENTS.md')]}
                if method=='turn/start':
                    self.observe({'method':'turn/started','params':{'threadId':'root','turn':{'id':'turn','status':'inProgress'}}})
                    self.observe({'method':'thread/started','params':{'thread':{'id':'child','parentThreadId':'root','status':{'type':'idle'}}}})
                    self.observe({'method':'turn/completed','params':{'threadId':'root','turn':{'id':'turn','status':'completed'}}})
                    self.connection(False)
                    return {'turn':{'id':'turn','status':'completed'}}
                raise AssertionError(method)
        with patch('proposition_runtime.native_host.AppServerClient',ProtocolHost):result=ns.serve(folder)
        self.assertEqual('UNKNOWN_OUTCOME',result['status'])

    def _finished_durable_session(self):
        from test_native_launch import SERVER
        from proposition_runtime.native_launch import NativeLaunch
        from proposition_runtime.native_host import AppServerClient
        from proposition_runtime.native_activity import NativeActivity
        from types import SimpleNamespace
        folder=self.workspace/'.vertigo/native/durable';folder.mkdir(parents=True)
        script=self.workspace/'host.py';script.write_text(SERVER)
        argv=[sys.executable,'-u',str(script),str(self.workspace)]
        feed=NativeActivity();observer=SimpleNamespace(feed=feed,ui_ready_at=1)
        inputs={str(self.workspace/'AGENTS.md'):hashlib.sha256(b'Entry').hexdigest()}
        request={'workspace':str(self.workspace),'prompt':'https://github.com/fixture/kit\nhttps://fixture.example/',
                 'model':'gpt-6-sol','effort':'xhigh','owner_thread_id':'owner','argv':argv,'inputs':inputs}
        (folder/'request.json').write_text(json.dumps(request))
        with AppServerClient(argv=argv,on_notification=feed.observe,on_connection=feed.connection) as host:
            launch=NativeLaunch(host,observer,folder,workspace=self.workspace,prompt=request['prompt'],
                model='gpt-6-sol',effort='xhigh',inputs=inputs,lane_id='owner',panel_open={'threadId':'owner','status':'queued'})
            started=launch.start();host.request('fixture/finish',{})
        (folder/'result.json').write_text(json.dumps({'status':'UNKNOWN_OUTCOME','error':'Lost source'}))
        (folder/'lifecycle.json').write_text(json.dumps({'root_id':started['thread_id'],'agents':[
            {'id':started['thread_id'],'turn_id':started['turn_id'],'parent_id':None}]}))
        return folder

    def test_reconcile_reads_durable_result_without_rewriting_failure_or_redispatching(self):
        folder=self._finished_durable_session();before=(folder/'result.json').read_bytes()
        result=ns.reconcile(folder,'owner')
        self.assertEqual('COMPLETED',result['status'])
        self.assertEqual(before,(folder/'result.json').read_bytes())
        self.assertEqual('COMPLETED',ns.status(folder)['status'])
        calls=[json.loads(x) for x in (self.workspace/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(1,sum(c['method']=='turn/start' for c in calls))

    def test_service_crash_before_result_write_can_still_reconcile_the_owned_turn(self):
        folder=self._finished_durable_session();(folder/'result.json').unlink()
        self.assertEqual('COMPLETED',ns.reconcile(folder,'owner')['status'])
        self.assertFalse((folder/'result.json').exists())
        self.assertEqual('COMPLETED',ns.status(folder)['status'])

    def test_reconcile_refuses_another_lane_before_contacting_host(self):
        folder=self._finished_durable_session();calls=(self.workspace/'calls.jsonl').read_bytes()
        with self.assertRaisesRegex(ValueError,'owner|lane'):ns.reconcile(folder,'foreign')
        self.assertEqual(calls,(self.workspace/'calls.jsonl').read_bytes())

    def test_installed_init_inherits_only_the_matching_worker_admission_clock(self):
        import contextlib,os,time
        from datetime import datetime,timezone
        from proposition_runtime import cli
        folder=self._finished_durable_session();request=json.loads((folder/'request.json').read_text())
        request['created_at']=time.time()-75;(folder/'request.json').write_text(json.dumps(request))
        (folder.parent/'current.json').write_text(json.dumps({'session':str(folder)}))
        args=cli.parser().parse_args(['init','https://fixture.example/','--runs-root',str(self.workspace/'runs'),'--delivery-format','web'])
        with contextlib.chdir(self.workspace),patch.dict(os.environ,{'CODEX_THREAD_ID':'owned'}):run=cli.execute(args)
        self.assertEqual(datetime.fromtimestamp(request['created_at'],timezone.utc).isoformat(),run['created_at'])
        self.assertIsNone(ns.admission_time(self.workspace,'foreign','https://fixture.example/'))

    def test_reconcile_cannot_clear_unknown_when_a_descendant_identity_is_incomplete(self):
        folder=self._finished_durable_session();ledger=json.loads((folder/'lifecycle.json').read_text())
        ledger['agents'].append({'id':'child','parent_id':'owned','turn_id':None})
        (folder/'lifecycle.json').write_text(json.dumps(ledger))
        self.assertEqual('UNKNOWN_OUTCOME',ns.reconcile(folder,'owner')['status'])

    def _serve_timeout(self,*,reject_stop=False):
        from test_native_launch import SERVER
        from types import SimpleNamespace
        import time
        folder=self.workspace/'.vertigo/native/timeout';folder.mkdir(parents=True)
        script=self.workspace/'host.py';script.write_text(SERVER)
        if reject_stop:(self.workspace/'reject-stop').touch()
        (folder/'request.json').write_text(json.dumps({'workspace':str(self.workspace),
            'prompt':'https://github.com/fixture/kit\nhttps://fixture.example/','model':'gpt-6-sol','effort':'xhigh',
            'owner_thread_id':'owner','argv':[sys.executable,'-u',str(script),str(self.workspace)],
            'created_at':time.time(),'inputs':{str(self.workspace/'AGENTS.md'):hashlib.sha256(b'Entry').hexdigest()}}))
        (folder/'panel-open.json').write_text(json.dumps({'status':'queued','threadId':'owner'}))
        (folder/'close-view.json').write_text('{}')
        ticks=iter([0,1,1202,1203,1204])
        clock=SimpleNamespace(monotonic=lambda:next(ticks),time=time.time,sleep=time.sleep)
        with patch.object(ns,'time',clock):result=ns.serve(folder)
        return folder,result

    def test_service_ceiling_interrupts_owned_turn_and_preserves_its_lifecycle(self):
        folder,result=self._serve_timeout()
        self.assertEqual('INTERRUPTED',result['status'])
        self.assertEqual('t1',result['launch']['turn_id'])
        self.assertEqual('INTERRUPTED',result['activity']['agents'][0]['status'])
        self.assertTrue((folder/'lifecycle.json').exists())

    def test_error_in_stop_still_preserves_owned_identities_and_observation(self):
        folder,result=self._serve_timeout(reject_stop=True)
        self.assertEqual('UNKNOWN_OUTCOME',result['status'])
        self.assertEqual('t1',result['launch']['turn_id'])
        self.assertEqual('owned',result['activity']['root_id'])
        self.assertEqual('t1',json.loads((folder/'lifecycle.json').read_text())['agents'][0]['turn_id'])

if __name__=='__main__':unittest.main()
