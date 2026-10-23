"""A hero alone, token method names or a removed conversion action cannot promote."""
import json
from pathlib import Path
import tempfile
import unittest
from proposition_runtime import state
from creative_fixture import make_outputs
from experience_fixture import prepare_experience,write_artifact,install_story


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs')
        self.root=Path(self.run['root']);prepare_experience(self.run)

    def check(self,stage='creative.direction'):
        from proposition_runtime.experience import inspect_experience
        return inspect_experience(state.load_run(self.root),stage)

    def mutate(self,name,transform):
        p=self.root/(name+'.json');d=json.loads(p.read_text());transform(d)
        write_artifact(self.run,name,name+'.json',d)

    def test_three_rendered_beats_mobile_and_named_methods_pass_evidence_check(self):
        self.assertEqual(self.check()['status'],'PASS')

    def test_desktop_hero_and_mobile_only_are_insufficient(self):
        self.mutate('creative-experience',lambda d:d['directions'][0].update(moments=d['directions'][0]['moments'][:1]))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_missing_upstream_application_blocks_even_with_three_scenes(self):
        self.mutate('creative-experience',lambda d:d.update(method_applications=d['method_applications'][:1]))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_identical_images_do_not_prove_a_scroll_progression(self):
        self.mutate('creative-experience',lambda d:d['directions'][0]['moments'][1].update(render_ref='artifact:scene-opening'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_claimed_live_animation_needs_its_test_evidence(self):
        self.mutate('creative-experience',lambda d:d['directions'][0].update(motion_status='implemented'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_existing_primary_action_cannot_silently_be_removed(self):
        self.mutate('creative-experience',lambda d:d['directions'][0].update(actions=[]))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_replacing_direct_action_with_a_category_page_needs_explicit_approval(self):
        self.mutate('creative-experience',lambda d:d['directions'][0]['actions'][0].update(target='https://fixture.example/products'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_tiny_mobile_action_text_blocks(self):
        self.mutate('creative-experience',lambda d:d['directions'][0]['mobile'].update(action_text_px=9))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_changed_inputs_invalidate_a_previously_prepared_direction(self):
        self.mutate('creative-inputs',lambda d:d.update(revision='r2'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_source_mutation_blocks_without_reregistering_the_plan(self):
        (self.root/'observation.txt').write_text('Changed source facts')
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_composition_requires_story_evidence_and_an_agency_next_step(self):
        self.assertEqual(self.check('client.composition')['status'],'BLOCKED')
        install_story(self.run);make_outputs(self.root)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        # Correct page count of fixture story so this case isolates missing mission.
        self.mutate('client-story',lambda d:([row.update(page=1) for row in d['pages']],d['observation_decisions'][0].update(page=1)))
        self.assertEqual(self.check('client.composition')['status'],'PASS')
        self.mutate('client-story',lambda d:d.update(pages=[r for r in d['pages'] if r['role']!='agency_value']))
        self.assertEqual(self.check('client.composition')['status'],'BLOCKED')

    def test_stage_report_blocks_missing_creative_graph(self):
        report=state.stage_report(self.root,'creative.direction')
        # Remove the graph after a valid local registration, not merely a low score.
        (self.root/'creative-experience.json').unlink()
        report=state.stage_report(self.root,'creative.direction')
        self.assertIn('creative_experience',{x['code'] for x in report['issues']})

    def test_scroll_order_cannot_start_with_the_action_and_end_with_the_opening(self):
        self.mutate('creative-experience',lambda d:(d['directions'][0]['moments'][0].update(role='action'),d['directions'][0]['moments'][-1].update(role='opening'),d['directions'][0]['actions'][0].update(moment_id='opening')))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_native_method_claim_needs_an_actual_execution_receipt(self):
        self.mutate('creative-experience',lambda d:d['method_applications'][0].update(mode='native'))
        self.assertEqual(self.check()['status'],'BLOCKED')

    def test_method_entrypoint_without_complete_cache_receipt_blocks(self):
        inputs=json.loads((self.root/'creative-inputs.json').read_text())
        receipt=Path(inputs['methods'][0]['reference_root']).parent/'receipt.json'
        receipt.unlink(missing_ok=True)
        self.assertEqual(self.check()['status'],'BLOCKED')
