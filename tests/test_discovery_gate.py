"""A high author score cannot replace current physical Discovery evidence."""
import unittest
import json
import importlib
import subprocess
import sys
from pathlib import Path
import test_state as fixtures
from discovery_fixture import write_report
from proposition_runtime import state


class DiscoveryGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StateTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def api(self):
        from proposition_runtime import discovery_evidence
        register=getattr(discovery_evidence,'register',None)
        self.assertTrue(callable(register),'Missing canonical discovery register operation')
        return register

    def test_missing_navigation_receipt_blocks_all_three_decision_commands(self):
        run=self.fixture.complete_run(discovery_receipt=False)
        report=state.stage_report(run['root'],'discovery.site')
        self.assertEqual('BLOCKED',report['status'], report)
        self.assertIn('discovery_evidence',{x['code'] for x in report['issues']})
        self.assertEqual('discovery.site',state.next_stage(run['root'])['stage_id'])
        self.assertNotEqual('PASS',state.validate_run(run['root'])['status'])

    def test_current_receipt_unblocks_but_tampered_capture_blocks(self):
        register=self.api()
        run=self.fixture.new_run()
        path=write_report(run)
        result=register(run['root'],path)
        self.assertEqual('PASS', result['status'])
        module=importlib.import_module('proposition_runtime.discovery_evidence')
        self.assertEqual('PASS',module.inspect_discovery(state.load_run(run['root']))['status'])
        (path.parent/'mobile.png').write_bytes(b'altered')
        self.assertEqual('BLOCKED',module.inspect_discovery(state.load_run(run['root']))['status'])

    def test_partial_navigation_cannot_be_registered_as_pass(self):
        register=self.api()
        run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['pages'][1]['exploration']['status']='partial'
        report['pages'][1]['exploration']['unresolved']=['overlay_not_dismissed']
        path.write_text(json.dumps(report))
        self.assertEqual('BLOCKED',register(run['root'],path)['status'])

    def test_forged_source_binding_is_refused_without_partial_state_write(self):
        register=self.api()
        run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text());report['pages'][1]['evidence'][0]['source_id']='source:other-page'
        path.write_text(json.dumps(report))
        with self.assertRaises(ValueError): register(run['root'],path)
        self.assertEqual({},state.load_run(run['root'])['sources'])

    def test_legacy_capture_is_not_promoted_to_complete_navigation(self):
        register=self.api()
        run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text());report['schema_version']='1.0';path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,'[Ll]egacy|[Cc]urrent|[Uu]nsupported'): register(run['root'],path)

    def test_registered_navigation_is_consumed_by_real_cli_check(self):
        run=self.fixture.new_run();path=write_report(run)
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        added=subprocess.run([sys.executable,str(launcher),'discovery','register',run['root'],'--report',str(path)],capture_output=True,text=True)
        self.assertEqual(0,added.returncode,added.stderr)
        checked=subprocess.run([sys.executable,str(launcher),'discovery','check',run['root']],capture_output=True,text=True)
        self.assertEqual(0,checked.returncode,checked.stderr)
        self.assertEqual('PASS',json.loads(checked.stdout)['status'])

    def test_high_score_on_unrelated_pdf_cannot_substitute_navigation_provenance(self):
        run=self.fixture.complete_run()
        state.record_evaluation(run['root'],'R08',{'status':'PASS','applicable':True,'evidence':['artifact:client-pdf'],'unknowns':[],'reason':'Unrelated fixture'})
        report=state.stage_report(run['root'],'discovery.site')
        self.assertEqual('BLOCKED',report['status'])
        self.assertIn('discovery_evidence',{x['code'] for x in report['issues']})

    def test_declared_scroll_success_cannot_override_recorded_geometry(self):
        register=self.api()
        run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['pages'][1]['evidence'][0].update(scroll_y=4000,height=14000,viewport_height=844)
        path.write_text(json.dumps(report))
        self.assertEqual('BLOCKED',register(run['root'],path)['status'])

    def test_external_outcomes_reconcile_all_entries_without_asserting_identity(self):
        from proposition_runtime import discovery_evidence as module
        reconcile=getattr(module,'reconcile',None)
        self.assertTrue(callable(reconcile),'Missing shared external outcome reconciliation')
        run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['link_entries']=[{'url':'https://www.instagram.com/fixture/','text':label,'source_id':'source:fixture-desktop'} for label in ('Instagram','Nos photos')]
        path.write_text(json.dumps(report));self.api()(run['root'],path)
        self.assertEqual('BLOCKED',module.inspect_channels(state.load_run(run['root']))['status'])
        journal=path.parent/'external.json'
        journal.write_text(json.dumps({'version':1,'attempts':[{'url':'https://www.instagram.com/fixture/','status':'unavailable','observed_at':'2026-10-26T01:00:00+00:00','reason':'Public access blocked','source_id':None}]}))
        result=reconcile(run['root'],journal)
        self.assertEqual('PASS',result['status'])
        self.assertEqual(2,len(result['entries']))
        self.assertTrue(all(e['destination_status']=='unavailable' and e['identity']=='candidate' and e['analyzed'] is False for e in result['entries']))

    def test_evidenced_www_redirect_can_be_completed_by_host_browser(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text());canonical='https://www.example.test/'
        report['coverage']['discovered_urls'].append(canonical)
        for page in report['pages']:
            page['final_url']=canonical
            page['redirects']=[{'from':run['url'],'to':canonical,'http_status':301}]
        for source in report['sources']: source['url']=canonical
        report['backend']='host-browser'
        path.write_text(json.dumps(report))
        self.assertEqual('PASS',register(run['root'],path)['status'])

    def test_foreign_redirect_is_not_silently_accepted_as_the_prospect(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        for page in report['pages']: page['final_url']='https://unrelated.test/'
        for source in report['sources']: source['url']='https://unrelated.test/'
        path.write_text(json.dumps(report))
        with self.assertRaises(ValueError): register(run['root'],path)

    def test_internal_entry_missing_from_declared_frontier_still_blocks(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['link_entries']=[{'url':run['url']+'offer','text':'Our offer','source_id':'source:fixture-desktop'}]
        path.write_text(json.dumps(report))
        self.assertEqual('BLOCKED',register(run['root'],path)['status'])

    def test_structured_social_candidate_requires_an_external_attempt(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['social_candidates']=[{'url':'https://www.instagram.com/fixture/','source_ids':['source:fixture-desktop'],'methods':['jsonld_sameAs'],'status':'candidate'}]
        path.write_text(json.dumps(report));register(run['root'],path)
        from proposition_runtime.discovery_evidence import inspect_channels
        self.assertEqual('BLOCKED',inspect_channels(state.load_run(run['root']))['status'])

    def test_unloaded_visible_image_overrules_a_declared_complete_status(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text())
        report['pages'][1]['evidence'][0]['visible_images']=[{'alt':'Required photo','loaded':False}]
        path.write_text(json.dumps(report))
        self.assertEqual('BLOCKED',register(run['root'],path)['status'])

    def test_new_channel_journal_invalidates_the_review_of_old_inputs(self):
        register=self.api();run=self.fixture.new_run();path=write_report(run)
        report=json.loads(path.read_text());url='https://www.instagram.com/fixture/'
        report['link_entries']=[{'url':url,'text':'Instagram','source_id':'source:fixture-desktop'}]
        path.write_text(json.dumps(report));register(run['root'],path)
        from proposition_runtime.discovery_evidence import reconcile
        first=path.parent/'external-1.json'
        first.write_text(json.dumps({'version':1,'attempts':[{'url':url,'status':'unavailable','observed_at':'2026-10-26T01:00:00+00:00','source_id':None,'reason':'Blocked first attempt'}]}))
        reconcile(run['root'],first)
        refs=['artifact:'+name for name in state.load_run(run['root'])['artifacts']]
        for item in state._requirements():
            if item['stage_id']=='discovery.channels':
                state.record_evaluation(run['root'],item['id'],{'status':'PASS','applicable':True,'evidence':refs,'unknowns':[],'reason':'Fixture external issue assessed'})
        reviewed={ref:state._resolve(state.load_run(run['root']),ref)['sha256'] for ref in refs}
        self.fixture.stage_review(run,'discovery.channels',reviewed)
        self.assertEqual('PASS',state.stage_report(run['root'],'discovery.channels')['status'])
        second=path.parent/'external-2.json'
        second.write_text(json.dumps({'version':1,'attempts':[{'url':url,'status':'unavailable','observed_at':'2026-10-26T02:00:00+00:00','source_id':None,'reason':'Second actual attempt'}]}))
        reconcile(run['root'],second)
        self.assertNotEqual('PASS',state.stage_report(run['root'],'discovery.channels')['status'])


if __name__=='__main__': unittest.main()
