"""Late or truncated skill reads cannot be repaired by a retrospective receipt."""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest

from proposition_runtime import state, preservation
from proposition_runtime.experience import inspect_experience
from experience_fixture import prepare_experience, prepare_inputs, write_artifact


class MethodReadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'runs')
        self.root=Path(self.run['root'])
        self.retained=prepare_experience(self.run)

    def check(self):
        return inspect_experience(state.load_run(self.root))

    def test_complete_prior_reading_preserves_the_valid_creative_graph(self):
        self.assertEqual(self.check()['status'],'PASS',self.check())

    def test_analysis_source_pack_does_not_expand_or_replace_the_four_creative_methods(self):
        result=self.check()
        self.assertEqual('PASS',result['status'],result)
        inputs=json.loads((self.root/'creative-inputs.json').read_text())
        self.assertEqual({'claude-seo','impeccable','scroll-craft','apple-design'},
                         {m['family'] for m in inputs['methods']})
        inputs['methods'][0]['family']='marketingskills'
        write_artifact(self.run,'creative-inputs','creative-inputs.json',inputs)
        self.assertEqual('BLOCKED',self.check()['status'])

    def test_missing_reading_receipt_blocks_promotion_and_freezing(self):
        (self.root/'creative-reading.json').unlink()
        self.assertEqual(self.check()['status'],'BLOCKED')
        with self.assertRaises(ValueError):
            preservation.freeze_creatives(self.root,{'revision':'r1','actor':'fixture',
                'decision':'Retain the compared direction.','retained':self.retained})
        self.assertFalse((self.root/preservation.LOCK).exists())

    def test_late_registration_cannot_backdate_reading_before_central_scenes(self):
        data=json.loads((self.root/'creative-reading.json').read_text())
        write_artifact(self.run,'creative-reading','creative-reading.json',data)
        result=self.check()
        self.assertEqual(result['status'],'BLOCKED',result)
        self.assertIn('before',result['issues'][0])

    def test_render_before_reading_cannot_hide_behind_later_artifact_registration(self):
        data=json.loads((self.root/'creative-exploration.json').read_text())
        data['candidates'][0]['rendered_at']=self.run['created_at']
        write_artifact(self.run,'creative-exploration','creative-exploration.json',data)
        plan=json.loads((self.root/'creative-experience.json').read_text())
        write_artifact(self.run,'creative-experience','creative-experience.json',plan)
        self.assertEqual(self.check()['status'],'BLOCKED',self.check())

    def test_central_render_date_cannot_be_null_or_missing(self):
        original=json.loads((self.root/'creative-exploration.json').read_text())
        for index,value in ((i,v) for i in (0,1) for v in (None,'',False,'missing')):
            with self.subTest(candidate=index,value=value):
                data=json.loads(json.dumps(original))
                if value=='missing':data['candidates'][index].pop('rendered_at')
                else:data['candidates'][index]['rendered_at']=value
                write_artifact(self.run,'creative-exploration','creative-exploration.json',data)
                plan=json.loads((self.root/'creative-experience.json').read_text())
                write_artifact(self.run,'creative-experience','creative-experience.json',plan)
                self.assertEqual(self.check()['status'],'BLOCKED',self.check())
                with self.assertRaises(ValueError):
                    preservation.freeze_creatives(self.root,{'revision':'r1','actor':'fixture',
                        'decision':'Retain after comparison.','retained':self.retained})
                self.assertFalse((self.root/preservation.LOCK).exists())

    def test_incomplete_wrong_or_future_reading_blocks_even_with_all_scenes(self):
        original=json.loads((self.root/'creative-reading.json').read_text())
        for defect in ('missing_method','duplicate_method','wrong_inputs','wrong_hash','empty_segments',
                       'gap','missing_tail','oversized_range','boolean_range','read_before_inputs','future_read'):
            with self.subTest(defect=defect):
                data=json.loads(json.dumps(original)); item=data['methods'][0]
                if defect=='missing_method':data['methods'].pop()
                elif defect=='duplicate_method':data['methods'][1]=item
                elif defect=='wrong_inputs':data['inputs_sha256']='0'*64
                elif defect=='wrong_hash':item['read_sha256']='0'*64
                elif defect=='empty_segments':item['segments']=[]
                elif defect=='gap':item['segments']=item['segments'][1:]
                elif defect=='missing_tail':item['segments']=item['segments'][:1]
                elif defect=='oversized_range':item['segments'][0]['end_line']=100000
                elif defect=='boolean_range':item['segments'][0]['start_line']=True
                elif defect=='read_before_inputs':item['segments'][0]['read_at']=self.run['created_at']
                elif defect=='future_read':item['segments'][0]['read_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
                # Change bytes at the original registered boundary to isolate content checks.
                # Reload/save is test corruption, not a supported backdating API.
                path=self.root/'creative-reading.json'; path.write_text(json.dumps(data))
                current=state.load_run(self.root)
                import hashlib
                current['artifacts']['creative-reading']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                state.save_run(self.root,current)
                self.assertEqual(self.check()['status'],'BLOCKED',self.check())

    def test_new_runs_pin_reading_contract_and_cannot_remove_it(self):
        run=state.load_run(self.root)
        self.assertEqual(run['metadata'].get('creative_reading_contract'),1)
        run['metadata'].pop('creative_reading_contract')
        with self.assertRaises(ValueError):state.save_run(self.root,run)

    def test_linked_reading_stays_inside_pinned_tree_and_uses_real_bytes(self):
        original=json.loads((self.root/'creative-reading.json').read_text())
        inputs=json.loads((self.root/'creative-inputs.json').read_text())
        method=inputs['methods'][0]; root=Path(method['reference_root'])
        file=next(root.rglob('SKILL.md')); relative=file.relative_to(root).as_posix()
        import hashlib
        item={'family':method['family'],'path':relative,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
              'purpose':'Synthetic linked-reference boundary fixture.',
              'segments':[original['methods'][0]['segments'][0]]}
        for defect in ('valid','escape','absolute','wrong_hash','unknown_family','missing_purpose'):
            with self.subTest(defect=defect):
                data=json.loads(json.dumps(original)); linked=dict(item)
                if defect=='escape':linked['path']='../SKILL.md'
                elif defect=='absolute':linked['path']=str(file)
                elif defect=='wrong_hash':linked['sha256']='0'*64
                elif defect=='unknown_family':linked['family']='unknown'
                elif defect=='missing_purpose':linked['purpose']=''
                data['supporting_reads']=[linked]
                path=self.root/'creative-reading.json';path.write_text(json.dumps(data))
                current=state.load_run(self.root)
                current['artifacts']['creative-reading']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                state.save_run(self.root,current)
                self.assertEqual(self.check()['status'],'PASS' if defect=='valid' else 'BLOCKED',self.check())

    def test_historical_runs_without_reading_contract_keep_their_old_scope(self):
        path=self.root/'state.json'; run=json.loads(path.read_text())
        run['metadata'].pop('creative_reading_contract',None); path.write_text(json.dumps(run))
        (self.root/'creative-reading.json').unlink()
        self.assertEqual(self.check()['status'],'PASS',self.check())

    def test_cli_preflight_can_pass_before_any_candidate_is_rendered(self):
        run=state.init_run('https://fixture.example/',Path(self.tmp.name)/'preflight')
        prepare_inputs(run)
        result=self.preflight(run['root'])
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['scope'],'creative_input_reading_consistency_only')
        self.assertEqual(report['status'],'PASS')
        self.assertFalse(list(Path(run['root']).glob('*.png')))

    def test_cli_preflight_blocks_missing_receipt_before_spending_on_creation(self):
        (self.root/'creative-reading.json').unlink()
        result=self.preflight(self.root)
        self.assertNotEqual(result.returncode,0)
        self.assertTrue(result.stdout.strip().startswith('{'),result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'BLOCKED')

    def preflight(self,root):
        launcher=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        return subprocess.run([sys.executable,str(launcher),'check-experience',str(root),'--inputs-only'],
                              capture_output=True,text=True,timeout=10)
