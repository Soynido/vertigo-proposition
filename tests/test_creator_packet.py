"""The frozen creator packet and its actual reading receipt are one contract."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

import test_state as fixtures
from experience_fixture import prepare_inputs
from web_fixture import prepare_web
from proposition_runtime import execution, state


class CreatorPacketTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.StateTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.run = fixture.new_run()
        self.root = Path(self.run['root'])
        self.inputs, _, _ = prepare_inputs(self.run)

    def packet(self, key='creative.direction.prepare', run=None, spec=None, omitted_contract=False):
        current = state.load_run(self.root if run is None else run['root'])
        root = Path(current['root'])
        spec = spec or next(s for s in execution._specs() if s['task_key'] == key)
        row = current['artifacts']['creative-inputs']
        selected = [execution._descriptor(root, root/row['path'], 'input', 'public')]
        plan = {'task_id': 'task-' + 'a'*24, 'task_key': key,
                'packet_plan': {'kind': 'creative_public', 'files': selected, 'record_refs': [],
                                'allowed_audiences': spec['audiences']},
                'input_hashes': {}, 'input_parameters': {'delivery_format': state.delivery_format(current)},
                'output_destinations': {name: 'output/'+name for name in spec['outputs']},
                'isolation': {'mode': spec['isolation'], 'creator_context_ref': None}}
        directory = root/'.execution/inputs'/key.replace('.', '-')
        directory.mkdir(parents=True)
        originals = execution._instruction_files
        def instructions(skill):
            paths = originals(skill)
            return {p for p in paths if p.name != 'creative-contract.md'} if omitted_contract else paths
        with patch.object(state, '_stage_report', return_value={'status': 'PASS'}), \
             patch('proposition_runtime.experience.require_packet_methods'), \
             patch.object(execution, '_creative_allowed', return_value=True), \
             patch.object(execution, '_instruction_files', side_effect=instructions), \
             patch.object(execution, '_method_files', return_value=({}, [])):
            packet = execution._freeze_packet(root, directory, current, plan, spec)
        return packet, directory

    def test_contract_read_is_required_by_actual_receipt(self):
        packet, _ = self.packet()
        self.assert_contract_receipt(self.root, packet, 'fresh_public')

    def assert_contract_receipt(self, root, packet, mode):
        manifest = execution._validate_packet(root, packet)
        contract = next(d for d in manifest['files'] if d['path'].endswith('/proposition-creative/references/creative-contract.md'))
        attempt = {'attempt_id': 'attempt-' + 'b'*32, 'request_hash': 'c'*64, 'host_job_ref': 'fixture-job'}
        receipt = {'schema_version': '1.0', 'attempt_id': attempt['attempt_id'],
                   'request_hash': attempt['request_hash'], 'manifest_hash': packet['manifest_hash'],
                   'worker_id': 'fixture-reader', 'host_job_ref': attempt['host_job_ref'],
                   'kind': 'agent_declared_reading', 'observed_at': datetime.now(timezone.utc).isoformat(),
                   'read_files': [{k: d[k] for k in ('path', 'sha256', 'size_bytes')}
                                  for d in manifest['files'] if d['path'] in manifest['required_reads'] and d['path'] != contract['path']],
                   'limitations': []}
        path = root/'receipt.json'
        path.write_text(json.dumps(receipt))
        result = {'consumed_packet_hash': packet['manifest_hash'],
                  'read_receipt_ref': {'path': path.name, 'sha256': state._sha(path), 'size_bytes': path.stat().st_size}}
        request = {'packet': packet, 'isolation': {'mode': mode}}
        with self.assertRaisesRegex(ValueError, 'omits mandatory'):
            execution._read_receipt(root, result, request, attempt)
        self.assertIn(contract['path'], manifest['required_reads'])
        receipt['read_files'].append({k: contract[k] for k in ('path', 'sha256', 'size_bytes')})
        path.write_text(json.dumps(receipt))
        result['read_receipt_ref'] = {'path': path.name, 'sha256': state._sha(path), 'size_bytes': path.stat().st_size}
        execution._read_receipt(root, result, request, attempt)

    def test_each_creator_phase_has_frozen_capsule_objective_and_specific_work(self):
        expectations = {
            'creative.direction.prepare': ('prepare', 'creative-reading', 'Ne pas rendre de scènes'),
            'creative.direction.explore': ('explore', 'creative-exploration', 'comparer les scènes exactes'),
            'creative.direction.develop': ('develop', 'creative-experience', 'directions retenues'),
        }
        for key, (phase, output, phrase) in expectations.items():
            packet, directory = self.packet(key)
            native = json.loads((directory/'native-task.json').read_text())
            task = native['task']
            self.assertEqual(phase, task['phase'])
            self.assertIn(phrase, task['instruction'])
            self.assertIn(output, native['output_destinations'])
            self.assertEqual(self.inputs['opportunity'], task['business_objective'])
            contract = self.root/task['creative_contract']['path']
            self.assertEqual(state._sha(contract), task['creative_contract']['sha256'])
            self.assertIn('au moins deux réponses créatives', task['dispatch_capsule'])
            self.assertIn(task['creative_contract']['path'], execution._validate_packet(self.root, packet)['required_reads'])
            self.assertNotIn('déléguer', task['instruction'].lower())
            self.assertNotIn('état', task['instruction'].lower())

    def test_web_continuation_has_plan_then_build_without_new_selection(self):
        with TemporaryDirectory() as tmp:
            run, _, _ = prepare_web(tmp)
            root = Path(run['root'])
            current = state.load_run(root)
            for key, phase, phrase in [('client.composition.plan', 'web_plan', 'avant tout HTML'),
                                       ('client.composition.build', 'web_build', 'sans refaire une sélection')]:
                spec = next(s for s in execution._format_specs(current) if s['task_key'] == key)
                packet, directory = self.packet(key, current, spec)
                native = json.loads((directory/'native-task.json').read_text())
                self.assertEqual(phase, native['task']['phase'])
                self.assertIn(phrase, native['task']['instruction'])
                self.assertEqual('continue_public', native['isolation']['mode'])
                self.assertIn(native['task']['creative_contract']['path'], execution._validate_packet(root, packet)['required_reads'])
                self.assertFalse(any(d['audience'] == 'private' for d in packet['files']))
                self.assert_contract_receipt(root, packet, 'continue_public')

    def test_missing_frozen_contract_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'requires its frozen creative contract'):
            self.packet(omitted_contract=True)

    def test_objective_is_taken_from_the_frozen_input(self):
        _, directory = self.packet()
        original = self.root/state.load_run(self.root)['artifacts']['creative-inputs']['path']
        original.write_text(json.dumps({'opportunity': {'task': 'Changed mutable source'}}))
        native = json.loads((directory/'native-task.json').read_text())
        self.assertEqual(self.inputs['opportunity'], native['task']['business_objective'])
        self.assertEqual(self.inputs['opportunity'], json.loads((directory/'files/creative-inputs.json').read_text())['opportunity'])

    def test_noncreative_document_task_keeps_its_existing_native_boundary(self):
        spec = next(s for s in execution._specs() if s['task_key'] == 'client.composition.plan')
        plan = {'task_id': 'task-' + 'a'*24, 'task_key': spec['task_key'],
                'packet_plan': {'kind': spec['packet'], 'files': [], 'record_refs': [],
                                'allowed_audiences': spec['audiences']},
                'input_hashes': {}, 'input_parameters': {'delivery_format': 'documents'},
                'output_destinations': {}, 'isolation': {'mode': spec['isolation'], 'creator_context_ref': None}}
        directory = self.root/'.execution/inputs/document-composition'
        directory.mkdir(parents=True)
        with patch.object(execution, '_method_files', return_value=({}, [])):
            packet = execution._freeze_packet(self.root, directory, state.load_run(self.root), plan, spec)
        native = json.loads((directory/'native-task.json').read_text())
        self.assertNotIn('task', native)
        self.assertEqual('private_internal', packet['kind'])


if __name__ == '__main__':
    unittest.main()
