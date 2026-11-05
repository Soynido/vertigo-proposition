"""URL-only web runs must not fabricate human input approvals or expose private leaves."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from proposition_runtime import state,web,execution,transactions,cli
from web_fixture import prepare_web,assess_web_fixture


class WebPublicPacketTests(unittest.TestCase):
    def test_web_context_projects_verified_public_inputs_without_a_human_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp,complete_evidence=True);root=Path(run['root'])
            web.build_run(root,source,plan);web.inspect_run(root);assess_web_fixture(run)
            before=state.load_run(root)
            selected=['creative-inputs']+['method-'+name for name in ['claude-seo','impeccable','scroll-craft','apple-design']]
            self.assertTrue(all(before['artifacts'][name]['approval'] is None for name in selected))
            release_result=cli.execute(cli.parser().parse_args(['web','release',str(root)]))
            self.assertEqual(release_result['status'],'PREPARED')
            result=state.build_context_packet(root,Path(tmp)/'public-context',selected)
            self.assertEqual(result['status'],'PREPARED')
            self.assertEqual(len(result['files']),5)
            current=state.load_run(root)
            self.assertTrue(all(current['artifacts'][name]['approval'] is None for name in selected))
            release=current['artifacts']['public-input-release']
            data=json.loads((root/release['path']).read_text())
            self.assertEqual(data['authority'],'verified_public_source_projection')
            self.assertNotIn('human_approved',data)
            # The optional host protocol must use that same release and ship
            # executable mechanisms, not just a path to a maintainer's files.
            spec=next(s for s in execution._format_specs(current) if s['task_key']=='creative.direction.prepare')
            with patch.object(execution,'_method_files',return_value=({},[])):
                task=execution._plan(current,spec,execution._parameters(current,spec))
                self.assertEqual({current['artifacts'][name]['path'] for name in selected},
                    {d['path'] for d in task['packet_plan']['files']})
                destination=root/'.execution/inputs/fixture-public';destination.mkdir(parents=True)
                packet=execution._freeze_packet(root,destination,current,task,spec)
            self.assertTrue(any(d['path'].endswith('/resources/web/motion.mjs') for d in packet['files']))
            native=json.loads((destination/'native-task.json').read_text())
            copied=native['input_artifacts']['artifact:creative-inputs']
            self.assertEqual((root/copied['path']).read_bytes(),(root/current['artifacts']['creative-inputs']['path']).read_bytes())
            self.assertIn('source:experience-source',native['public_evidence'])
            self.assertFalse(any('path' in row for row in native['public_evidence'].values()))
            contracts=transactions.contract_hashes()
            self.assertTrue(any(name.endswith('/resources/web/motion.mjs') for name in contracts))
            # The two reviewers receive the actual frozen served files and
            # captures, and the correct web rubric, never only JSON claims.
            spec=next(s for s in execution._variants(current) if s['task_key']=='review.client.review_a')
            with patch.object(execution,'_method_files',return_value=({},[])):
                task=execution._plan(current,spec,execution._parameters(current,spec))
                destination=root/'.execution/inputs/fixture-review';destination.mkdir(parents=True)
                packet=execution._freeze_packet(root,destination,current,task,spec)
            paths={d['path'] for d in packet['files']}
            self.assertTrue(any('/.vercel/output/static/index.html' in name for name in paths))
            self.assertTrue(any(name.endswith('.png') for name in paths))
            native=json.loads((destination/'native-task.json').read_text())
            self.assertNotIn('client-pdf',json.dumps(native['adoption_contract']['rubric']))
            # Adding a file with private provenance cannot expand this release,
            # even if an actor writes the old approval-shaped local metadata.
            secret=root/'private-source.txt';secret.write_text('PRIVATE_SENTINEL')
            state.add_source(root,'private-source',secret,kind='private',audience='internal')
            row=state.add_artifact(root,'private-asset',secret,'client',['source:private-source'])
            current=state.load_run(root);current['artifacts']['private-asset'].update(public_allowed=True,
                approval={'actor':'fixture-owner','sha256':row['sha256']})
            state.save_run(root,current)
            with self.assertRaises(ValueError):
                state.build_context_packet(root,Path(tmp)/'leak',selected+['private-asset'])
            self.assertFalse((Path(tmp)/'leak').exists())


if __name__=='__main__':unittest.main()
