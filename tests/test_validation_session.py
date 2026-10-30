"""Same consumers, shared stable work, fresh commands and fail-closed changes."""
import json
import os
from pathlib import Path
import unittest
import test_replay as fixtures
from proposition_runtime import state, strategy, telemetry
try:
    from proposition_runtime.validation import ValidationSession
except ImportError:
    ValidationSession = None


class ValidationSessionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ValidationSession, 'Per-phase validation session is missing')
        self.case = fixtures.ReplayTests('runTest');self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root

    def test_six_consumer_verdicts_share_common_integrity_work(self):
        with telemetry.TraceRecorder(self.root) as trace:
            with trace.span('cli.command'):
                with ValidationSession():
                    run = state.load_run(self.root)
                    results = [strategy.inspect(run, stage) for stage in ('analysis.specialists','company.v2','brief.public')*2]
        self.assertEqual(['PASS']*6, [r['status'] for r in results])
        metrics = telemetry.metrics(self.root)
        self.assertEqual(3, metrics['counters']['reader.json'])
        events = [json.loads(x) for x in next((self.root/'telemetry').glob('*.jsonl')).read_text().splitlines()]
        for name in ('upstream.inspect','research.validate','channels.inspect','discovery.inspect'):
            self.assertEqual(1, sum(e['event']=='end' and e['name']==name for e in events), name)

    def test_each_consumer_keeps_its_own_summary_checks(self):
        (self.root/'company.json').write_text(json.dumps({'audience_need_summary':{}}))
        state.add_artifact(self.root,'company-evidence-brief','company.json','internal',['artifact:observation-analysis-map'])
        with ValidationSession():
            run = state.load_run(self.root)
            results = [strategy.inspect(run, stage) for stage in ('analysis.specialists','company.v2','brief.public')]
        self.assertEqual(['PASS','BLOCKED','BLOCKED'], [r['status'] for r in results])

    def change_same_size_and_mtime(self, path):
        old = path.stat();data = path.read_bytes()
        path.write_bytes(bytes([data[0]^1])+data[1:])
        os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))

    def test_new_phase_detects_corruption_with_size_and_mtime_restored(self):
        with ValidationSession():
            self.assertEqual('PASS',strategy.inspect(state.load_run(self.root))['status'])
        self.change_same_size_and_mtime(self.root/'strategy-source.txt')
        with ValidationSession():
            self.assertEqual('BLOCKED',strategy.inspect(state.load_run(self.root))['status'])

    def test_mid_phase_change_never_produces_mixed_pass(self):
        with self.assertRaises(ValueError):
            with ValidationSession():
                run = state.load_run(self.root)
                self.assertEqual('PASS',strategy.inspect(run)['status'])
                self.change_same_size_and_mtime(self.root/'strategy-source.txt')
                self.assertEqual('BLOCKED',strategy.inspect(run)['status'])

    def test_changed_linked_method_is_checked_in_the_next_phase(self):
        with ValidationSession():
            self.assertEqual('PASS',strategy.inspect(state.load_run(self.root))['status'])
        data = json.loads(self.case.report.read_text())
        root = Path(data['methods'][0]['reference_root'])
        reference = next(p for p in root.rglob('*.md') if p.name != 'SKILL.md')
        self.change_same_size_and_mtime(reference)
        with ValidationSession():
            self.assertEqual('BLOCKED',strategy.inspect(state.load_run(self.root))['status'])

    def test_explicit_mutation_opens_fresh_hash_phase(self):
        path = self.root/'strategy-source.txt'
        with ValidationSession() as session:
            before = state._sha(path)
            path.write_text('New synthetic observation')
            session.invalidate()
            self.assertNotEqual(before,state._sha(path))

    def test_cache_never_turns_a_replaced_file_into_a_symlink_read(self):
        path = self.root/'strategy-source.txt'
        with self.assertRaises(ValueError):
            with ValidationSession():
                state._sha(path)
                path.unlink();path.symlink_to(self.root/'mission-trace.txt')
                state._sha(path)

    def test_final_validation_starts_a_fresh_hash_phase(self):
        from hashlib import sha256
        path = self.root/'strategy-source.txt'
        with telemetry.TraceRecorder(self.root) as trace:
            with trace.span('cli.command'):
                with ValidationSession():
                    state._sha(path)
                    state.validate_run(self.root)
        file_id = sha256(str(path.absolute()).encode()).hexdigest()
        events = [json.loads(x) for x in next((self.root/'telemetry').glob('*.jsonl')).read_text().splitlines()]
        self.assertEqual(2, sum(e['name']=='validation.hash' and e['attributes'].get('file_id')==file_id for e in events))

    def test_artifact_hashes_participate_in_the_same_stable_phase(self):
        from proposition_runtime.artifacts import sha256
        path = self.root/'strategy-source.txt'
        with self.assertRaises(ValueError):
            with ValidationSession():
                sha256(path)
                self.change_same_size_and_mtime(path)
                state._sha(path)

    def test_tiny_cache_budget_does_not_grow_or_skip_a_consumer(self):
        import inspect
        self.assertIn('max_bytes', inspect.signature(ValidationSession).parameters, 'Cache byte budget is missing')
        with ValidationSession(max_bytes=1) as session:
            run = state.load_run(self.root)
            for stage in ('analysis.specialists','company.v2','brief.public'):
                self.assertEqual('PASS', strategy.inspect(run,stage)['status'])
            self.assertLessEqual(session.cached_bytes,1)
