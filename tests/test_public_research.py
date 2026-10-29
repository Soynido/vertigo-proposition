"""Real journal/state/CLI boundaries for public lookups, no external network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_state as fixtures
from discovery_fixture import write_report
from public_research_fixture import journal
from proposition_runtime import state, discovery_evidence


class PublicResearchTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StateTests('runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.run=self.fixture.new_run()
        discovery_evidence.register(self.run['root'],write_report(self.run))

    def test_linked_destination_coverage_cannot_replace_public_research(self):
        run=state.load_run(self.run['root'])
        run['metadata']['public_research_contract']=1;state.save_run(run['root'],run)
        report=discovery_evidence.inspect_channels(state.load_run(run['root']))
        self.assertEqual('BLOCKED',report['status'])
        self.assertTrue(any('public research' in message.lower() for message in report['issues']))

    def test_new_runs_pin_the_contract_and_refuse_its_removal(self):
        run=state.load_run(self.run['root'])
        self.assertEqual(1,run['metadata'].get('public_research_contract'))
        del run['metadata']['public_research_contract']
        with self.assertRaises(ValueError): state.save_run(run['root'],run)

    def test_complete_journal_and_current_evidence_are_consumed(self):
        path=journal(self.run)
        report=discovery_evidence.reconcile(self.run['root'],path)
        self.assertEqual('PASS',report['status'],report)
        self.assertEqual(4,len(report['public_research']['topics']))
        (Path(self.run['root'])/'google_ads.txt').write_text('changed')
        report=discovery_evidence.inspect_channels(state.load_run(self.run['root']))
        self.assertEqual('BLOCKED',report['status'])

    def test_invalid_or_private_research_does_not_register_a_bundle(self):
        path=journal(self.run);good=json.loads(path.read_text())
        cases=[]
        for key in ('query','provider','geography','window'):
            data=copy.deepcopy(good);data['attempts'][0][key]='';cases.append(data)
        data=copy.deepcopy(good);data['public_research']['topics'][0]['conclusion']='no_ads_exist';cases.append(data)
        data=copy.deepcopy(good);data['public_research']['entity']['source_ids']=[];cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): discovery_evidence.reconcile(self.run['root'],path)
        path.write_text(json.dumps(good))
        run=state.load_run(self.run['root']);run['sources']['google_search']['kind']='private';state.save_run(run['root'],run)
        with self.assertRaises(ValueError): discovery_evidence.reconcile(run['root'],path)
        self.assertNotIn('discovery-channels',state.load_run(run['root'])['artifacts'])

    def test_unavailable_is_unknown_with_real_trace_and_explicit_fallback(self):
        path=journal(self.run);data=json.loads(path.read_text())
        row=data['attempts'][1];row.update(status='unavailable',reason='Public library login wall',trace_source_id='google_ads')
        del row['source_id']
        topic=data['public_research']['topics'][1];topic['conclusion']='unknown'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): discovery_evidence.reconcile(self.run['root'],path)
        row['fallback']={'reason':'Host search capability unavailable in this fixture; no bypass attempted'}
        path.write_text(json.dumps(data))
        report=discovery_evidence.reconcile(self.run['root'],path)
        self.assertEqual('PASS',report['status'],report)
        self.assertEqual('unknown',report['public_research']['topics'][1]['conclusion'])

    def test_native_plan_uses_real_cli_and_does_not_perform_a_search(self):
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result=subprocess.run([sys.executable,str(launcher),'discovery','research-plan',self.run['root']],capture_output=True,text=True)
        self.assertEqual(0,result.returncode,result.stderr)
        report=json.loads(result.stdout)
        task=json.loads(Path(report['native_task_path']).read_text())
        self.assertEqual(self.run['url'],task['url'])
        self.assertEqual(4,len(task['topics']))
        self.assertEqual({},state.load_run(self.run['root'])['metadata'].get('discovery_external_reports',{}))
