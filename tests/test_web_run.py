import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from proposition_runtime import state, web
from web_fixture import prepare_web


class WebRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run, self.source, self.plan = prepare_web(Path(self.tmp.name))
        self.root = Path(self.run['root'])

    def build(self):
        self.assertTrue(callable(getattr(web,'build_run',None)),
                        'The web build must consume the real run and its frozen creative inputs')
        return web.build_run(self.root,self.source,self.plan)

    def test_build_binds_current_brief_selection_and_public_proofs(self):
        result = self.build()
        current = state.load_run(self.root)
        self.assertIn('web-plan',current['artifacts'])
        self.assertIn('web-build',current['artifacts'])
        self.assertIn('artifact:creative-inputs',current['artifacts']['web-plan']['dependencies'])
        self.assertEqual(result['creative_quality'],'NOT_ASSESSED')
        self.assertEqual(result['run_id'],self.run['id'])

    def test_repeated_identical_build_does_not_stale_reviews_or_rewrite_records(self):
        first = self.build(); before=state.load_run(self.root)['artifacts']
        second = self.build()
        self.assertEqual(second['build_id'],first['build_id'])
        self.assertEqual(state.load_run(self.root)['artifacts'],before)

    def test_forged_selection_or_omitted_sales_function_is_rejected(self):
        self.assertTrue(callable(getattr(web,'build_run',None)), 'Run-aware builder absent')
        original=json.loads(self.plan.read_text())
        for mutation in ('selection','coverage','action'):
            data=json.loads(json.dumps(original))
            if mutation=='selection':data['selection_sha256']='0'*64
            elif mutation=='coverage':data['coverage'].pop()
            else:data['actions'][0]['target']='https://unapproved.invalid/'
            self.plan.write_text(json.dumps(data))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                web.build_run(self.root,self.source,self.plan)
        self.assertNotIn('web-build',state.load_run(self.root)['artifacts'])

    def test_private_source_cannot_support_a_client_facing_claim(self):
        self.assertTrue(callable(getattr(web,'build_run',None)), 'Run-aware builder absent')
        (self.root/'private.txt').write_text('Confidential fixture')
        state.add_source(self.root,'private','private.txt',kind='private')
        data=json.loads(self.plan.read_text());data['coverage'][0]['proofs']=['source:private']
        self.plan.write_text(json.dumps(data))
        with self.assertRaises(ValueError):web.build_run(self.root,self.source,self.plan)

    def test_public_research_can_support_a_claim_without_publishing_its_internal_raw_file(self):
        path=self.root/'public-research.txt';path.write_text('A public source kept in the internal evidence folder')
        state.add_source(self.root,'public-research',path,kind='public',audience='internal')
        data=json.loads(self.plan.read_text());data['coverage'][0]['proofs']=['source:public-research']
        self.plan.write_text(json.dumps(data))
        prepared=state.load_run(self.root)['metadata']['web_plan']
        web.plan_run(self.root,self.source,self.plan,supersedes=prepared['sha256'],reason='Add the separately verified public research proof')
        result=self.build()
        self.assertEqual(result['status'],'PASS')
        public=Path(result['manifest_path']).parent/'.vercel/output/static'
        self.assertFalse((public/'public-research.txt').exists())

    def test_missing_commercial_mechanism_measurement_mission_or_decision_is_rejected(self):
        original=json.loads(self.plan.read_text())
        for identifier,field in [('K03','mechanism'),('K06','measurement'),('K07','mission'),('K08','decision')]:
            data=json.loads(json.dumps(original));row=next(r for r in data['coverage'] if r['id']==identifier)
            row.pop(field);self.plan.write_text(json.dumps(data))
            with self.subTest(function=identifier),self.assertRaises(ValueError):self.build()

    def test_dropped_frozen_intent_cannot_be_hidden_by_a_new_html_build(self):
        data=json.loads(self.plan.read_text());data['scenes'][0]['intent_ids'].pop()
        self.plan.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.build()

    def test_symlinked_bundle_parent_cannot_write_outside_the_run(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        (self.root/'web/bundles').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.build()
        self.assertEqual(list(outside.iterdir()),[])

    def test_source_change_is_detected_even_without_ledger_re_registration(self):
        self.build()
        (self.source/'app.js').write_text('a different experience')
        with self.assertRaises(ValueError):web.current_build(state.load_run(self.root))

    def test_real_cli_build_reports_only_the_bounded_receipt(self):
        cli=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result=subprocess.run([sys.executable,str(cli),'web','build',str(self.root),
            '--source',str(self.source),'--plan',str(self.plan)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=json.loads(result.stdout)
        self.assertEqual(receipt['scope'],'static_build_only')
        self.assertIn('build_id',receipt)
        self.assertNotIn('files',receipt)


if __name__=='__main__':unittest.main()
