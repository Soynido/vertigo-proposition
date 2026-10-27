"""A commercial role list cannot replace a prior plan or current client handoff."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from proposition_runtime import state
from proposition_runtime.experience import inspect_experience
from experience_fixture import prepare_experience, write_artifact, install_story
from creative_fixture import make_outputs
from composition_fixture import prepare_plan, register_client

LAUNCHER = Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run = state.init_run('https://fixture.example/', Path(self.tmp.name)/'runs')
        self.root = Path(self.run['root'])

    def approve(self, success=True):
        result = subprocess.run([sys.executable, str(LAUNCHER), 'check-experience',
            str(self.root), '--composition-plan-only'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode == 0, success, result.stdout+result.stderr)
        self.assertTrue(result.stdout.strip().startswith('{'), result.stdout+result.stderr)
        return json.loads(result.stdout)

    def change_plan(self, change):
        path = self.root/'client-story-map.json'
        data = json.loads(path.read_text()); change(data)
        write_artifact(self.run, 'client-story-map', path.name, data)

    def test_old_eight_roles_cannot_promote_new_kit_without_prior_visual_plan(self):
        prepare_experience(self.run); install_story(self.run); make_outputs(self.root)
        state.add_artifact(self.root, 'client-pdf', 'client.pdf', 'client')
        data = json.loads((self.root/'client-story.json').read_text())
        for row in data['pages']: row['page'] = 1
        data['observation_decisions'][0]['page'] = 1
        write_artifact(self.run, 'client-story', 'client-story.json', data)
        report = inspect_experience(state.load_run(self.root), 'client.composition')
        self.assertEqual(report['status'], 'BLOCKED', report)

    def test_new_runs_pin_sales_contract_against_profile_downgrade(self):
        run = state.load_run(self.root)
        self.assertEqual(run['metadata'].get('sales_kit_contract'), 1)
        run['metadata'].pop('sales_kit_contract')
        with self.assertRaises(ValueError): state.save_run(self.root, run)

    def test_historical_registration_keeps_its_original_dependency_scope(self):
        # Model a pre-contract persisted run; this is not a supported downgrade API.
        path = self.root/'state.json'; old = json.loads(path.read_text())
        old['metadata'].pop('sales_kit_contract'); path.write_text(json.dumps(old))
        (self.root/'client.html').write_text('Historical client source.')
        state.add_artifact(self.root, 'client-source', 'client.html', 'client')
        (self.root/'sales.md').write_text('Historical independently registered evidence.')
        state.add_artifact(self.root, 'sales-pdf', 'sales.md', 'sales')
        (self.root/'client.html').write_text('Changed old source.')
        state.invalidate_changed(self.root)
        self.assertEqual(state.load_run(self.root)['artifacts']['sales-pdf']['status'], 'CURRENT')

    def test_prior_plan_passes_without_final_pdf_and_can_share_one_page(self):
        prepare_plan(self.run)
        report = self.approve()
        self.assertEqual(report['status'], 'PASS')
        self.assertFalse((self.root/'client.pdf').exists())
        self.assertIn('composition-plan-review', state.load_run(self.root)['artifacts'])

    def test_plan_omission_blocks_despite_all_old_role_names(self):
        prepare_plan(self.run)
        self.change_plan(lambda d: d.update(coverage=[r for r in d['coverage'] if r['id'] != 'K03']))
        self.assertEqual(self.approve(False)['status'], 'BLOCKED')

    def test_missing_measurement_or_mission_conditions_blocks(self):
        original = prepare_plan(self.run)
        for role, field in [('K06', 'measurement'), ('K07', 'mission')]:
            with self.subTest(role=role):
                data = json.loads(json.dumps(original))
                next(r for r in data['coverage'] if r['id'] == role).pop(field)
                write_artifact(self.run, 'client-story-map', 'client-story-map.json', data)
                self.assertEqual(self.approve(False)['status'], 'BLOCKED')

    def test_plan_cannot_self_exempt_a_required_sales_function(self):
        prepare_plan(self.run)
        self.change_plan(lambda d: d['coverage'][6].update(status='NOT_APPLICABLE',
            reason='Author wants only creative validation'))
        self.assertEqual(self.approve(False)['status'], 'BLOCKED')

    def test_late_plan_cannot_cover_outputs_already_created_but_unregistered(self):
        prepare_plan(self.run)
        (self.root/'client.pdf').write_bytes(b'Already manufactured')
        self.assertEqual(self.approve(False)['status'], 'BLOCKED')
        self.assertNotIn('composition-plan-review', state.load_run(self.root)['artifacts'])

    def test_private_or_missing_proof_cannot_enter_the_public_plan(self):
        prepare_plan(self.run)
        state.add_source(self.root, 'private', self.root/'observation.txt', kind='private', audience='public')
        self.change_plan(lambda d: d['coverage'][0].update(proof='source:private'))
        self.assertEqual(self.approve(False)['status'], 'BLOCKED')

    def test_current_plan_and_exact_final_coverage_can_pass_evidence_gate(self):
        plan = prepare_plan(self.run); self.approve(); make_outputs(self.root); register_client(self.run)
        install_story(self.run)
        data = json.loads((self.root/'client-story.json').read_text())
        for row in data['pages']: row['page'] = 1
        data['observation_decisions'][0]['page'] = 1
        data['kit_coverage'] = [{'id': r['id'], 'page': 1, 'anchor': r['anchor']} for r in plan['coverage']]
        write_artifact(self.run, 'client-story', 'client-story.json', data)
        result = inspect_experience(state.load_run(self.root), 'client.composition')
        self.assertEqual(result['status'], 'PASS', result)
        data['kit_coverage'].pop()
        write_artifact(self.run, 'client-story', 'client-story.json', data)
        self.assertEqual(inspect_experience(state.load_run(self.root), 'client.composition')['status'], 'BLOCKED')

    def test_plan_reapproval_is_idempotent_without_backdating_a_new_decision(self):
        prepare_plan(self.run); self.approve()
        before = state.load_run(self.root)['artifacts']['composition-plan-review']
        self.approve()
        self.assertEqual(state.load_run(self.root)['artifacts']['composition-plan-review'], before)

    def test_client_and_sales_bind_real_dependencies_and_invalidate_on_change(self):
        prepare_plan(self.run); self.approve(); register_client(self.run)
        write_artifact(self.run, 'client-story', 'client-story.json', {'note': 'Fictional final story'})
        (self.root/'sales.md').write_text('Explain the current scoped mission.')
        state.add_artifact(self.root, 'sales-playbook', 'sales.md', 'sales')
        run = state.load_run(self.root)
        self.assertIn('artifact:client-source', run['artifacts']['sales-playbook']['dependencies'])
        self.assertIn('artifact:composition-plan-review', run['artifacts']['client-pdf']['dependencies'])
        (self.root/'client.html').write_text('A changed mission and next decision.')
        invalid = state.invalidate_changed(self.root)['invalidated']
        self.assertIn('artifact:sales-playbook', invalid)
        self.assertIn('artifact:client-pdf', invalid)

    def test_unrelated_artifact_does_not_stale_client_or_sales(self):
        prepare_plan(self.run); self.approve(); register_client(self.run)
        write_artifact(self.run, 'client-story', 'client-story.json', {'note': 'Fictional final story'})
        (self.root/'sales.md').write_text('Scoped mission.')
        state.add_artifact(self.root, 'sales-playbook', 'sales.md', 'sales')
        (self.root/'unrelated.txt').write_text('Independent evidence.')
        state.add_artifact(self.root, 'unrelated', 'unrelated.txt', 'internal')
        (self.root/'unrelated.txt').write_text('Changed independently.')
        invalid = state.invalidate_changed(self.root)['invalidated']
        self.assertNotIn('artifact:client-pdf', invalid)
        self.assertNotIn('artifact:sales-playbook', invalid)

    def test_full_score_review_cannot_ignore_the_current_kit_packet(self):
        prepare_plan(self.run)
        state.record_stage_review(self.root, 'client.composition', {
            'reviewer_id': 'review-a', 'status': 'PASS', 'scores': [2,2,2,2,2],
            'evidence': ['artifact:deck-plan'], 'unknowns': [],
            'criterion_evidence': {name: ['artifact:deck-plan'] for name in
                ('story','language','balance','demonstration','privacy')}})
        report = state.stage_report(self.root, 'client.composition')
        self.assertIn('kit_review_packet', {row['code'] for row in report['issues']})

    def test_an_early_internal_pdf_cannot_hide_behind_current_handoff_documents(self):
        from proposition_runtime.composition import handoff_issues
        (self.root/'early-sales.pdf').write_text('Old unbound internal export.')
        state.add_artifact(self.root, 'sales-pdf', 'early-sales.pdf', 'sales')
        prepare_plan(self.run); self.approve(); register_client(self.run)
        write_artifact(self.run, 'client-story', 'client-story.json', {'note': 'Fictional story'})
        for identifier in ('sales-playbook', 'follow-up-register', 'technical-handoff'):
            (self.root/(identifier+'.md')).write_text('Current scoped client mission.')
            state.add_artifact(self.root, identifier, identifier+'.md', 'internal')
        self.assertTrue(any('sales-pdf' in issue for issue in handoff_issues(state.load_run(self.root))))
        state.add_artifact(self.root, 'sales-pdf', 'early-sales.pdf', 'sales')
        self.assertFalse(handoff_issues(state.load_run(self.root)))

    def test_client_only_context_still_needs_current_client_dependencies(self):
        from proposition_runtime.composition import handoff_issues
        self.run = state.init_run('https://fixture.example/', Path(self.tmp.name)/'client-runs',
                                  {'parameters': {'delivery_scope': 'client'}})
        self.root = Path(self.run['root'])
        (self.root/'context.md').write_text('Early unbound context.')
        state.add_artifact(self.root, 'client-context', 'context.md', 'client')
        prepare_plan(self.run); self.approve(); register_client(self.run)
        write_artifact(self.run, 'client-story', 'client-story.json', {'note': 'Fictional story'})
        self.assertTrue(any('client-context' in issue for issue in handoff_issues(state.load_run(self.root))))
        state.add_artifact(self.root, 'client-context', 'context.md', 'client')
        self.assertFalse(handoff_issues(state.load_run(self.root)))

    def test_changed_plan_invalidates_the_approval_and_dependent_exports(self):
        prepare_plan(self.run); self.approve(); register_client(self.run)
        self.change_plan(lambda d: d.update(revision='changed-after-pilot'))
        invalid = state.invalidate_changed(self.root)['invalidated']
        self.assertIn('artifact:composition-plan-review', invalid)
        self.assertIn('artifact:client-pdf', invalid)
