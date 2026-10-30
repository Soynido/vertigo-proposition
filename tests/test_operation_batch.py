"""Closed transactional operations, historical replay and fresh validity."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import multiprocessing
import subprocess
import sys
from unittest.mock import patch
import test_state as fixtures
from proposition_runtime import state,transactions

def concurrent_batch(root,batch,barrier,output):
    real=state._prepared_file_inputs
    def wait_at_commit(previous,prepared):
        result=real(previous,prepared);barrier.wait(3);return result
    try:
        with patch.object(state,'_prepared_file_inputs',wait_at_commit):result=transactions.apply_batch(root,batch)
        output.put(result['status'])
    except Exception as error:output.put(type(error).__name__+': '+str(error))

class OperationBatchTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(transactions,'apply_batch'),'Closed atomic batch missing')
        self.f=fixtures.StateTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups);self.run=self.f.new_run();self.root=Path(self.run['root']);(self.root/'proof.txt').write_text('fixed observation')
    def batch(self,operations,key='op-transaction1'):
        self.assertTrue(hasattr(transactions,'apply_batch'),'Closed atomic batch missing')
        run=state.load_run(self.root)
        result={'schema_version':'1.0','operation_id':key,'run_id':run['id'],'expected_inputs':{},'expected_contracts':transactions.contract_hashes(),'expected_profile_hash':state._digest(run['profile']),'expected_state_revision':None,'operations':operations}
        result['payload_sha256']=state._digest(result);return result
    def op(self,id='proof'):return {'op':'artifact.register','args':{'artifact_id':id,'path':'proof.txt','audience':'internal','dependencies':[]}}
    def test_atomic_failure_does_not_commit_first_operation(self):
        batch=self.batch([self.op(),{'op':'fact.register','args':{'fact_id':'bad','value':'x','source_ids':['missing']}}]);before=(self.root/'state.json').read_bytes()
        with self.assertRaises(ValueError):transactions.apply_batch(self.root,batch)
        self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_replay_is_read_only_and_does_not_resurrect_stale(self):
        batch=self.batch([self.op()]);first=transactions.apply_batch(self.root,batch);self.assertEqual('COMMITTED',first['status']);before=(self.root/'state.json').read_bytes();again=transactions.apply_batch(self.root,batch)
        self.assertEqual('REPLAYED',again['status']);self.assertEqual(first['receipt'],again['receipt']);self.assertEqual(before,(self.root/'state.json').read_bytes())
        (self.root/'proof.txt').write_text('changed');state.invalidate_changed(self.root);before=(self.root/'state.json').read_bytes();again=transactions.apply_batch(self.root,batch)
        self.assertEqual('STALE',again['current_validity']['artifact:proof']);self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_key_conflict_and_unknown_fields_are_rejected(self):
        batch=self.batch([self.op()]);transactions.apply_batch(self.root,batch);changed=copy.deepcopy(batch);changed['operations'][0]['args']['artifact_id']='other';changed.pop('payload_sha256');changed['payload_sha256']=state._digest(changed)
        with self.assertRaisesRegex(ValueError,'CONFLICT'):transactions.apply_batch(self.root,changed)
        batch=self.batch([self.op('other')],key='op-transaction2');batch['unexpected']='no';batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch)
        with self.assertRaises(ValueError):transactions.apply_batch(self.root,batch)
    def test_new_key_same_record_preserves_dates_approval_and_dependents(self):
        transactions.apply_batch(self.root,self.batch([self.op()]));record=state.load_run(self.root)['artifacts']['proof'];transactions.apply_batch(self.root,self.batch([self.op()],key='op-transaction2'));self.assertEqual(record,state.load_run(self.root)['artifacts']['proof'])
    def test_disjoint_intervening_write_survives_long_result(self):
        batch=self.batch([self.op()]);real=state._prepared_file_inputs;done=[]
        def intervening(previous,prepared):
            result=real(previous,prepared)
            if not done:
                done.append(True);run=state.load_run(self.root);run['metadata']['independent']='keep';state.save_run(self.root,run)
            return result
        with patch.object(state,'_prepared_file_inputs',intervening):transactions.apply_batch(self.root,batch)
        current=state.load_run(self.root);self.assertEqual('keep',current['metadata']['independent']);self.assertIn('proof',current['artifacts'])
    def test_relevant_intervening_change_is_conflict(self):
        transactions.apply_batch(self.root,self.batch([self.op()]));run=state.load_run(self.root);batch=self.batch([self.op('dependent')],key='op-transaction2');batch['operations'][0]['args']['dependencies']=['artifact:proof'];batch['expected_inputs']={'artifact:proof':state._record_digest(run['artifacts']['proof'])};batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch)
        (self.root/'proof.txt').write_text('different');state.invalidate_changed(self.root)
        with self.assertRaisesRegex(ValueError,'CONFLICT|[Ss]tale'):transactions.apply_batch(self.root,batch)
    def test_strict_revision_rejects_an_independent_new_commit(self):
        batch=self.batch([self.op()]);batch['expected_state_revision']=0;batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch)
        transactions.apply_batch(self.root,self.batch([self.op('other')],key='op-transaction2'))
        with self.assertRaisesRegex(ValueError,'CONFLICT'):transactions.apply_batch(self.root,batch)
    def test_noop_receipt_still_names_its_output(self):
        transactions.apply_batch(self.root,self.batch([self.op()]));result=transactions.apply_batch(self.root,self.batch([self.op()],key='op-transaction2'))
        self.assertIn('artifact:proof',result['receipt']['record_refs'])
    def test_source_and_fact_noops_preserve_their_dates(self):
        source={'op':'source.register','args':{'source_id':'s','path':'proof.txt'}}
        transactions.apply_batch(self.root,self.batch([source]));run=state.load_run(self.root);expected={'source:s':state._record_digest(run['sources']['s'])}
        fact={'op':'fact.register','args':{'fact_id':'f','value':'observed','source_ids':['s']}}
        b=self.batch([fact],key='op-transaction2');b['expected_inputs']=expected;b.pop('payload_sha256');b['payload_sha256']=state._digest(b);transactions.apply_batch(self.root,b);before=state.load_run(self.root)
        b=self.batch([source,fact],key='op-transaction3');b['expected_inputs']=expected;b.pop('payload_sha256');b['payload_sha256']=state._digest(b);transactions.apply_batch(self.root,b);after=state.load_run(self.root)
        self.assertEqual(before['sources'],after['sources']);self.assertEqual(before['facts'],after['facts'])
    def test_two_real_processes_preserve_disjoint_records_and_receipts(self):
        batches=[self.batch([self.op('output'+str(i))],key='op-process-key'+str(i)) for i in range(2)]
        ctx=multiprocessing.get_context('fork');barrier=ctx.Barrier(2);output=ctx.Queue();processes=[ctx.Process(target=concurrent_batch,args=(self.root,b,barrier,output)) for b in batches]
        for p in processes:p.start()
        for p in processes:p.join(6)
        try:self.assertEqual(['COMMITTED','COMMITTED'],sorted(output.get(timeout=2) for _ in processes))
        finally:
            for p in processes:
                if p.is_alive():p.kill();p.join()
        current=state.load_run(self.root);self.assertEqual({'output0','output1'},set(current['artifacts']));self.assertEqual(2,len(current['metadata']['execution']['receipts']));self.assertEqual(2,current['metadata']['execution']['revision'])
    def test_source_reread_does_not_resurrect_stale(self):
        op={'op':'source.register','args':{'source_id':'s','path':'proof.txt'}};transactions.apply_batch(self.root,self.batch([op]));run=state.load_run(self.root);run['sources']['s']['status']='STALE';state.save_run(self.root,run)
        transactions.apply_batch(self.root,self.batch([op],key='op-transaction2'))
        self.assertEqual('STALE',state.load_run(self.root)['sources']['s']['status'])
    def test_reobserve_binds_a_new_dated_capture_and_cannot_reuse_it(self):
        from discovery_fixture import write_report
        path=write_report(state.load_run(self.root));report=json.loads(path.read_text());source=report['sources'][0]
        op={'op':'source.register','args':{'source_id':'s','path':str(path.parent.relative_to(self.root)/source['artifacts'][0]['path']),'locator':source['url'],'kind':'observation'}}
        transactions.apply_batch(self.root,self.batch([op]));run=state.load_run(self.root);run['sources']['s']['observed_at']='2026-10-25T00:00:00+00:00';state.save_run(self.root,run)
        op={'op':'source.reobserve','args':op['args']|{'observed_at':source['retrieved_at'],'observation_proof':{'source_id':source['id'],'file':{'path':str(path.relative_to(self.root)),'sha256':state._sha(path),'size_bytes':path.stat().st_size,'role':'observation','audience':'internal'}}}}
        transactions.apply_batch(self.root,self.batch([op],key='op-transaction2'))
        self.assertEqual(source['retrieved_at'],state.load_run(self.root)['sources']['s']['observed_at'])
        with self.assertRaisesRegex(ValueError,'new|[Nn]ew|observation'):transactions.apply_batch(self.root,self.batch([op],key='op-transaction3'))
    def test_real_launcher_commits_and_reports_conflict_code(self):
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        help_result=subprocess.run([sys.executable,str(launcher),'apply-batch','--help'],capture_output=True,text=True)
        self.assertEqual(0,help_result.returncode,'apply-batch is not available to the installed CLI')
        batch=self.batch([self.op()]);path=self.root/'batch.json';path.write_text(json.dumps(batch))
        result=subprocess.run([sys.executable,str(launcher),'apply-batch',str(self.root),str(path)],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr);self.assertEqual('COMMITTED',json.loads(result.stdout)['status'])
        batch['operations'][0]['args']['artifact_id']='different';batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch);path.write_text(json.dumps(batch))
        result=subprocess.run([sys.executable,str(launcher),'apply-batch',str(self.root),str(path)],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(3,result.returncode);self.assertEqual('CONFLICT',json.loads(result.stdout)['status'])
    def test_partial_discovery_keeps_valid_observations_without_business_pass(self):
        from discovery_fixture import write_report
        from proposition_runtime.discovery_evidence import inspect_discovery
        path=write_report(state.load_run(self.root));data=json.loads(path.read_text());data['status']='partial';data['pages'][0]['exploration']['status']='partial';data['pages'][0]['exploration']['unresolved']=['overlay_not_dismissed'];path.write_text(json.dumps(data))
        batch=self.batch([{'op':'discovery.register','args':{'report_path':str(path.relative_to(self.root))}}])
        problem=None
        try:result=transactions.apply_batch(self.root,batch)
        except Exception as error:problem=error
        self.assertIsNone(problem,'Valid partial observations must be retained while their business gate remains blocked')
        current=state.load_run(self.root);self.assertIn('site-discovery',current['artifacts']);self.assertEqual('BLOCKED',inspect_discovery(current)['status'])
    def test_changed_observation_invalidates_derived_fact_in_same_commit(self):
        state.add_source(self.root,'s','proof.txt');state.add_fact(self.root,'f','old',['s']);before=state.load_run(self.root)
        (self.root/'proof.txt').write_text('new observation')
        batch=self.batch([{'op':'source.register','args':{'source_id':'s','path':'proof.txt'}}]);batch['expected_inputs']={'source:s':state._record_digest(before['sources']['s'])};batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch)
        transactions.apply_batch(self.root,batch);self.assertEqual('STALE',state.load_run(self.root)['facts']['f']['status'])
    def test_self_dependency_is_rejected_without_commit(self):
        transactions.apply_batch(self.root,self.batch([self.op()]));before=state.load_run(self.root);op=self.op();op['args']['dependencies']=['artifact:proof'];batch=self.batch([op],key='op-transaction2');batch['expected_inputs']={'artifact:proof':state._record_digest(before['artifacts']['proof'])};batch.pop('payload_sha256');batch['payload_sha256']=state._digest(batch)
        with self.assertRaisesRegex(ValueError,'[Cc]ycl'):transactions.apply_batch(self.root,batch)
