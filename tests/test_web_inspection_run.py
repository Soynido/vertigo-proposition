"""Inspection receipts remain tied to the exact build and actual screenshot bytes."""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from proposition_runtime import state, web
from web_fixture import prepare_web


class WebInspectionRunTests(unittest.TestCase):
    def test_unavailable_inspection_engine_preserves_a_blocked_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);web.build_run(run['root'],source,plan)
            report=web.inspect_run(run['root'],browsers=('unsupported-fixture-engine',),viewports=((390,844),))
            self.assertEqual(report['status'],'BLOCKED')
            self.assertTrue(any(r['code']=='browser_unavailable' for r in report['issues']))
            self.assertEqual(web.current_inspection(state.load_run(run['root']))['status'],'BLOCKED')

    def test_real_cli_can_inspect_the_current_build_without_requiring_pdf_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, source, plan = prepare_web(tmp)
            web.build_run(run['root'],source,plan)
            cli=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
            result=subprocess.run([sys.executable,str(cli),'web','inspect',run['root'],
                '--browser','chromium'],capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            receipt=json.loads(result.stdout)
            self.assertEqual(receipt['status'],'PASS')
            self.assertEqual(receipt['scope'],'observed_browser_mechanics_only')
            self.assertEqual(receipt['creative_quality'],'NOT_ASSESSED')
            self.assertNotIn('captures',receipt)

    def test_adopted_real_inspection_is_reusable_but_changed_capture_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, source, plan = prepare_web(tmp)
            root = Path(run['root'])
            web.build_run(root, source, plan)
            self.assertTrue(callable(getattr(web, 'inspect_run', None)),
                            'No run-bound exact-build inspection')
            report = web.inspect_run(root, browsers=('chromium',), viewports=((390,844),))
            self.assertEqual(report['status'], 'PASS', report.get('issues'))
            current = state.load_run(root)
            row = current['artifacts']['web-inspection']
            self.assertIn('artifact:web-build', row['dependencies'])
            inspection = web.current_inspection(current)
            self.assertEqual(inspection['build_id'], report['build_id'])
            repeated = web.inspect_run(root, browsers=('chromium',), viewports=((390,844),))
            self.assertEqual(repeated, report)
            self.assertEqual(state.load_run(root)['artifacts']['web-inspection'], row)
            capture = root / row['path']
            capture = capture.parent / report['captures'][0]['path']
            capture.write_bytes(b'replaced image')
            with self.assertRaises(ValueError):
                web.current_inspection(state.load_run(root))
            with self.assertRaises(ValueError):
                web.inspect_run(root, browsers=('chromium',), viewports=((390,844),))

    def test_report_only_or_changed_build_cannot_provide_current_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, source, plan = prepare_web(tmp)
            root = Path(run['root'])
            web.build_run(root, source, plan)
            self.assertTrue(callable(getattr(web, 'inspect_run', None)),
                            'No run-bound exact-build inspection')
            report = web.inspect_run(root, browsers=('chromium',), viewports=((390,844),))
            self.assertEqual(report['status'], 'PASS', report.get('issues'))
            (source / 'app.js').write_text('throw new Error("new revision")')
            with self.assertRaises(ValueError):
                web.current_inspection(state.load_run(root))


if __name__ == '__main__':
    unittest.main()
