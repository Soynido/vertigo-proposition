"""Explicit V2 projection; V1 evidence never silently migrates."""
import inspect
import json
from pathlib import Path
import unittest
import test_state as fixtures
from discovery_fixture import install_discovery
from strategy_fixture import make_analysis
from proposition_runtime import state, strategy


class MissionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.assertIn('audience_handoff_contract', inspect.signature(state.init_run).parameters,
                      'Explicit versioned handoff initialization is missing')
        self.fixture=fixtures.StateTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.run=state.init_run('https://example.test/',self.fixture.base/'runs',audience_handoff_contract=2)
        self.root=Path(self.run['root']);install_discovery(self.run)
        self.path=make_analysis(self.run);self.data=json.loads(self.path.read_text());self.data['version']=2
        self.data['missions'][0].update(outcome='blocked',reason='Le contenu différé est inaccessible',limits='Aucune préférence utilisateur démontrée')
        self.path.write_text(json.dumps(self.data))

    def project(self):
        self.assertEqual('PASS',strategy.register(self.root,self.path)['status'])
        summary=strategy.summary(self.data)
        (self.root/'company.json').write_text(json.dumps({'audience_need_summary':summary}))
        state.add_artifact(self.root,'company-evidence-brief','company.json','internal',['artifact:observation-analysis-map'])
        brief={'audience_need_summary':summary,'observations':[{'id':'o1','need_ids':['n1'],'decision':'retained','proof':'source:strategy-source'}]}
        (self.root/'brief.json').write_text(json.dumps(brief))
        state.add_artifact(self.root,'creative-inputs','brief.json','public',['artifact:company-evidence-brief'])
        return brief

    def test_blocked_mission_limits_reach_model_and_brief(self):
        brief=self.project();summary=brief['audience_need_summary']
        self.assertEqual(2,summary['version'])
        self.assertEqual(['m1'],summary['needs'][0]['mission_ids'])
        mission=summary['missions'][0]
        self.assertEqual('blocked',mission['outcome'])
        self.assertEqual(self.data['missions'][0]['reason'],mission['reason'])
        self.assertEqual(self.data['missions'][0]['limits'],mission['limits'])
        self.assertTrue(any(mission['reason'] in u and mission['limits'] in u for u in summary['unknowns']))
        self.assertNotIn('methods',summary)
        self.assertNotIn('task',mission)
        self.assertEqual('PASS',strategy.inspect(state.load_run(self.root))['status'])

    def test_dropped_or_weakened_mission_in_brief_is_blocked(self):
        brief=self.project();brief['audience_need_summary']['missions'][0]['limits']='Sans réserve'
        (self.root/'brief.json').write_text(json.dumps(brief));state.add_artifact(self.root,'creative-inputs','brief.json','public',['artifact:company-evidence-brief'])
        self.assertEqual('BLOCKED',strategy.inspect(state.load_run(self.root))['status'])

    def test_v1_contract_and_projection_remain_unchanged(self):
        run=state.init_run('https://example.test/',self.fixture.base/'legacy',audience_handoff_contract=1)
        install_discovery(run);path=make_analysis(run);data=json.loads(path.read_text());data['version']=1;path.write_text(json.dumps(data))
        self.assertEqual('PASS',strategy.register(run['root'],path)['status'])
        self.assertNotIn('missions',strategy.summary(data));self.assertNotIn('version',strategy.summary(data))
        self.assertEqual(1,state.load_run(run['root'])['metadata']['audience_handoff_contract'])

    def test_report_version_cannot_be_downgraded_or_boolean(self):
        for version in (1,True,False,0,3,'2'):
            with self.subTest(version=version):
                data={**self.data,'version':version};self.path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):strategy.register(self.root,self.path)

    def test_v2_contract_cannot_be_removed_or_changed_after_initialization(self):
        for version in (1,None,True,3):
            with self.subTest(version=version):
                run=state.load_run(self.root);run['metadata']['audience_handoff_contract']=version
                with self.assertRaises(ValueError):state.save_run(self.root,run)

    def test_new_run_defaults_to_mission_aware_contract(self):
        run=state.init_run('https://example.test/',self.fixture.base/'default')
        self.assertEqual(2,run['metadata']['audience_handoff_contract'])

    def test_v2_stage_review_still_requires_its_current_consumer(self):
        self.project()
        (self.root/'unrelated.txt').write_text('Synthetic unrelated proof')
        record=state.add_artifact(self.root,'unrelated','unrelated.txt','internal')
        self.fixture.stage_review(state.load_run(self.root),'analysis.specialists',
                                  reviewed={'artifact:unrelated':record['sha256']})
        report=state.stage_report(self.root,'analysis.specialists')
        self.assertTrue(any(x['code']=='audience_handoff' and 'current audience/need consumer' in x['message'] for x in report['issues']),report)

    def test_generated_limits_do_not_displace_existing_unknowns(self):
        self.data['unknowns']=['Unknown '+str(i) for i in range(100)]
        error=None
        try:
            summary=strategy.summary(self.data)
        except ValueError as caught:
            error=caught
        self.assertIsNone(error)
        self.assertEqual(101,len(summary['unknowns']))

    def test_registration_returns_the_exact_public_projection(self):
        result=strategy.register(self.root,self.path)
        self.assertEqual(strategy.summary(self.data),result.get('audience_need_summary'))
