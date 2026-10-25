"""A montage restart must not wait indefinitely or overwrite prior exports."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from proposition_runtime import state, artifacts
try:
    from proposition_runtime import recovery
except ImportError:
    recovery = None


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = state.init_run('https://example.test', self.base/'runs')
        self.root = Path(self.run['root'])

    def prepare(self, entries, **kwargs):
        self.assertIsNotNone(recovery, 'Bounded input recovery is missing')
        manifest = self.root/'inputs.json'
        manifest.write_text(json.dumps({'inputs':entries}))
        return recovery.prepare_inputs(self.root, manifest, self.base/'local', **kwargs)

    def test_copies_only_explicit_inputs_and_verifies_expected_bytes(self):
        (self.root/'scene.png').write_bytes(b'fixture-scene')
        (self.root/'irrelevant').write_text('do not traverse')
        digest=hashlib.sha256(b'fixture-scene').hexdigest()
        result=self.prepare([{'id':'scene','path':'scene.png','sha256':digest}])
        self.assertEqual(result['status'],'PASS')
        self.assertEqual((self.base/'local/scene.png').read_bytes(),b'fixture-scene')
        self.assertFalse((self.base/'local/irrelevant').exists())

    def test_missing_input_reports_checkpoint_instead_of_research_restart(self):
        result=self.prepare([{'id':'missing','path':'absent','sha256':'a'*64}])
        self.assertEqual(result['status'],'PARTIAL')
        self.assertEqual(result['inputs'][0]['status'],'UNAVAILABLE')
        self.assertTrue((self.base/'local/input-receipt.json').is_file())

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX bounded stalled-read fixture')
    def test_stalled_open_is_interrupted_by_parent_deadline(self):
        os.mkfifo(self.root/'stalled')
        started=time.monotonic()
        result=self.prepare([{'id':'stalled','path':'stalled','sha256':'a'*64}],timeout_seconds=0.2)
        self.assertLess(time.monotonic()-started,2)
        self.assertEqual(result['status'],'PARTIAL')

    def test_hash_mismatch_is_not_silently_refreshed(self):
        (self.root/'scene').write_text('changed')
        result=self.prepare([{'id':'scene','path':'scene','sha256':'a'*64}])
        self.assertEqual(result['status'],'PARTIAL')
        self.assertFalse((self.base/'local/scene').exists())

    def test_export_refuses_to_overwrite_before_starting_renderer(self):
        source=self.root/'page.html'; source.write_text('<h1>New</h1>')
        output=self.root/'approved.pdf'; output.write_bytes(b'approved bytes')
        with self.assertRaisesRegex(ValueError,'exists|revision'):
            artifacts.export_pdf(source,output)
        self.assertEqual(output.read_bytes(),b'approved bytes')

    def test_staged_names_cannot_collide_with_receipt(self):
        (self.root/'proof.json').write_text('{}')
        with self.assertRaises(ValueError):
            self.prepare([{'id':'input-receipt','path':'proof.json','sha256':hashlib.sha256(b'{}').hexdigest()}])

    def test_temporary_name_cannot_delete_an_earlier_ready_input(self):
        (self.root/'one').write_bytes(b'one');(self.root/'two').write_bytes(b'two')
        with self.assertRaises(ValueError):
            self.prepare([{'id':'scene.partial','path':'one','sha256':hashlib.sha256(b'one').hexdigest()},
                          {'id':'scene','path':'two','sha256':hashlib.sha256(b'two').hexdigest()}])

    def test_case_insensitive_destination_names_are_rejected_portably(self):
        (self.root/'one').write_bytes(b'one');(self.root/'two').write_bytes(b'two')
        with self.assertRaises(ValueError):
            self.prepare([{'id':'SCENE','path':'one','sha256':hashlib.sha256(b'one').hexdigest()},
                          {'id':'scene','path':'two','sha256':hashlib.sha256(b'two').hexdigest()}])


if __name__=='__main__': unittest.main()
