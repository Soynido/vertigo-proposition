"""Client-only removes internal outputs, never the applicable quality gates."""
import unittest
import test_state as fixtures
from proposition_runtime import state


class ClientScopeTests(unittest.TestCase):
    setUp=fixtures.StateTests.setUp
    write=fixtures.StateTests.write
    complete_run=fixtures.StateTests.complete_run
    stage_review=fixtures.StateTests.stage_review
    # Reuse the existing real evidence fixture, not mocks or invented PASS defaults.
    def new_run(self):
        return state.init_run('https://fixture.example/',self.base/'runs',{
            'actor':'operator','responsible':'project-owner','responsible_confirmed':True,
            'required_reviewers':['review-a','review-b'],'parameters':{'delivery_scope':'client'}})

    def test_client_scope_passes_without_internal_handoffs_or_publication(self):
        run=self.complete_run()
        for row in state._requirements():
            if row['stage_id']=='internal.handoffs':run['evaluations'].pop(row['id'],None)
        run['stage_reviews'].pop('internal.handoffs',None)
        state.save_run(run['root'],run)
        report=state.validate_run(run['root'])
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertEqual(report['scope'],'client')
        self.assertNotIn('internal.handoffs',report['stages'])

    def test_client_scope_still_blocks_a_missing_source_or_analysis_gate(self):
        run=self.complete_run();run['stage_reviews'].pop('analysis.specialists');state.save_run(run['root'],run)
        self.assertEqual(state.validate_run(run['root'])['status'],'BLOCKED')
        self.assertEqual(state.next_stage(run['root'])['stage_id'],'analysis.specialists')

    def test_next_stage_never_treats_a_sidecar_note_as_a_registered_review(self):
        run=self.new_run();self.write(run,'stage-notes.json','{"score":10,"status":"PASS"}')
        report=state.next_stage(run['root'])
        self.assertEqual(report['status'],'BLOCKED')
        self.assertEqual(report['stage_id'],'discovery.site')

    def test_unknown_scope_is_rejected_instead_of_disabling_gates(self):
        with self.assertRaises(ValueError):
            state.init_run('https://fixture.example/',self.base/'other',{'parameters':{'delivery_scope':'anything'}})
