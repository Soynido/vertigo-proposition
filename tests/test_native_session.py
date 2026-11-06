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

if __name__=='__main__':unittest.main()
