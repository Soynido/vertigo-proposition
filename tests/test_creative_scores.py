"""Nine cannot compensate a partial creative system or weak visual execution."""
import unittest
import test_state as fixtures
from proposition_runtime import state


class CreativeScoreTests(unittest.TestCase):
    setUp=fixtures.StateTests.setUp
    new_run=fixtures.StateTests.new_run
    write=fixtures.StateTests.write
    complete_run=fixtures.StateTests.complete_run
    stage_review=fixtures.StateTests.stage_review

    def test_nine_with_partial_creative_system_still_blocks(self):
        run=self.complete_run()
        self.stage_review(run,'creative.direction',scores=[2,2,2,1,2])
        report=state.stage_report(run['root'],'creative.direction')
        self.assertEqual(report['score'],9)
        self.assertEqual(report['status'],'BLOCKED')
        self.assertIn('stage_critical_score',{x['code'] for x in report['issues']})

    def test_nine_with_weak_client_visuals_still_blocks(self):
        run=self.complete_run()
        self.stage_review(run,'review.client',scores=[2,1,2,2,2])
        self.assertEqual(state.stage_report(run['root'],'review.client')['status'],'BLOCKED')

    def test_nine_with_partial_client_story_still_blocks(self):
        run=self.complete_run()
        self.stage_review(run,'client.composition',scores=[1,2,2,2,2])
        report=state.stage_report(run['root'],'client.composition')
        self.assertEqual(report['score'],9)
        self.assertEqual(report['status'],'BLOCKED')
        self.assertIn('stage_critical_score',{x['code'] for x in report['issues']})

    def test_complete_client_story_does_not_trigger_critical_score_issue(self):
        run=self.complete_run()
        self.stage_review(run,'client.composition',scores=[2,2,2,2,2])
        report=state.stage_report(run['root'],'client.composition')
        self.assertNotIn('stage_critical_score',{x['code'] for x in report['issues']})
