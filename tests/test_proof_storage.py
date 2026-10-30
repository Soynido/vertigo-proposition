"""Exact byte-addressed proof publication and unchanged observation identities."""
from concurrent.futures import ThreadPoolExecutor
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_state as fixtures
from discovery_fixture import write_report
from proposition_runtime import discovery,discovery_evidence,state

class ProofStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();(self.root/'sources').mkdir()
    def write(self,stem,kind,content):
        self.assertTrue(hasattr(discovery,'write_proof'),'Exact content-addressed publisher missing')
        return discovery.write_proof(self.root,stem,kind,content,'content_addressed')
    def test_same_bytes_share_path_but_distinct_bytes_do_not(self):
        a=self.write('one','txt','é\n');b=self.write('two','txt','é\n');c=self.write('three','txt','é\r\n')
        self.assertEqual(a,b);self.assertNotEqual(a,c)
        self.assertEqual('é\n'.encode(),a.read_bytes());self.assertIn('/sources/blobs/',str(a))
    def test_concurrent_publish_converges_without_overwrite(self):
        self.assertTrue(hasattr(discovery,'write_proof'),'Atomic publisher missing')
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths=list(pool.map(lambda i:discovery.write_proof(self.root,str(i),'html','<h1>same</h1>','content_addressed'),range(12)))
        self.assertEqual(1,len(set(paths)));self.assertEqual(1,len(list((self.root/'sources/blobs').iterdir())))
        paths[0].write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'integrity'):self.write('again','html','<h1>same</h1>')
        self.assertEqual(b'corrupt',paths[0].read_bytes())
    def test_symlink_blob_refused_and_png_not_deduplicated(self):
        import hashlib
        digest=hashlib.sha256(b'x').hexdigest();blob=self.root/'sources/blobs';blob.mkdir();target=self.root/'target';target.write_bytes(b'x');(blob/(digest+'.txt')).symlink_to(target)
        with self.assertRaisesRegex(ValueError,'[Ss]ymlink'):self.write('x','txt','x')
        with self.assertRaises(ValueError):self.write('image','png','x')
    def test_conflicting_repeated_descriptor_refused_before_adoption(self):
        f=fixtures.StateTests('runTest');f.setUp();self.addCleanup(f.doCleanups);run=f.new_run();path=write_report(run);data=json.loads(path.read_text())
        repeated=dict(data['sources'][0]['artifacts'][0]);repeated['encoding']='contradictory';data['sources'][1]['artifacts'].append(repeated);path.write_text(json.dumps(data))
        before=(Path(run['root'])/'state.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'descriptor'):discovery_evidence.register(run['root'],path)
        self.assertEqual(before,(Path(run['root'])/'state.json').read_bytes())
    def test_collect_and_continue_expose_storage_switch(self):
        for fn in (discovery.collect,discovery.continue_collect):self.assertIn('proof_storage',inspect.signature(fn).parameters)
    def test_continuation_rejects_conflicting_descriptors_before_collection(self):
        f=fixtures.StateTests('runTest');f.setUp();self.addCleanup(f.doCleanups);run=f.new_run();path=write_report(run);data=json.loads(path.read_text())
        data['coverage']['omitted_urls']=[]
        repeated=dict(data['sources'][0]['artifacts'][0]);repeated['encoding']='contradictory';data['sources'][1]['artifacts'].append(repeated);path.write_text(json.dumps(data))
        problem=None
        with patch.object(discovery,'_collect',side_effect=AssertionError('network path entered')):
            try:discovery.continue_collect(path,self.root/'next')
            except Exception as error:problem=error
        self.assertIsInstance(problem,ValueError);self.assertIn('descriptor',str(problem))
