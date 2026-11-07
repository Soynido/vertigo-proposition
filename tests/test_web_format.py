"""Web routing must not masquerade as a PDF run or mutate an archived format."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from proposition_runtime import state

CLI = Path(__file__).resolve().parents[1] / 'skills/proposition/scripts/proposition.py'


class WebFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def web_run(self):
        result = subprocess.run([sys.executable, str(CLI), 'init',
            'https://fixture.example/', '--runs-root', str(self.base/'runs'),
            '--delivery-format', 'web'], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_explicit_web_cli_selects_persisted_format(self):
        run = self.web_run()
        self.assertEqual(run['profile']['parameters']['delivery_format'], 'web')
        self.assertEqual(run['metadata']['web_contract'], 1)

    def test_new_web_runs_use_bounded_native_work_without_changing_document_defaults(self):
        from proposition_runtime.transactions import execution_metadata
        run=self.web_run()
        config=execution_metadata(run)['config']
        self.assertEqual(config,{'concurrency':2,'max_host_tasks':2,'panel_scan':'batch',
            'image_wait_policy':'terminal_aware','proof_storage':'content_addressed'})
        legacy=state.init_run('https://fixture.example/',self.base/'documents')
        self.assertEqual(execution_metadata(legacy)['config']['max_host_tasks'],1)
        explicit=dict(config,concurrency=1,max_host_tasks=1)
        run=state.init_run('https://fixture.example/',self.base/'explicit',delivery_format='web',execution_config=explicit)
        self.assertEqual(execution_metadata(run)['config'],explicit)

    def test_explicit_document_request_overrides_workspace_default_only_at_initialization(self):
        profile={'actor':'fixture','responsible':'fixture','responsible_confirmed':True,
                 'required_reviewers':['review-a','review-b'],'parameters':{'delivery_format':'web'}}
        run=state.init_run('https://fixture.example/',self.base/'runs',profile,delivery_format='documents')
        self.assertEqual(state.delivery_format(run),'documents')
        self.assertNotIn('web_contract',run['metadata'])
        self.assertEqual(profile['parameters']['delivery_format'],'web')

    def test_archived_run_without_format_keeps_document_gates(self):
        run = state.init_run('https://fixture.example/', self.base/'legacy')
        # Absence is the on-disk shape of historical runs, not an update API.
        path = Path(run['root'])/'state.json'
        data = json.loads(path.read_text())
        data['profile']['parameters'].pop('delivery_format', None)
        path.write_text(json.dumps(data))
        report = state.stage_report(run['root'], 'export.documents')
        self.assertIn('pdf-text-inspection', report['expected_evidence'])
        self.assertIsNotNone(getattr(state, 'delivery_format', None),
                             'Persisted formats need a backwards-compatible reader')
        self.assertEqual(state.delivery_format(state.load_run(run['root'])), 'documents')

    def test_web_export_demands_build_and_browser_evidence_not_pdf(self):
        run = self.web_run()
        report = state.stage_report(run['root'], 'export.documents')
        self.assertIn('web-build', report['expected_evidence'])
        self.assertIn('web-inspection', report['expected_evidence'])
        self.assertNotIn('pdf-text-inspection', report['expected_evidence'])
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertNotIn('internal.handoffs', state._quality_stages(run))

    def test_format_and_web_contract_cannot_be_changed_after_init(self):
        run = self.web_run()
        for change in ('format', 'contract', 'remove'):
            changed = state.load_run(run['root'])
            if change == 'format':
                changed['profile']['parameters']['delivery_format'] = 'documents'
            elif change == 'contract':
                changed['metadata']['web_contract'] = 0
            else:
                changed['profile']['parameters'].pop('delivery_format')
            with self.subTest(change=change), self.assertRaises(ValueError):
                state.save_run(run['root'], changed)

    def test_invalid_format_is_rejected_before_creating_a_run(self):
        result = subprocess.run([sys.executable, str(CLI), 'init',
            'https://fixture.example/', '--runs-root', str(self.base/'runs'),
            '--delivery-format', 'anything'], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base/'runs').exists())


if __name__ == '__main__':
    unittest.main()
