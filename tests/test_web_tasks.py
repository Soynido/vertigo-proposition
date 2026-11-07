"""The optional task protocol must route web work, not request documentary exports."""
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime,timezone
from proposition_runtime import execution,state
from web_fixture import prepare_web


class WebTaskTests(unittest.TestCase):
    def test_an_empty_web_run_can_start_discovery_before_creative_inputs_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=state.init_run('https://fixture.example/',Path(tmp)/'runs',delivery_format='web')
            host={'schema_version':'1.0','observed_at':datetime.now(timezone.utc).isoformat(),
                'host_kind':'synthetic_fixture','capabilities':[{'id':'browser','status':'AVAILABLE'}]}
            before=(Path(run['root'])/'state.json').read_bytes()
            result=execution.ready_tasks(run['root'],host)
            self.assertEqual(result['ready'][0]['task_key'],'discovery.site.collect')
            self.assertEqual(before,(Path(run['root'])/'state.json').read_bytes())

    def test_web_tasks_keep_creator_continuity_and_format_specific_reviewer_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,_,_=prepare_web(tmp);specs=execution._variants(state.load_run(run['root']))
            self.assertFalse(any(s['stage_id']=='internal.handoffs' for s in specs))
            for spec in specs:
                self.assertFalse({'client-pdf','client-pptx','presentation-catalog'} & set(spec['inputs']),spec['task_key'])
                self.assertFalse({'client-pdf','client-pptx'} & set(spec['outputs']),spec['task_key'])
            by_key={s['task_key']:s for s in specs}
            for key in ('client.composition.plan','client.composition.build'):
                self.assertEqual(by_key[key]['isolation'],'continue_public')
                self.assertEqual(by_key[key]['packet'],'creative_public')
            for key in ('review.client.review_a','review.client.review_b'):
                self.assertEqual(by_key[key]['isolation'],'independent_review')
                self.assertTrue({'web-build','web-plan','web-inspection','web-sources'}.issubset(by_key[key]['inputs']))

    def test_web_source_destinations_reserved_at_planning_are_retained_at_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,_,_=prepare_web(tmp);specs={s['task_key']:s for s in execution._variants(state.load_run(run['root']))}
            reserved=execution._destinations(run,specs['client.composition.plan'],'plan-attempt')
            self.assertIn('web-source',reserved);self.assertIn('web-material',reserved)
            outputs={name:reserved[name] for name in ('web-source','web-material')}
            path=Path(run['root'])/'reserved-web-plan.json';path.write_text(json.dumps({'outputs':outputs}))
            state.add_artifact(run['root'],'web-plan',path,'internal')
            current=state.load_run(run['root'])
            built=execution._destinations(current,specs['client.composition.build'],'different-build-attempt')
            self.assertEqual({k:built[k] for k in outputs},outputs)
            request={'input_parameters':{'delivery_format':'web'},'output_destinations':reserved}
            execution._check_future_outputs(request,{'outputs':outputs})
            changed=dict(outputs,**{'web-source':'outputs/elsewhere/index.html'})
            with self.assertRaises(ValueError):execution._check_future_outputs(request,{'outputs':changed})


if __name__=='__main__':unittest.main()
