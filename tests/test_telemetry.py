"""Bounded local measurement; a trace failure never changes business results."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
try:
    from proposition_runtime import telemetry
except ImportError:
    telemetry = None


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(telemetry, 'Bounded telemetry is not implemented')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'run'
        self.root.mkdir()

    def test_success_exception_and_cancellation_have_real_end_events(self):
        with telemetry.TraceRecorder(self.root) as trace:
            with trace.span('cli.command'):
                with trace.span('strategy.validate'):
                    trace.counter('reader.json', 2)
                with self.assertRaises(ValueError):
                    with trace.span('research.validate'):
                        raise ValueError('PRIVATE exception text')
                with self.assertRaises(asyncio.CancelledError):
                    with trace.span('research.host'):
                        raise asyncio.CancelledError()
        events = [json.loads(line) for line in next((self.root/'telemetry').glob('*.jsonl')).read_text().splitlines()]
        ends = [e for e in events if e['event'] == 'end']
        self.assertEqual({'SUCCEEDED', 'FAILED', 'CANCELLED'}, {e['status'] for e in ends})
        self.assertTrue(all(e['monotonic_ns'] > 0 for e in events))
        self.assertNotIn('PRIVATE', json.dumps(events))
        self.assertTrue(all(e['parent_span_id'] for e in ends if e['name'] != 'cli.command'))
        result = telemetry.metrics(self.root)
        self.assertEqual('complete', result['coverage'])
        self.assertEqual(2, result['counters']['reader.json'])
        self.assertIsNone(result['tokens_used'])
        self.assertIsNone(result['account_tokens_remaining'])

    def test_forbidden_attributes_are_not_recorded(self):
        with telemetry.TraceRecorder(self.root) as trace:
            with self.assertRaises(ValueError):
                with trace.span('cli.command', url='https://example.org/?token=SECRET'):
                    pass
        self.assertFalse(any('SECRET' in p.read_text() for p in (self.root/'telemetry').glob('*')))

    def test_budget_and_io_failure_leave_the_business_result_unchanged(self):
        with telemetry.TraceRecorder(self.root, max_events=2) as trace:
            for _ in range(4):
                with trace.span('cli.command'):
                    result = 42
        self.assertEqual(42, result)
        self.assertEqual('partial', telemetry.metrics(self.root)['coverage'])
        other = self.root/'other';other.mkdir()
        (other/'telemetry').write_text('Not a directory')
        with telemetry.TraceRecorder(other) as failed:
            with failed.span('cli.command'):
                result = 43
        self.assertEqual(43, result)
        self.assertTrue(failed.diagnostics)

    def test_metrics_read_is_pure_and_historical_run_is_uninstrumented(self):
        state = self.root/'state.json';state.write_text('{}')
        before = list(self.root.rglob('*'))
        result = telemetry.metrics(self.root)
        self.assertEqual('unavailable', result['coverage'])
        self.assertEqual(before, list(self.root.rglob('*')))
        self.assertEqual('{}', state.read_text())

    def write_events(self, rows):
        folder = self.root/'telemetry';folder.mkdir()
        path = folder/'synthetic.jsonl'
        path.write_text(''.join(json.dumps({
            'schema_version': '1.0', 'run_id': self.root.name,
            'trace_id': 't', 'process_id': 'p', 'clock_domain_id': 'c',
            'parent_span_id': None, 'utc': '2026-10-30T10:00:00Z',
            'status': None, 'error_code': None, 'attributes': {}, **r,
        })+'\n' for r in rows))

    def test_nested_intervals_are_not_added_twice(self):
        self.write_events([
            {'span_id':'root','event':'start','name':'cli.command','monotonic_ns':0},
            {'span_id':'a','parent_span_id':'root','event':'start','name':'strategy.validate','monotonic_ns':0},
            {'span_id':'b','parent_span_id':'root','event':'start','name':'research.validate','monotonic_ns':4_000_000_000},
            {'span_id':'a','parent_span_id':'root','event':'end','name':'strategy.validate','monotonic_ns':4_000_000_000,'status':'SUCCEEDED'},
            {'span_id':'b','parent_span_id':'root','event':'end','name':'research.validate','monotonic_ns':10_000_000_000,'status':'SUCCEEDED'},
            {'span_id':'root','event':'end','name':'cli.command','monotonic_ns':10_000_000_000,'status':'SUCCEEDED'},
        ])
        result = telemetry.metrics(self.root)
        self.assertEqual(10, result['work_seconds'])
        self.assertEqual(10, result['instrumented_union_seconds'])
        self.assertEqual(10, result['command_sessions'][0]['wall_seconds'])

    def test_incomplete_span_and_foreign_clock_domains_remain_partial(self):
        self.write_events([
            {'span_id':'root','event':'start','name':'cli.command','monotonic_ns':0},
            {'span_id':'foreign','event':'start','name':'cli.command','process_id':'q','clock_domain_id':'d','monotonic_ns':2},
            {'span_id':'foreign','event':'end','name':'cli.command','process_id':'q','clock_domain_id':'d','monotonic_ns':4,'status':'SUCCEEDED'},
        ])
        result = telemetry.metrics(self.root)
        self.assertEqual('partial', result['coverage'])
        self.assertIsNone(result['instrumented_union_seconds'])
        self.assertTrue(result['trace_errors'])

    def test_cli_metrics_is_available_without_changing_run_state(self):
        state = self.root/'state.json';state.write_text('{}')
        launcher = Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result = subprocess.run([sys.executable, str(launcher), 'metrics', str(self.root)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('unavailable', json.loads(result.stdout)['coverage'])
        self.assertEqual('{}', state.read_text())

    def test_real_strategy_work_exposes_reader_and_inspection_counts(self):
        from test_replay import ReplayTests
        from proposition_runtime import state, strategy
        case = ReplayTests('runTest');case.setUp();self.addCleanup(case.doCleanups)
        with telemetry.TraceRecorder(case.root) as trace:
            with trace.span('cli.command'):
                for stage in ('analysis.specialists','company.v2','brief.public')*2:
                    self.assertEqual('PASS', strategy.inspect(state.load_run(case.root), stage)['status'])
        result = telemetry.metrics(case.root)
        self.assertGreater(result['counters'].get('reader.json', 0), 0)
        self.assertGreater(result['repeated_operations'].get('upstream.inspect', 0), 0)
        self.assertGreater(result['unique_files_hashed'], 0)

    def test_markdown_output_is_human_readable(self):
        launcher = Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        result = subprocess.run([sys.executable, str(launcher), 'metrics', str(self.root), '--format', 'markdown'], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.startswith('# Mesures locales'), result.stdout)

    def test_unknown_fields_and_malformed_events_are_rejected(self):
        self.write_events([
            {'span_id':'root','event':'start','name':'cli.command','monotonic_ns':0,'prompt':'SECRET'},
            {'span_id':'root','event':'end','name':'cli.command','monotonic_ns':1,'status':'SUCCEEDED','prompt':'SECRET'},
        ])
        result = telemetry.metrics(self.root)
        self.assertEqual('partial', result['coverage'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_nested_waits_are_not_added_twice(self):
        self.write_events([
            {'span_id':'root','event':'start','name':'navigation.image_wait','monotonic_ns':0},
            {'span_id':'child','parent_span_id':'root','event':'start','name':'export.font_wait','monotonic_ns':2_000_000_000},
            {'span_id':'child','parent_span_id':'root','event':'end','name':'export.font_wait','monotonic_ns':6_000_000_000,'status':'SUCCEEDED'},
            {'span_id':'root','event':'end','name':'navigation.image_wait','monotonic_ns':10_000_000_000,'status':'SUCCEEDED'},
        ])
        self.assertEqual(10, telemetry.metrics(self.root)['wait_seconds'])

    def test_emitted_events_conform_to_the_closed_contract(self):
        from jsonschema import Draft202012Validator
        schema_path = Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition_runtime/contracts/trace-event.schema.json'
        self.assertTrue(schema_path.is_file(), 'Closed trace event schema is missing')
        validator = Draft202012Validator(json.loads(schema_path.read_text()))
        with telemetry.TraceRecorder(self.root) as trace:
            with trace.span('cli.command'):
                trace.counter('reader.json')
        events = [json.loads(x) for x in next((self.root/'telemetry').glob('*.jsonl')).read_text().splitlines()]
        for event in events:
            validator.validate(event)
            self.assertFalse(validator.is_valid({**event, 'prompt':'Forbidden'}))

    def test_run_trace_limit_cannot_leave_a_false_complete_measurement(self):
        with telemetry.TraceRecorder(self.root) as trace:
            with trace.span('cli.command'):
                pass
        for number in range(telemetry.MAX_FILES-1):
            (self.root/'telemetry'/('empty-'+str(number)+'.jsonl')).write_text('')
        with telemetry.TraceRecorder(self.root) as limited:
            with limited.span('cli.command'):
                result = 42
        self.assertEqual(42,result)
        self.assertTrue(limited.diagnostics)
        self.assertEqual('partial',telemetry.metrics(self.root)['coverage'])
