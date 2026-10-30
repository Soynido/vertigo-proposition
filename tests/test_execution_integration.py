"""Canonical task/gate parity; synthetic stage availability, no creative PASS."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import unittest
import test_state as fixtures
from proposition_runtime import state,execution,transactions,composition

class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.StateTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.run=self.f.new_run();self.root=Path(self.run['root'])
        (self.root/'input.txt').write_text('Synthetic input, not a real proposal')
    def event(self,attempt,kind,payload,proof=None):
        return {'schema_version':'1.0','event_id':'evt-'+uuid4().hex,'attempt_id':attempt,'kind':kind,
                'observed_at':datetime.now(timezone.utc).isoformat(),'evidence_ref':proof,'payload':payload}
    def add_inputs(self,identifiers):
        for identifier in identifiers:
            name=identifier+'.txt';(self.root/name).write_text(identifier)
            state.add_artifact(self.root,identifier,name,'internal')
    def claims(self):
        run=state.load_run(self.root);meta=transactions.execution_metadata(run);meta['config']['max_host_tasks']=2
        run['metadata']['execution']=meta;state.save_run(self.root,run)
        self.add_inputs([r.split(':',1)[1] for r in composition.CLIENT_INPUTS])
        host={'schema_version':'1.0','observed_at':datetime.now(timezone.utc).isoformat(),'host_kind':'synthetic_fixture','capabilities':[{'id':'host.independent_context','status':'AVAILABLE'}]}
        with patch.object(state,'_quality_stages',return_value=['review.client']),patch.object(state,'_stage_report',return_value={'status':'BLOCKED'}):
            plans=execution.ready_tasks(self.root,host)['ready']
            return [execution.claim_task(self.root,p['task_id'],p) for p in plans]
    def reconcile(self,claim,index,context):
        attempt=claim['attempt'];identifier=attempt['attempt_id'];key='dispatch-'+str(index)
        execution.task_event(self.root,self.event(identifier,'dispatch_intent',{'dispatch_key':key}))
        execution.task_event(self.root,self.event(identifier,'unknown_outcome',{'last_known_state':'DISPATCHING','error_code':'lost'}))
        proof={'attempt_id':identifier,'request_hash':attempt['request_hash'],'dispatch_key':key,'host_job_ref':'job-'+str(index),'state':'RUNNING','context_ref':context,'fresh_context':True}
        path=self.root/('host-'+str(index)+'.json');path.write_text(json.dumps(proof))
        descriptor={'path':path.name,'sha256':state._sha(path),'size_bytes':path.stat().st_size}
        return execution.task_event(self.root,self.event(identifier,'reconciled',{'observed_state':'RUNNING','host_job_ref':'job-'+str(index),'result_path':None,'result_sha256':None},descriptor))
    def test_reconciled_independent_context_cannot_be_used_by_a_second_review(self):
        a,b=self.claims();self.assertEqual('RUNNING',self.reconcile(a,0,'shared-context')['status'])
        with self.assertRaisesRegex(ValueError,'already used'): self.reconcile(b,1,'shared-context')
    def test_reconciliation_rechecks_context_after_intervening_write(self):
        claim=self.claims()[0];original=execution._isolation_proof
        def interleave(*args):
            original(*args);state.add_artifact(self.root,'intervening','input.txt','internal')
        with patch.object(execution,'_isolation_proof',interleave):
            with self.assertRaises(transactions.Conflict):self.reconcile(claim,0,'context-a')
    def test_creator_continuation_recovers_its_context_from_reconciliation(self):
        self.add_inputs(['creative-inputs']);run=state.load_run(self.root);row=run['artifacts']['creative-inputs']
        proof=self.root/'creator-proof.json';proof.write_text(json.dumps({'context_ref':'creator-recovered'}))
        descriptor={'path':proof.name,'sha256':state._sha(proof),'size_bytes':proof.stat().st_size}
        run['metadata']['execution']={**transactions.execution_metadata(run),'attempts':{'old':{'attempt_id':'old','state':'COMMITTED','events':[{'kind':'reconciled','evidence_ref':descriptor}]}}}
        request={'task_key':'creative.direction.prepare','input_hashes':{'artifact:creative-inputs':state._record_digest(row)}}
        with patch.object(execution,'_request',return_value=request):
            self.assertEqual('creator-recovered',execution._creator_context(run,{'isolation':'continue_public','task_key':'creative.direction.develop'}))
    def test_client_and_synthesized_reviews_receive_every_canonical_client_input(self):
        specs=execution._specs();ids={i for s in specs if s['stage_id'] in ('client.composition','review.client') for i in s['completed_by']+s['inputs']}|{r.split(':',1)[1] for r in composition.CLIENT_INPUTS}
        self.add_inputs(sorted(ids));run=state.load_run(self.root)
        for spec in execution._variants(run):
            if spec['task_key'].startswith('review.client.') or (spec['task_key'].startswith('stage-review.') and spec['stage_id'] in ('client.composition','review.client')):
                self.assertTrue({r.split(':',1)[1] for r in composition.CLIENT_INPUTS}.issubset(spec['inputs']),spec['task_key'])
                plan=execution._plan(run,spec,execution._parameters(run,spec))
                self.assertTrue(set(composition.CLIENT_INPUTS).issubset(plan['packet_plan']['record_refs']))
                self.assertTrue({i+'.txt' for i in [r.split(':',1)[1] for r in composition.CLIENT_INPUTS]}.issubset({f['path'] for f in plan['packet_plan']['files']}))
    def test_handoff_roles_own_the_canonical_derivatives_and_correct_skill(self):
        specs=execution._specs();sales=next(s for s in specs if s['task_key']=='internal.handoffs.sales');technical=next(s for s in specs if s['task_key']=='internal.handoffs.technical')
        self.assertEqual('proposition-technical',technical['skill'])
        self.assertTrue({'sales-playbook','follow-up-register'}.issubset(sales['completed_by']))
        producers={i for s in specs for i in s['completed_by']}
        self.assertTrue(composition.DERIVATIVES.issubset(producers),composition.DERIVATIVES-producers)
        for spec in (sales,technical):
            self.assertTrue({r.split(':',1)[1] for r in composition.CLIENT_INPUTS}.issubset(spec['inputs']))
            for identifier in spec['completed_by']:
                if identifier not in spec['outputs']:continue
                details=spec['outputs'][identifier];path='outputs/'+details['name'];mapping={path:(self.root/'input.txt',{'role':identifier,'audience':details['audience']})}
                operation={'op':'artifact.register','args':{'artifact_id':identifier,'path':path,'audience':details['audience'],'dependencies':list(composition.CLIENT_INPUTS)}}
                execution._check_operations(state.load_run(self.root),{'task_key':spec['task_key']},spec,[operation],mapping)

if __name__=='__main__':unittest.main()
