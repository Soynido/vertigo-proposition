"""Task protocol on synthetic runs; host use remains an independent evidence claim."""
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import unittest
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4
import test_state as fixtures
from proposition_runtime import state

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('proposition_runtime.execution'),'Pure task/packet protocol missing')
        from proposition_runtime import execution
        self.execution=execution;self.f=fixtures.StateTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups);self.run=self.f.new_run();self.root=Path(self.run['root'])
        self.host={'schema_version':'1.0','observed_at':datetime.now(timezone.utc).isoformat(),'host_kind':'synthetic_fixture','capabilities':[{'id':'browser','status':'AVAILABLE'}]}
    def claim(self):
        listing=self.execution.ready_tasks(self.root,self.host);plan=next(p for p in listing['ready'] if p['task_key']=='discovery.site.collect')
        return self.execution.claim_task(self.root,plan['task_id'],plan)
    def event(self,attempt,kind,payload,proof=None):
        return {'schema_version':'1.0','event_id':'evt-'+uuid4().hex,'attempt_id':attempt,'kind':kind,'observed_at':datetime.now(timezone.utc).isoformat(),'evidence_ref':proof,'payload':payload}
    def test_ready_is_pure_deterministic_and_requires_capabilities(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()};a=self.execution.ready_tasks(self.root,self.host);b=self.execution.ready_tasks(self.root,self.host)
        self.assertEqual(a,b);self.assertTrue(a['ready']);self.assertEqual(before,{str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        no={**self.host,'capabilities':[]};blocked=self.execution.ready_tasks(self.root,no);self.assertFalse(blocked['ready']);self.assertTrue(blocked['blocked'])
    def test_claim_replay_returns_same_attempt_without_second_reservation(self):
        first=self.claim();again=self.claim();self.assertEqual(first['attempt']['attempt_id'],again['attempt']['attempt_id']);self.assertEqual(first['request']['request_hash'],again['request']['request_hash'])
        self.assertEqual(1,len(state.load_run(self.root)['metadata']['execution']['attempts']))
    def test_dispatch_permission_is_granted_only_once(self):
        claim=self.claim();event=self.event(claim['attempt']['attempt_id'],'dispatch_intent',{'dispatch_key':'dispatch-stable'})
        first=self.execution.task_event(self.root,event);again=self.execution.task_event(self.root,event)
        self.assertTrue(first['dispatch_granted']);self.assertFalse(again['dispatch_granted']);self.assertEqual('DISPATCHING',again['attempt']['state'])
    def test_unknown_outcome_is_not_a_retry_permission(self):
        claim=self.claim();attempt=claim['attempt']['attempt_id'];self.execution.task_event(self.root,self.event(attempt,'dispatch_intent',{'dispatch_key':'dispatch-stable'}));self.execution.task_event(self.root,self.event(attempt,'unknown_outcome',{'error_code':'response_lost','last_known_state':'DISPATCHING'}))
        again=self.claim();self.assertEqual(attempt,again['attempt']['attempt_id']);self.assertEqual('UNKNOWN_OUTCOME',again['attempt']['state'])
    def test_dispatched_requires_current_host_proof(self):
        claim=self.claim();attempt=claim['attempt']['attempt_id'];self.execution.task_event(self.root,self.event(attempt,'dispatch_intent',{'dispatch_key':'dispatch-stable'}))
        with self.assertRaises(ValueError):self.execution.task_event(self.root,self.event(attempt,'dispatched',{'host_job_ref':'invented'}))
    def test_event_reuse_with_changed_payload_is_conflict(self):
        claim=self.claim();event=self.event(claim['attempt']['attempt_id'],'dispatch_intent',{'dispatch_key':'dispatch-stable'});self.execution.task_event(self.root,event);event['payload']['dispatch_key']='different'
        with self.assertRaisesRegex(ValueError,'CONFLICT'):self.execution.task_event(self.root,event)
    def test_status_is_pure_and_never_reports_business_pass(self):
        self.claim();before=(self.root/'state.json').read_bytes();report=self.execution.execution_status(self.root);self.assertEqual(before,(self.root/'state.json').read_bytes());self.assertIn('attempts',report);self.assertNotEqual('PASS',report.get('status'))
    def proof(self,attempt,**values):
        data={'attempt_id':attempt['attempt_id'],'request_hash':attempt['request_hash'],**values}
        path=self.root/('host-'+uuid4().hex+'.json');path.write_text(json.dumps(data))
        return {'path':path.name,'sha256':state._sha(path),'size_bytes':path.stat().st_size}
    def test_claim_rejects_rehashed_parameters_not_issued_by_ready(self):
        plan=deepcopy(self.execution.ready_tasks(self.root,self.host)['ready'][0]);plan['input_parameters']['url']='https://other.test/'
        plan['task_fingerprint']=state._digest({k:plan[k] for k in self.execution.FINGERPRINT_FIELDS});plan['task_id']='task-'+plan['task_fingerprint'][:24]
        with self.assertRaises(ValueError):self.execution.claim_task(self.root,plan['task_id'],plan)
    def test_expired_never_dispatched_claim_releases_only_its_reservation(self):
        first=self.claim();run=state.load_run(self.root);attempt=run['metadata']['execution']['attempts'][first['attempt']['attempt_id']];attempt['claim_expires_at']='2000-01-01T00:00:00Z';state.save_run(self.root,run)
        second=self.claim();self.assertNotEqual(first['attempt']['attempt_id'],second['attempt']['attempt_id']);self.assertEqual('CANCELLED',state.load_run(self.root)['metadata']['execution']['attempts'][first['attempt']['attempt_id']]['state'])
    def test_reconciled_success_requires_real_valid_result_before_state_change(self):
        claim=self.claim();attempt=claim['attempt'];identifier=attempt['attempt_id'];self.execution.task_event(self.root,self.event(identifier,'dispatch_intent',{'dispatch_key':'key'}));self.execution.task_event(self.root,self.event(identifier,'unknown_outcome',{'last_known_state':'DISPATCHING','error_code':'lost'}))
        bad=self.root/'not-a-result.json';bad.write_text('{}');proof=self.proof(attempt,state='SUCCEEDED',host_job_ref='job',dispatch_key='key')
        before=(self.root/'state.json').read_bytes()
        with self.assertRaises(ValueError):self.execution.task_event(self.root,self.event(identifier,'reconciled',{'observed_state':'SUCCEEDED','host_job_ref':'job','result_path':bad.name,'result_sha256':'0'*64},proof))
        self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_terminal_attempt_cannot_be_cancelled_retroactively(self):
        claim=self.claim();attempt=claim['attempt'];identifier=attempt['attempt_id'];self.execution.task_event(self.root,self.event(identifier,'cancelled',{'reason':'not sent','never_dispatched':True}))
        proof=self.proof(attempt,state='CANCELLED')
        with self.assertRaises(ValueError):self.execution.task_event(self.root,self.event(identifier,'cancelled',{'reason':'new cancellation','never_dispatched':False},proof))
    def test_private_packet_copies_inputs_and_detects_snapshot_mutation(self):
        self.f.write(self.run,'input.txt','original observation');state.add_source(self.root,'s','input.txt');state.add_artifact(self.root,'site-discovery','input.txt','internal',['source:s']);state.add_artifact(self.root,'discovery-channels','input.txt','internal',['source:s'])
        run=state.load_run(self.root);spec=next(s for s in self.execution._specs() if s['task_key']=='company.v1.synthesize');plan=self.execution._plan(run,spec,self.execution._parameters(run,spec));directory=self.root/'.execution/inputs/test-packet';directory.mkdir(parents=True)
        packet=self.execution._freeze_packet(self.root,directory,run,plan,spec)
        copied=next(d for d in packet['files'] if d['role']=='input');path=self.root/copied['path'];self.assertEqual('original observation',path.read_text());(self.root/'input.txt').write_text('changed cache/source')
        self.assertEqual('original observation',path.read_text());self.execution._validate_packet(self.root,packet)
        path.chmod(0o644);path.write_text('tampered snapshot')
        with self.assertRaises(ValueError):self.execution._validate_packet(self.root,packet)
    def candidate(self):
        from discovery_fixture import write_report
        import shutil
        claim=self.claim();attempt=claim['attempt'];identifier=attempt['attempt_id'];self.execution.task_event(self.root,self.event(identifier,'dispatch_intent',{'dispatch_key':'key'}));proof=self.proof(attempt,state='RUNNING',host_job_ref='job',dispatch_key='key');self.execution.task_event(self.root,self.event(identifier,'dispatched',{'host_job_ref':'job'},proof))
        source=write_report(self.run);work=self.root/'.work'/identifier;work.mkdir(parents=True);data=json.loads(source.read_text());(work/'sources').mkdir()
        for p in source.parent.iterdir():
            if p!=source:shutil.copyfile(p,work/'sources'/p.name)
        for s in data['sources']:
            for a in s['artifacts']:a['path']='sources/'+a['path']
        for page in data['pages']:
            for e in page['evidence']:
                for k in ('text_path','html_path','screenshot_path'):e[k]='sources/'+e[k]
        (work/'discovery.json').write_text(json.dumps(data));outputs=[]
        for p in sorted(work.rglob('*')):
            if p.is_file():outputs.append(self.execution._descriptor(self.root,p,'discovery-report' if p.name=='discovery.json' else 'discovery-material','internal'))
        request=claim['request'];result={k:request[k] for k in ('run_id','task_id','request_hash','input_hashes','profile_hash','contract_hashes')};result.update(schema_version='1.0',attempt_id=identifier,consumed_packet_hash=None,read_receipt_ref=None,status='SUCCEEDED',outputs=outputs,operations=[{'op':'discovery.register','args':{'report_path':request['output_destinations']['discovery-report']}}],limitations=['Synthetic collector result, no live browsing claim'])
        path=work/'result.json';path.write_text(json.dumps(result));descriptor={'path':path.relative_to(self.root).as_posix(),'sha256':state._sha(path),'size_bytes':path.stat().st_size};self.execution.task_event(self.root,self.event(identifier,'result_ready',{'result_path':descriptor['path'],'result_sha256':descriptor['sha256']},descriptor))
        return claim,path,result
    def test_accept_publishes_exact_files_and_commits_attempt_with_records_once(self):
        self.assertTrue(callable(getattr(self.execution,'accept_task_result',None)),'Result adoption missing')
        claim,path,result=self.candidate();real=state._save_locked;writes=[]
        def tracked(*args,**kwargs):writes.append(True);return real(*args,**kwargs)
        with patch.object(state,'_save_locked',tracked):receipt=self.execution.accept_task_result(self.root,result)
        self.assertEqual(1,len(writes));run=state.load_run(self.root);self.assertEqual('COMMITTED',run['metadata']['execution']['attempts'][claim['attempt']['attempt_id']]['state']);self.assertIn('site-discovery',run['artifacts']);self.assertEqual('COMMITTED',receipt['status'])
        dest=self.root/claim['request']['output_destinations']['discovery-report'];self.assertEqual((path.parent/'discovery.json').read_bytes(),dest.read_bytes());self.assertTrue(dest.stat().st_mode & 0o200,'Published files must remain normally editable; only frozen inputs are read-only');before=(self.root/'state.json').read_bytes()
        self.assertEqual('REPLAYED',self.execution.accept_task_result(self.root,result)['status']);self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_stale_candidate_is_rejected_before_publishing_or_business_adoption(self):
        self.assertTrue(callable(getattr(self.execution,'accept_task_result',None)),'Stale adoption guard missing')
        claim,path,result=self.candidate();run=state.load_run(self.root);run['profile']['actor']='changed owner';state.save_run(self.root,run)
        self.assertEqual('REJECTED_STALE',self.execution.accept_task_result(self.root,result)['status']);run=state.load_run(self.root);self.assertNotIn('site-discovery',run['artifacts']);self.assertFalse((self.root/claim['request']['output_destinations']['discovery-report']).exists())
    def test_task_cannot_adopt_operations_outside_its_role(self):
        self.assertTrue(callable(getattr(self.execution,'accept_task_result',None)),'Task role checks missing')
        claim,path,result=self.candidate();result['operations'].append({'op':'artifact.register','args':{'artifact_id':'unrelated-private-output','path':claim['request']['output_destinations']['discovery-report'],'audience':'client','dependencies':[]}})
        before=(self.root/'state.json').read_bytes()
        with self.assertRaises(ValueError):self.execution.accept_task_result(self.root,result)
        self.assertEqual(before,(self.root/'state.json').read_bytes());self.assertFalse((self.root/claim['request']['output_destinations']['discovery-report']).exists())
    def test_snapshot_keeps_complete_selected_method_tree_not_mutable_cache_paths(self):
        import tempfile
        with tempfile.TemporaryDirectory() as cache:
            cache=Path(cache).resolve();family={'id':'marketingskills','commit':'a'*40,'entrypoints':['skills/method/SKILL.md']};folder=cache/family['id']/family['commit'];source=folder/'source/skills/method/SKILL.md';source.parent.mkdir(parents=True);source.write_text('Original method');(folder/'receipt.json').write_text('{}');(folder/'tree.json').write_text('{}');(folder/'LICENSE').write_text('Example license')
            files={'upstreams/'+family['id']+'/'+family['commit']+'/'+p.relative_to(folder).as_posix():p for p in folder.rglob('*') if p.is_file()}
            spec=next(s for s in self.execution._specs() if s['task_key']=='strategy.understand');plan={'task_id':'task-'+'a'*24,'task_key':spec['task_key'],'packet_plan':{'kind':'private_internal','files':[],'allowed_audiences':['internal']},'input_hashes':{},'input_parameters':{},'output_destinations':{'report':'output.json'},'isolation':{'mode':'coordinator','creator_context_ref':None}}
            directory=self.root/'.execution/inputs/method-test';directory.mkdir(parents=True)
            with patch.object(self.execution,'_method_files',return_value=(files,[(family,folder)])):packet=self.execution._freeze_packet(self.root,directory,state.load_run(self.root),plan,spec)
            native=json.loads((directory/'native-task.json').read_text());method_root=Path(native['methods'][0]['reference_root']);self.assertEqual('Original method',(method_root/'skills/method/SKILL.md').read_text());self.assertTrue((method_root.parent/'receipt.json').exists());self.assertTrue((method_root.parent/'tree.json').exists());self.assertTrue((method_root.parent/'LICENSE').exists())
            for name in ('strategy-draft','task-result','execution-reading'):
                self.assertIn(name,native.get('schemas',{}),'Assigned output schemas were omitted from the worker packet')
                schema=Path(native['schemas'][name]);self.assertTrue(schema.is_relative_to(directory));self.assertEqual(json.loads((state.CONTRACT_ROOT/(name+'.schema.json')).read_text()),json.loads(schema.read_text()))
                self.assertIn(schema.relative_to(self.root).as_posix(),{d['path'] for d in packet['files']})
            source.write_text('Modified mutable cache');self.execution._validate_packet(self.root,packet);self.assertEqual('Original method',(method_root/'skills/method/SKILL.md').read_text())
    def test_canonical_change_between_preflight_and_commit_refuses_atomic_adoption(self):
        self.assertTrue(callable(getattr(self.execution,'accept_task_result',None)),'Atomic task adoption missing')
        claim,path,result=self.candidate();real=state._prepared_file_inputs;done=[]
        def intervening(previous,prepared):
            value=real(previous,prepared)
            if not done:
                done.append(True);run=state.load_run(self.root);run['profile']['actor']='intervening owner';state.save_run(self.root,run)
            return value
        with patch.object(state,'_prepared_file_inputs',intervening):
            with self.assertRaisesRegex(ValueError,'CONFLICT'):self.execution.accept_task_result(self.root,result)
        run=state.load_run(self.root);self.assertNotIn('site-discovery',run['artifacts']);self.assertEqual('SUCCEEDED',run['metadata']['execution']['attempts'][claim['attempt']['attempt_id']]['state'])
    def test_real_launcher_exposes_pure_read_and_resumable_commands(self):
        import subprocess,sys
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py';cap=self.root/'host.json';cap.write_text(json.dumps(self.host));before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for command,args in [('ready-tasks',['--capabilities',str(cap)]),('execution-status',[])]:
            result=subprocess.run([sys.executable,str(launcher),command,str(self.root),*args],capture_output=True,text=True);self.assertEqual(0,result.returncode,result.stderr+result.stdout);json.loads(result.stdout)
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        for command in ('claim-task','task-event','accept-task-result'):
            result=subprocess.run([sys.executable,str(launcher),command,'--help'],capture_output=True,text=True);self.assertEqual(0,result.returncode,result.stderr)
    def test_four_public_topics_are_separate_tasks_before_reconciliation(self):
        self.f.write(self.run,'site.json','{}');state.add_artifact(self.root,'site-discovery','site.json','internal')
        self.host['capabilities']=[{'id':c,'status':'AVAILABLE'} for c in {c for s in self.execution._specs() for c in s['capabilities']}]
        with patch.object(state,'_quality_stages',return_value={'discovery.channels':{}}):listing=self.execution.ready_tasks(self.root,self.host)
        topics=[p for p in listing['ready'] if p['task_key'].startswith('research.topic')]
        self.assertEqual({'google_search','google_ads','meta_ads','reviews'},{p['input_parameters']['topic'] for p in topics});self.assertEqual(4,len({p['task_id'] for p in topics}));self.assertFalse(any(p['task_key']=='research.reconcile' for p in listing['ready']))
    def test_composition_build_reuses_the_four_paths_reserved_before_plan(self):
        self.assertTrue(callable(getattr(self.execution,'_destinations',None)),'Four client destinations are not reserved before composition')
        from proposition_runtime.composition import OUTPUTS
        spec=next(s for s in self.execution._specs() if s['task_key']=='client.composition.plan');reserved=self.execution._destinations(self.run,spec,'seed-before-plan')
        plan={k:reserved[k] for k in OUTPUTS};self.assertEqual(set(OUTPUTS),set(plan))
        self.f.write(self.run,'plan.json',json.dumps({'outputs':plan}));state.add_artifact(self.root,'client-story-map','plan.json','internal')
        build=next(s for s in self.execution._specs() if s['task_key']=='client.composition.build');dest=self.execution._destinations(state.load_run(self.root),build,'different-build-seed')
        self.assertEqual(plan,{k:dest[k] for k in OUTPUTS})
        self.assertTrue(callable(getattr(self.execution,'_check_future_outputs',None)),'The candidate plan can ignore its prior reservation')
        self.execution._check_future_outputs({'output_destinations':reserved},{'outputs':plan})
        with self.assertRaises(ValueError):self.execution._check_future_outputs({'output_destinations':reserved},{'outputs':{**plan,'client-pdf':'another-folder/client-pdf.pdf'}})
    def test_creator_continuation_needs_the_original_context_and_review_needs_freshness(self):
        self.assertTrue(callable(getattr(self.execution,'_isolation_proof',None)),'Creator context continuity is not enforced')
        attempt={'attempt_id':'attempt-'+'a'*32};run=state.load_run(self.root)
        continued={'isolation':{'mode':'continue_public','creator_context_ref':'creator-original'}}
        with self.assertRaises(ValueError):self.execution._isolation_proof(self.root,run,attempt,continued,{'context_ref':'new-unrelated-creator'})
        self.execution._isolation_proof(self.root,run,attempt,continued,{'context_ref':'creator-original'})
        review={'isolation':{'mode':'independent_review','creator_context_ref':None}}
        with self.assertRaises(ValueError):self.execution._isolation_proof(self.root,run,attempt,review,{'context_ref':'reviewer'})
        self.execution._isolation_proof(self.root,run,attempt,review,{'context_ref':'reviewer','fresh_context':True})
    def test_launcher_inventory_block_is_read_success_but_unknown_dispatch_is_code_five(self):
        import subprocess,sys
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py';path=self.root/'host.json';path.write_text(json.dumps({**self.host,'capabilities':[]}))
        observed=subprocess.run([sys.executable,str(launcher),'ready-tasks',str(self.root),'--capabilities',str(path)],capture_output=True,text=True);self.assertEqual(0,observed.returncode,observed.stdout)
        claim=self.claim();identifier=claim['attempt']['attempt_id'];self.execution.task_event(self.root,self.event(identifier,'dispatch_intent',{'dispatch_key':'key'}));self.execution.task_event(self.root,self.event(identifier,'unknown_outcome',{'last_known_state':'DISPATCHING','error_code':'response_lost'}))
        plan=deepcopy(claim['request']);plan.pop('request_hash');plan.update(kind='plan',packet=None);path=self.root/'plan.json';path.write_text(json.dumps(plan))
        observed=subprocess.run([sys.executable,str(launcher),'claim-task',str(self.root),plan['task_id'],'--request',str(path)],capture_output=True,text=True);self.assertEqual(5,observed.returncode,observed.stdout);self.assertFalse(json.loads(observed.stdout)['dispatch_granted'])
