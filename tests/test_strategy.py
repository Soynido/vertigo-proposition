"""Handoff omission/tampering is refused by actual files and stage consumers."""
import copy
import importlib
import json
from pathlib import Path
import unittest
import test_state as fixtures
from strategy_fixture import make_analysis
from proposition_runtime import state


class StrategyTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StateTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.run=self.fixture.new_run()
        from discovery_fixture import install_discovery
        install_discovery(self.run)

    def api(self):
        try: return importlib.import_module('proposition_runtime.strategy')
        except ImportError: self.fail('Missing canonical strategic handoff consumer')

    def test_proposed_missions_have_their_own_draft_without_fabricated_outcomes(self):
        api=self.api();self.assertTrue(callable(getattr(api,'validate_draft',None)),'Prepared missions still require fabricated actual outcomes')
        path=make_analysis(self.run);data=json.loads(path.read_text());missions=[]
        for mission in data['missions']:
            missions.append({k:v for k,v in mission.items() if k in ('id','need_ids','target','task','success','stop','source_ids')}|{'depends_on':[]})
        draft={'schema_version':'1.0','handoff_version':data['version'],'methods':data['methods'],'audiences':data['audiences'],'needs':data['needs'],'proposed_missions':missions,'unknowns':data['unknowns']}
        refs=api.validate_draft(state.load_run(self.run['root']),draft);self.assertTrue(refs);self.assertNotIn('observation-analysis-map',state.load_run(self.run['root'])['artifacts'])
        bad=copy.deepcopy(draft);bad['proposed_missions'][0]['outcome']='completed'
        with self.assertRaises(ValueError):api.validate_draft(state.load_run(self.run['root']),bad)
        bad=copy.deepcopy(draft);bad['proposed_missions'][0]['depends_on']=[bad['proposed_missions'][0]['id']]
        with self.assertRaises(ValueError):api.validate_draft(state.load_run(self.run['root']),bad)

    def test_mission_outcome_must_match_the_prepared_task_and_current_proof(self):
        api=self.api();self.assertTrue(callable(getattr(api,'validate_mission',None)),'A mission result is not bound to its prepared task')
        data=json.loads(make_analysis(self.run).read_text());mission=data['missions'][0];planned={k:v for k,v in mission.items() if k in ('id','need_ids','target','task','success','stop','source_ids')}|{'depends_on':[]}
        draft={'proposed_missions':[planned]};run=state.load_run(self.run['root']);self.assertTrue(api.validate_mission(run,draft,mission['id'],mission))
        for field,value in [('task','Different easy task'),('source_ids',[])]:
            bad=copy.deepcopy(mission);bad[field]=value
            with self.assertRaises(ValueError):api.validate_mission(run,draft,mission['id'],bad)

    def test_missing_handoff_blocks_analysis_and_downstream(self):
        for stage in ('analysis.specialists','company.v2','brief.public'):
            report=state.stage_report(self.run['root'],stage)
            self.assertIn('audience_handoff',{x['code'] for x in report['issues']})

    def test_reading_methods_and_public_only_application_are_required(self):
        api=self.api();path=make_analysis(self.run);good=json.loads(path.read_text())
        for field,value in [('methods',[]),('audiences',[]),('needs',[])]:
            bad=copy.deepcopy(good);bad[field]=value;path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):api.register(self.run['root'],path)
        bad=copy.deepcopy(good);bad['audiences'][0]['status']='validated_priority_ICP';path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):api.register(self.run['root'],path)
        bad=copy.deepcopy(good);bad['methods'][0]['read_sections']=[];path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):api.register(self.run['root'],path)
        path.write_text(json.dumps(good));self.assertEqual('PASS',api.register(self.run['root'],path)['status'])

    def test_need_without_actual_mission_or_consequence_is_refused(self):
        api=self.api();path=make_analysis(self.run);good=json.loads(path.read_text())
        for change in ('no_mission','no_consequence','false_completion'):
            bad=copy.deepcopy(good)
            if change=='no_mission':bad['needs'][0]['mission_ids']=[]
            elif change=='no_consequence':bad['needs'][0]['experience_consequence']=''
            else:bad['missions'][0]['source_ids']=[]
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):api.register(self.run['root'],path)

    def test_model_and_brief_receive_same_status_and_consequence_with_dependencies(self):
        api=self.api();path=make_analysis(self.run);api.register(self.run['root'],path)
        summary=api.summary(json.loads(path.read_text()));root=Path(self.run['root'])
        (root/'company.json').write_text(json.dumps(dict(audience_need_summary=summary)))
        state.add_artifact(root,'company-evidence-brief','company.json','internal',['artifact:observation-analysis-map'])
        self.assertEqual('PASS',api.inspect(state.load_run(root),'company.v2')['status'])
        brief=dict(audience_need_summary=summary,observations=[dict(id='o1',need_ids=['n1'],decision='retained',proof='source:strategy-source')])
        (root/'brief.json').write_text(json.dumps(brief))
        state.add_artifact(root,'creative-inputs','brief.json','public',['artifact:company-evidence-brief'])
        self.assertEqual('PASS',api.inspect(state.load_run(root),'brief.public')['status'])
        brief['audience_need_summary']['audiences'][0]['status']='declared'
        (root/'brief.json').write_text(json.dumps(brief));state.add_artifact(root,'creative-inputs','brief.json','public',['artifact:company-evidence-brief'])
        self.assertEqual('BLOCKED',api.inspect(state.load_run(root),'brief.public')['status'])

    def test_raw_presence_without_dependency_and_stale_sources_do_not_pass(self):
        api=self.api();path=make_analysis(self.run);api.register(self.run['root'],path)
        root=Path(self.run['root']);(root/'company.json').write_text(json.dumps(dict(audience_need_summary=api.summary(json.loads(path.read_text())))))
        state.add_artifact(root,'company-evidence-brief','company.json','internal')
        self.assertEqual('BLOCKED',api.inspect(state.load_run(root),'company.v2')['status'])
        (root/'strategy-source.txt').write_text('changed')
        self.assertEqual('BLOCKED',api.inspect(state.load_run(root),'analysis.specialists')['status'])
