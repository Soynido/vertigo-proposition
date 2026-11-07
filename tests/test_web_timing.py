"""The complete run clock is never reset by a stage, retry or publication."""
from datetime import datetime,timedelta
from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch
from proposition_runtime import state,execution


class WebTimingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('proposition_runtime.web_timing'),'Web wall-time contract is missing')
        from proposition_runtime import web_timing
        self.timing=web_timing
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',delivery_format='web')
        self.start=datetime.fromisoformat(self.run['created_at'])

    def test_the_target_failure_remains_visible_within_the_qualification_ceiling(self):
        result=self.timing.budget(self.run,now=self.start+timedelta(seconds=701))
        self.assertEqual(result['target_status'],'FAIL')
        self.assertEqual(result['wall_seconds'],701)
        self.assertTrue(result['may_continue']);self.assertEqual(result['ceiling_remaining_seconds'],499)
        self.assertEqual(result['tokens_used'],None)

    def test_native_admission_time_is_included_in_the_immutable_run_clock(self):
        admitted=(self.start-timedelta(seconds=80)).isoformat()
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs',delivery_format='web',admitted_at=admitted)
        self.assertEqual(admitted,run['created_at'])
        self.assertEqual(80,self.timing.budget(run,now=self.start)['wall_seconds'])
        changed=dict(run,created_at=self.start.isoformat())
        with self.assertRaises(ValueError):state.save_run(run['root'],changed)

    def test_ceiling_prevents_new_work_without_mutating_the_run(self):
        host={'schema_version':'1.0','observed_at':self.run['created_at'],'host_kind':'synthetic_fixture',
              'capabilities':[{'id':'browser','status':'AVAILABLE'}]}
        path=Path(self.run['root'])/'state.json';before=path.read_bytes()
        with patch.object(self.timing,'utc_now',return_value=self.start+timedelta(seconds=1201)):
            listing=execution.ready_tasks(self.run['root'],host)
            self.assertEqual(listing['status'],'BLOCKED');self.assertEqual(listing['ready'],[])
            with self.assertRaises(ValueError):self.timing.require_time(self.run)
        self.assertEqual(before,path.read_bytes())

    def test_fixed_deadlines_do_not_change_the_task_fingerprint_when_time_passes(self):
        spec=next(s for s in execution._format_specs(self.run) if s['task_key']=='discovery.site.collect')
        parameters=execution._parameters(self.run,spec)
        self.assertEqual(datetime.fromisoformat(parameters['deadline_at']),self.start+timedelta(seconds=1200))
        later=dict(self.run);later['created_at']=(self.start+timedelta(seconds=100)).isoformat()
        with self.assertRaises(ValueError):state.save_run(self.run['root'],later)

    def test_a_claim_does_not_authorize_a_new_dispatch_after_the_complete_deadline(self):
        host={'schema_version':'1.0','observed_at':self.run['created_at'],'host_kind':'synthetic_fixture',
              'capabilities':[{'id':'browser','status':'AVAILABLE'}]}
        task=execution.ready_tasks(self.run['root'],host)['ready'][0]
        claim=execution.claim_task(self.run['root'],task['task_id'],task)
        event={'schema_version':'1.0','event_id':'evt-'+'a'*32,
            'attempt_id':claim['attempt']['attempt_id'],'kind':'dispatch_intent',
            'observed_at':self.run['created_at'],'evidence_ref':None,'payload':{'dispatch_key':'stable'}}
        with patch.object(self.timing,'utc_now',return_value=self.start+timedelta(seconds=1201)):
            with self.assertRaisesRegex(ValueError,'ceiling exceeded'):execution.task_event(self.run['root'],event)


if __name__=='__main__':unittest.main()
