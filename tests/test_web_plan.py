"""The experience plan is frozen before implementation, not reconstructed at export."""
import json
from pathlib import Path
import tempfile
import unittest
from proposition_runtime import state,web
from web_fixture import prepare_web


class WebPlanTests(unittest.TestCase):
    def test_a_scene_or_action_cannot_hide_on_an_unpublished_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp)
            data=json.loads(plan.read_text());data['scenes'][0]['page']='unpublished.html'
            with self.assertRaisesRegex(ValueError,'public HTML'):
                web.validate_plan(state.load_run(run['root']),data,source)

    def test_builder_requires_a_real_predevelopment_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);root=Path(run['root'])
            current=state.load_run(root);current['metadata'].pop('web_plan',None)
            state.save_run(root,current)
            with self.assertRaisesRegex(ValueError,'pre-development'):
                web.build_run(root,source,plan)

    def test_first_plan_cannot_regularize_an_already_written_homepage(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);root=Path(run['root'])
            self.assertTrue(callable(getattr(web,'plan_run',None)),'No pre-development plan operation')
            current=state.load_run(root);current['metadata'].pop('web_plan',None)
            current['artifacts'].pop('web-plan',None);state.save_run(root,current)
            with self.assertRaisesRegex(ValueError,'before.*homepage'):
                web.plan_run(root,source,plan)

    def test_plan_is_immutable_reused_and_explicitly_revised_without_a_new_creative_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);root=Path(run['root'])
            current=state.load_run(root)
            self.assertIn('web_plan',current['metadata'],'Fixture did not pass through a real plan registration')
            first=current['metadata']['web_plan'];selection=current['metadata']['creative_selection']
            row=current['artifacts']['web-plan'];frozen=root/row['path'];old=frozen.read_bytes()
            web.plan_run(root,source,plan)
            self.assertEqual(state.load_run(root)['metadata']['web_plan'],first)
            data=json.loads(plan.read_text());data['coverage'][0]['meaning']='A clearer sourced opening'
            plan.write_text(json.dumps(data))
            with self.assertRaises(ValueError):web.build_run(root,source,plan)
            with self.assertRaises(ValueError):web.plan_run(root,source,plan)
            web.plan_run(root,source,plan,supersedes=first['sha256'],reason='Clarify the opening, preserve the concept')
            current=state.load_run(root)
            self.assertEqual(frozen.read_bytes(),old)
            self.assertEqual(current['metadata']['creative_selection'],selection)
            self.assertEqual(current['metadata']['web_plan']['parent_sha256'],first['sha256'])
            self.assertEqual(web.build_run(root,source,plan)['status'],'PASS')

    def test_delivered_origin_requires_a_root_index_not_a_file_only_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);data=json.loads(plan.read_text())
            data['entrypoint']='proposal.html';data['public_files'].remove('index.html');data['public_files'].append('proposal.html')
            (source/'index.html').rename(source/'proposal.html')
            with self.assertRaisesRegex(ValueError,'index.html'):
                web.build_bundle(source,Path(tmp)/'candidate',data)


if __name__=='__main__':unittest.main()
