"""Exercise the supported launcher as a collaborator would, in a fresh process."""
import json
import hashlib
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'skills/proposition/scripts/proposition.py'


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()

    def command(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(LAUNCHER), *map(str, args)],
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_launcher_works_outside_checkout_and_initial_run_is_not_pass(self):
        created = self.command('init', 'https://example.com', '--runs-root', self.base / 'runs')
        self.assertEqual(created['id'], Path(created['root']).name)
        checked = self.command('validate', created['root'], ok=False)
        self.assertEqual(checked['status'], 'BLOCKED')
        self.assertTrue(any(i['code'] == 'missing_evaluation' for i in checked['issues']))

    def test_experience_stage_flag_reaches_the_gate(self):
        run = self.command('init', 'https://example.com', '--runs-root', self.base / 'runs')
        checked = self.command('check-experience', run['root'], '--stage', 'client.composition', ok=False)
        self.assertEqual(checked['status'], 'BLOCKED')
        self.assertIn('scope', checked)

    def test_native_preprocessing_does_not_require_cloudflare_configuration(self):
        created=self.command('init','https://example.com','--runs-root',self.base/'native-runs')
        result=self.command('preprocess',created['root'],'--mode','codex')
        self.assertEqual('CODEX_REQUIRED',result['status'])
        self.assertEqual(0,result['requests'])
        self.assertTrue(Path(result['native_task_path']).is_file())
        self.assertNotIn('batches',result)

    def test_initial_explicit_mandate_reaches_the_chosen_direction_contract(self):
        instruction=(self.base/'current-user-input.txt').resolve()
        text='Continue the already chosen direction a only.';instruction.write_text(text)
        mandate=self.base/'creative-mandate.json'
        mandate.write_text(json.dumps({'version':1,'mode':'external_selection','candidate_count':1,'candidate_ids':['a'],
            'authority':{'kind':'current_user_instruction','site_url':'https://example.com',
                         'input_path':str(instruction),'input_sha256':hashlib.sha256(text.encode()).hexdigest(),
                         'quote':text,'captured_at':datetime.now(timezone.utc).isoformat()}}))
        run=self.command('init','https://example.com','--runs-root',self.base/'runs','--creative-mandate',mandate)
        contract=run['metadata']['creative_exploration_contract']
        self.assertEqual(contract['mode'],'external_selection')
        self.assertEqual(contract['candidate_ids'],['a'])
        self.assertEqual((Path(run['root'])/'creative-mandate-input.txt').read_text(),text)

    def test_creative_mandate_file_cannot_block_the_launcher_on_a_fifo(self):
        mandate=self.base/'creative-mandate.fifo';os.mkfifo(mandate)
        try:
            result=subprocess.run([sys.executable,str(LAUNCHER),'init','https://example.com',
                '--runs-root',str(self.base/'fifo-runs'),'--creative-mandate',str(mandate)],
                cwd=self.base,capture_output=True,text=True,timeout=2)
        except subprocess.TimeoutExpired:
            self.fail('A mandate FIFO blocked the launcher instead of being rejected')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(result.stdout)['status'],'ERROR')
        self.assertFalse((self.base/'fifo-runs').exists())

    def test_source_fact_and_receipt_persist_without_exposing_private_value(self):
        run = self.command('init', 'https://example.com', '--runs-root', self.base / 'runs')
        root = Path(run['root'])
        (root / 'copy.txt').write_text('Public source')
        source = self.base / 'source.json'
        source.write_text(json.dumps({'id': 'web', 'path': 'copy.txt', 'locator': 'https://example.com'}))
        self.command('source', root, source)
        fact = self.base / 'fact.json'
        fact.write_text(json.dumps({'id': 'account-note', 'value': 'PRIVATE_SENTINEL', 'source_ids': ['web']}))
        self.command('fact', root, fact)
        receipt = self.command('receipt', root)
        self.assertEqual(receipt['counts']['facts'], 1)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(receipt))
        self.assertNotEqual(receipt['quality'], 'PASS')

    def test_resource_measurement_keeps_unavailable_values_unknown(self):
        run = self.command('init', 'https://example.com', '--runs-root', self.base / 'runs')
        metrics = self.command('measure', run['root'])
        self.assertIsNone(metrics['tokens_used'])
        self.assertIsNone(metrics['account_tokens_remaining'])
        self.assertIsNone(metrics['quota_remaining_percent'])
        self.assertFalse(metrics['stop_for_quota'])
        metrics = self.command('measure', run['root'], '--quota-remaining-percent', '25', '--quota-source', 'host-test')
        self.assertTrue(metrics['stop_for_quota'])
        self.assertIn('NON DISPONIBLES', metrics['footer'])

    def test_local_workbench_is_escaped_and_has_no_external_assets(self):
        run = self.command('init', 'https://example.com', '--runs-root', self.base / 'runs')
        root = Path(run['root'])
        output = self.command('workbench', root)
        html = Path(output['path']).read_text()
        self.assertIn('Vue interne', html)
        self.assertIn('BLOCKED', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('PRIVATE_SENTINEL', html)


if __name__ == '__main__':
    unittest.main()
