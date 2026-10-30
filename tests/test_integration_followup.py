"""Maintenance closure must account for the entire existing capability inventory."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts/check_integration.py'


class IntegrationFollowupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        evidence = self.root / 'manual-review.md'
        evidence.write_text('Bounded manual comparison; no autonomous execution.')
        self.ref = {'path': evidence.name, 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}
        self.matrix = {
            'rows': [
                {'id': 'P1', 'decision': 'retain', 'followup': {
                    'state': 'OPEN', 'stage': 'integration', 'owner': 'strategy',
                    'scope': 'Public offer details, manually compared.',
                    'last_evidence': self.ref, 'next_action': 'Verify canonical loading and brief consumer.'}},
                {'id': 'P2', 'decision': 'unqualified', 'followup': {
                    'state': 'BLOCKED', 'stage': 'qualification', 'owner': 'discovery',
                    'scope': 'Public alternative only.', 'last_evidence': None,
                    'blocker': 'Public alternative not yet available.',
                    'next_action': 'Resume the bounded alternative trial when available.'}},
            ],
            'integration_followup': {
                'version': 1, 'scope_ids': ['P1', 'P2'], 'parent_status': 'OPEN',
                'active_id': 'P1', 'next_action': 'Verify canonical loading and brief consumer.',
            },
        }

    def run_check(self, matrix=None, close=False):
        path = self.root / 'matrix.json'
        path.write_text(json.dumps(self.matrix if matrix is None else matrix))
        args = [sys.executable, str(SCRIPT), str(path)]
        if close:
            args.append('--close')
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return result.returncode, json.loads(result.stdout)

    def close_rows(self):
        for row in self.matrix['rows']:
            row['followup'].update(state='CLOSED', stage='decision', next_action=None,
                closure={'kind': 'not_admitted', 'reason': 'Unavailable within this agreed scope.',
                         'decision_receipt': self.ref})
        self.matrix['integration_followup'].update(parent_status='COMPLETE', active_id=None, next_action=None)

    def test_valid_open_checkpoint_exposes_every_pending_capability_without_pass(self):
        code, report = self.run_check()
        self.assertEqual(0, code)
        self.assertEqual('IN_PROGRESS', report['status'])
        self.assertEqual(['P1', 'P2'], report['open_ids'])
        self.assertEqual('P1', report['active_id'])
        self.assertEqual('strategy', report['pending'][0]['owner'])
        self.assertEqual('Verify canonical loading and brief consumer.', report['pending'][0]['next_action'])

    def test_finished_neighbor_cannot_close_parent_with_manual_work_remaining(self):
        self.matrix['navigation_fix'] = {'status': 'COMPLETE', 'tests': 'PASS'}
        self.matrix['integration_followup']['parent_status'] = 'COMPLETE'
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertEqual('INVALID', report['status'])
        self.assertIn('parent_has_open_capabilities', {i['code'] for i in report['issues']})

    def test_closing_gate_refuses_an_otherwise_valid_open_checkpoint(self):
        code, report = self.run_check(close=True)
        self.assertNotEqual(0, code)
        self.assertEqual('IN_PROGRESS', report['status'])

    def test_dropped_inventory_row_is_not_silently_forgotten(self):
        self.matrix['rows'].pop()
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertIn('inventory_mismatch', {i['code'] for i in report['issues']})

    def test_open_capability_needs_owner_and_concrete_next_action(self):
        self.matrix['rows'][0]['followup'].update(owner='', next_action='')
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertIn('missing_next_action', {i['code'] for i in report['issues']})
        self.assertIn('missing_owner', {i['code'] for i in report['issues']})

    def test_explicit_non_admission_is_terminal_without_forcing_integration(self):
        self.close_rows()
        code, report = self.run_check(close=True)
        self.assertEqual(0, code)
        self.assertEqual('TRACKING_COMPLETE', report['status'])
        self.assertEqual([], report['open_ids'])
        self.assertEqual('NOT_ASSESSED', report['autonomous_quality'])

    def test_integrated_closure_requires_route_and_separate_receipts(self):
        self.close_rows()
        self.matrix['rows'][0]['followup']['closure'] = {'kind': 'integrated'}
        code, report = self.run_check(close=True)
        self.assertNotEqual(0, code)
        codes = {i['code'] for i in report['issues']}
        self.assertIn('missing_route', codes)
        self.assertIn('missing_qualification_receipt', codes)
        self.assertIn('missing_integration_receipt', codes)
        self.assertIn('missing_e2e_receipt', codes)

    def test_changed_evidence_invalidates_a_previously_closed_checkpoint(self):
        self.close_rows()
        (self.root / self.ref['path']).write_text('Changed after review')
        code, report = self.run_check(close=True)
        self.assertNotEqual(0, code)
        self.assertIn('evidence_changed', {i['code'] for i in report['issues']})

    def test_closed_capability_cannot_hide_a_remaining_action(self):
        self.close_rows()
        self.matrix['rows'][0]['followup']['next_action'] = 'Integration still needs work.'
        code, report = self.run_check(close=True)
        self.assertNotEqual(0, code)
        self.assertIn('closed_capability_has_next_action', {i['code'] for i in report['issues']})

    def test_no_evidence_must_be_explicit_rather_than_an_omitted_field(self):
        del self.matrix['rows'][1]['followup']['last_evidence']
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertIn('missing_evidence_state', {i['code'] for i in report['issues']})

    def test_integration_receipts_close_accounting_but_never_certify_quality(self):
        self.close_rows()
        self.matrix['rows'][0]['followup']['closure'] = {
            'kind': 'integrated', 'qualification_receipt': self.ref,
            'integration_receipt': self.ref, 'e2e_receipt': self.ref,
            'route': {'canonical_file': 'skills/fixture/SKILL.md', 'loaded_by': 'fixture dispatch',
                      'consumer': 'public brief', 'acceptance': 'artifact inspection'},
        }
        code, report = self.run_check(close=True)
        self.assertEqual(0, code)
        self.assertEqual('TRACKING_COMPLETE', report['status'])
        self.assertEqual('NOT_ASSESSED', report['autonomous_quality'])

    def test_duplicate_ids_and_untracked_rows_cannot_hide_missing_work(self):
        self.matrix['rows'].append(copy.deepcopy(self.matrix['rows'][0]))
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertIn('duplicate_id', {i['code'] for i in report['issues']})

    def test_malformed_checkpoint_returns_a_bounded_error(self):
        code, report = self.run_check({'rows': [None], 'integration_followup': {}})
        self.assertNotEqual(0, code)
        self.assertEqual('INVALID', report['status'])

    @unittest.skipUnless(hasattr(__import__('os'), 'mkfifo'), 'requires POSIX FIFO')
    def test_evidence_fifo_cannot_stall_resume(self):
        import os
        fifo = self.root / 'receipt.fifo'
        os.mkfifo(fifo)
        self.matrix['rows'][0]['followup']['last_evidence'] = {'path': fifo.name, 'sha256': '0' * 64}
        code, report = self.run_check()
        self.assertNotEqual(0, code)
        self.assertIn('unsupported_evidence', {i['code'] for i in report['issues']})


if __name__ == '__main__':
    unittest.main()
