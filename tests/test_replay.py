"""Real local retries, malformed journals and current versus retained evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_state as fixtures
from discovery_fixture import install_discovery, write_report
from public_research_fixture import journal
from strategy_fixture import make_analysis
from proposition_runtime import state, strategy, discovery_evidence, public_research


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StateTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.run = self.fixture.new_run()
        self.root = Path(self.run['root'])
        install_discovery(self.run)
        self.report = make_analysis(self.run)
        strategy.register(self.root, self.report)
        data = json.loads(self.report.read_text())
        summary = strategy.summary(data)
        (self.root/'company.json').write_text(json.dumps({'audience_need_summary': summary}))
        state.add_artifact(self.root, 'company-evidence-brief', 'company.json', 'internal',
                           ['artifact:observation-analysis-map'])
        (self.root/'brief.json').write_text(json.dumps({
            'audience_need_summary': summary,
            'observations': [{'id': 'o1', 'need_ids': ['n1'], 'decision': 'retained',
                              'proof': 'source:strategy-source'}],
        }))
        state.add_artifact(self.root, 'creative-inputs', 'brief.json', 'public',
                           ['artifact:company-evidence-brief'])

    def test_identical_strategy_retry_preserves_records_and_consumers(self):
        before = state.load_run(self.root)
        strategy.register(self.root, self.report)
        self.assertEqual([], state.invalidate_changed(self.root)['invalidated'])
        self.assertEqual(before['artifacts'], state.load_run(self.root)['artifacts'])

    def test_identical_channel_retry_preserves_records_and_consumers(self):
        before = state.load_run(self.root)
        discovery_evidence.reconcile(self.root, self.root/'research-public.json')
        self.assertEqual([], state.invalidate_changed(self.root)['invalidated'])
        after = state.load_run(self.root)
        self.assertEqual(before['artifacts'], after['artifacts'])
        self.assertEqual(before['metadata']['discovery_external_reports'],
                         after['metadata']['discovery_external_reports'])

    def test_strategy_retry_keeps_existing_approval(self):
        current = state.load_run(self.root)
        record = current['artifacts']['observation-analysis-map']
        record['approval'] = {'actor': 'operator', 'sha256': record['sha256']}
        state.save_run(self.root, current)
        strategy.register(self.root, self.report)
        self.assertEqual(record, state.load_run(self.root)['artifacts']['observation-analysis-map'])

    def test_earlier_current_journal_retry_preserves_the_bundle_and_consumers(self):
        path = self.root/'ordinary.json'
        path.write_text(json.dumps({'version': 1, 'attempts': []}))
        self.assertEqual('PASS', discovery_evidence.reconcile(self.root, path)['status'])
        state.invalidate_changed(self.root)
        current = state.load_run(self.root)
        bundle = current['artifacts']['discovery-channels']
        bundle['approval'] = {'actor': 'operator', 'sha256': bundle['sha256']}
        state.save_run(self.root, current)
        consumer = self.root/'retry-consumer.txt'
        consumer.write_text('Result of the same current public research')
        state.add_artifact(self.root, 'retry-consumer', consumer.name, 'internal',
                           ['artifact:discovery-channels'])
        before = state.load_run(self.root)
        self.assertEqual('PASS', discovery_evidence.reconcile(self.root, self.root/'research-public.json')['status'])
        self.assertEqual(before['artifacts'], state.load_run(self.root)['artifacts'])
        self.assertEqual([], state.invalidate_changed(self.root)['invalidated'])

    def test_missing_historical_journal_blocks_without_crashing(self):
        old = state.load_run(self.root)['metadata']['discovery_external_reports'][0]
        (self.root/'google_search.txt').write_text('Old observation changed')
        discovery_evidence.reconcile(self.root, self.new_research())
        current = state.load_run(self.root)
        del current['artifacts'][old]
        state.save_run(self.root, current)
        error = None
        try:
            result = state.validate_run(self.root)
        except Exception as caught:
            error = caught
        self.assertIsNone(error)
        self.assertNotEqual('PASS', result['status'])
        channels = discovery_evidence.inspect_channels(state.load_run(self.root))
        self.assertEqual('BLOCKED', channels['status'])
        self.assertTrue(any('missing journal' in x for x in channels['issues']))

    def test_same_payload_does_not_resurrect_a_stale_map(self):
        current = state.load_run(self.root)
        current['artifacts']['observation-analysis-map']['status'] = 'STALE'
        state.save_run(self.root, current)
        result = strategy.register(self.root, self.report)
        self.assertEqual('BLOCKED', result['status'])
        self.assertEqual('STALE', state.load_run(self.root)['artifacts']['observation-analysis-map']['status'])

    def test_real_report_change_still_invalidates_consumers(self):
        data = json.loads(self.report.read_text())
        data['unknowns'].append('A new documented limitation')
        self.report.write_text(json.dumps(data))
        strategy.register(self.root, self.report)
        state.invalidate_changed(self.root)
        current = state.load_run(self.root)
        self.assertEqual('STALE', current['artifacts']['company-evidence-brief']['status'])
        self.assertEqual('STALE', current['artifacts']['creative-inputs']['status'])

    def test_changed_source_cannot_be_hidden_by_a_retry(self):
        (self.root/'strategy-source.txt').write_text('Changed actual observation')
        with self.assertRaises(ValueError):
            strategy.register(self.root, self.report)
        self.assertEqual('STALE', state.load_run(self.root)['artifacts']['creative-inputs']['status'])

    def new_research(self):
        data = json.loads((self.root/'research-public.json').read_text())
        current = state.load_run(self.root)
        for sid in ('identity', 'google_search', 'google_ads', 'meta_ads', 'reviews'):
            new_id = 'new-'+sid
            path = self.root/(new_id+'.txt')
            path.write_text('New synthetic public observation: '+sid)
            state.add_source(self.root, new_id, path.name, kind='public',
                             locator=current['sources'][sid]['locator'])
        for row in data['attempts']:
            row['id'] = 'new-'+row['id']
            row['source_id'] = 'new-'+row['source_id']
            row['observed_at'] = '2026-10-30T09:00:00+00:00'
        data['public_research']['entity']['source_ids'] = ['new-identity']
        for row in data['public_research']['topics']:
            row['attempt_ids'] = ['new-'+identifier for identifier in row['attempt_ids']]
        path = self.root/'new-research.json'
        path.write_text(json.dumps(data))
        return path

    def test_current_replacement_excludes_stale_history_without_deleting_it(self):
        old = state.load_run(self.root)['metadata']['discovery_external_reports'][0]
        (self.root/'google_search.txt').write_text('Old public observation has changed')
        path = self.new_research()
        result = discovery_evidence.reconcile(self.root, path)
        self.assertEqual('PASS', result['status'], result)
        current = state.load_run(self.root)
        self.assertIn(old, current['metadata']['discovery_external_reports'])
        self.assertEqual('STALE', current['artifacts'][old]['status'])
        self.assertNotIn('artifact:'+old, current['artifacts']['discovery-channels']['dependencies'])
        self.assertEqual('PASS', public_research.inspect(current)['status'])

    def test_incomplete_replacement_does_not_reuse_stale_research(self):
        (self.root/'google_search.txt').write_text('Old public observation has changed')
        path = self.root/'ordinary.json'
        path.write_text(json.dumps({'version': 1, 'attempts': []}))
        result = discovery_evidence.reconcile(self.root, path)
        self.assertEqual('BLOCKED', result['status'])
        self.assertTrue(any('Missing public research' in x for x in result['issues']), result)

    def test_replaced_history_alone_does_not_block_global_validation(self):
        old = state.load_run(self.root)['metadata']['discovery_external_reports'][0]
        (self.root/'google_search.txt').write_text('Old observation changed')
        discovery_evidence.reconcile(self.root, self.new_research())
        result = state.validate_run(self.root)
        obsolete = {'artifact:'+old, 'source:google_search'}
        self.assertFalse([x for x in result['issues'] if x.get('id') in obsolete], result)
        self.assertNotEqual('PASS', result['status'])  # Other required work remains missing/stale.

    def test_history_exemption_cannot_hide_a_stale_fact_or_its_source(self):
        state.add_fact(self.root, 'still-required', 'Separate required claim', ['google_search'])
        (self.root/'google_search.txt').write_text('Old observation changed')
        discovery_evidence.reconcile(self.root, self.new_research())
        result = state.validate_run(self.root)
        stale = {x['id'] for x in result['issues'] if x['code'] == 'stale_evidence'}
        self.assertIn('fact:still-required', stale)
        self.assertIn('source:google_search', stale)

    def test_missing_historical_source_does_not_crash_validation(self):
        (self.root/'google_search.txt').write_text('Old observation changed')
        discovery_evidence.reconcile(self.root, self.new_research())
        current = state.load_run(self.root)
        del current['sources']['google_search']
        state.save_run(self.root, current)
        error = None
        try:
            result = state.validate_run(self.root)
        except Exception as caught:
            error = caught
        self.assertIsNone(error)
        self.assertNotEqual('PASS', result['status'])

    def test_replacement_does_not_invent_a_missing_external_attempt(self):
        url = 'https://www.instagram.com/fixture/'
        self.run = self.fixture.new_run()
        self.root = Path(self.run['root'])
        path = write_report(self.run)
        data = json.loads(path.read_text())
        data['link_entries'] = [{'url': url, 'text': 'Instagram', 'source_id': 'source:fixture-desktop'}]
        path.write_text(json.dumps(data))
        discovery_evidence.register(self.root, path)
        old = json.loads(journal(self.run).read_text())
        old['attempts'].append({'url': url, 'status': 'unavailable',
                                'observed_at': '2026-10-29T12:00:00+00:00',
                                'reason': 'Old synthetic external trace'})
        path = self.root/'with-external.json'
        path.write_text(json.dumps(old))
        self.assertEqual('PASS', discovery_evidence.reconcile(self.root, path)['status'])
        (self.root/'google_search.txt').write_text('Old observation changed')
        result = discovery_evidence.reconcile(self.root, self.new_research())
        self.assertEqual('BLOCKED', result['status'])
        self.assertEqual('PASS', result['public_research']['status'])
        self.assertTrue(any('External destination not attempted' in x for x in result['issues']))

    def test_new_attempt_still_invalidates_the_old_analysis(self):
        data = json.loads((self.root/'research-public.json').read_text())
        for row in data['attempts']:
            row['id'] = 'later-'+row['id']
            row['observed_at'] = '2026-10-30T09:00:00+00:00'
        for row in data['public_research']['topics']:
            row['attempt_ids'] = ['later-'+identifier for identifier in row['attempt_ids']]
        path = self.root/'later-attempt.json'
        path.write_text(json.dumps(data))
        discovery_evidence.reconcile(self.root, path)
        state.invalidate_changed(self.root)
        self.assertEqual('STALE', state.load_run(self.root)['artifacts']['observation-analysis-map']['status'])


class ResearchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.StateTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.run = self.fixture.new_run()
        self.root = Path(self.run['root'])
        install_discovery(self.run)

    def test_malformed_research_shapes_are_rejected_before_adoption(self):
        good = json.loads((self.root/'research-public.json').read_text())
        cases = [[], None, {'version': 1, 'attempts': [None]}]
        for value in (None, [], 'research', 1):
            data = copy.deepcopy(good)
            data['public_research'] = value
            cases.append(data)
        for field, value in (('entity', []), ('topics', [None])):
            data = copy.deepcopy(good)
            data['public_research'][field] = value
            cases.append(data)
        data = copy.deepcopy(good)
        data['public_research']['topics'][0]['conclusion'] = []
        cases.append(data)
        data = copy.deepcopy(good)
        data['attempts'][0]['fallback'] = []
        cases.append(data)
        data = copy.deepcopy(good)
        data['attempts'][0]['query'] = []
        cases.append(data)
        before = state.load_run(self.root)
        for n, data in enumerate(cases):
            with self.subTest(case=n):
                # Deliberate fixture reset, with an explicit current CAS precondition.
                state.save_run(self.root, before, expected_state_hash=state.load_run(self.root).base_sha256)
                path = self.root/'malformed.json'
                path.write_text(json.dumps(data))
                error = None
                try:
                    discovery_evidence.reconcile(self.root, path)
                except Exception as caught:
                    error = caught
                self.assertIsInstance(error, ValueError)
                after = state.load_run(self.root)
                self.assertEqual(before['artifacts'], after['artifacts'])
                self.assertEqual(before['metadata'], after['metadata'])

    def test_malformed_research_cli_returns_json_without_traceback(self):
        path = self.root/'malformed.json'
        path.write_text(json.dumps({'version': 1, 'attempts': [], 'public_research': []}))
        launcher = Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result = subprocess.run([sys.executable, str(launcher), 'discovery', 'reconcile',
                                 str(self.root), '--report', str(path)], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertTrue(result.stdout.strip(), 'Expected structured JSON, got: '+result.stderr)
        self.assertEqual('ERROR', json.loads(result.stdout)['status'])
        self.assertNotIn('Traceback', result.stderr)

    def test_ordinary_journal_keeps_prior_complete_research(self):
        path = self.root/'ordinary.json'
        path.write_text(json.dumps({'version': 1, 'attempts': []}))
        self.assertEqual('PASS', discovery_evidence.reconcile(self.root, path)['status'])

    def test_present_invalid_contract_versions_are_blocked(self):
        path = make_analysis(self.run)
        strategy.register(self.root, path)
        for value in (None, False, True, 0, 3, '1'):
            with self.subTest(version=value):
                current = state.load_run(self.root)
                current['metadata']['public_research_contract'] = value
                current['metadata']['audience_handoff_contract'] = value
                self.assertEqual('BLOCKED', public_research.inspect(current)['status'])
                self.assertEqual('BLOCKED', strategy.inspect(current, 'analysis.specialists')['status'])

    def test_absent_contract_keys_keep_legacy_scope(self):
        current = state.load_run(self.root)
        current['metadata'].pop('public_research_contract')
        current['metadata'].pop('audience_handoff_contract')
        self.assertEqual('NOT_REQUIRED', public_research.inspect(current)['status'])
        self.assertEqual('NOT_REQUIRED', strategy.inspect(current)['status'])

    def test_boolean_cannot_replace_initialized_integer_contracts(self):
        for key in ('public_research_contract', 'audience_handoff_contract'):
            with self.subTest(contract=key):
                current = state.load_run(self.root)
                current['metadata'][key] = True
                with self.assertRaises(ValueError):
                    state.save_run(self.root, current)


if __name__ == '__main__':
    unittest.main()
