"""Real state/CAS/lock boundaries, no prospect or remote service."""
import copy
import multiprocessing
from pathlib import Path
import time
import unittest
from contextlib import contextmanager
from unittest.mock import patch
import test_state as fixtures
from proposition_runtime import state


def hold_lock(root,ready,release):
    from proposition_runtime.transactions import run_lock
    with run_lock(root):ready.set();release.wait(3)


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.StateTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups);self.run=self.f.new_run();self.root=Path(self.run['root'])
    def test_stale_loaded_snapshot_cannot_overwrite(self):
        a=state.load_run(self.root);b=state.load_run(self.root);a['metadata']['independent']='current';state.save_run(self.root,a)
        b['metadata']['other']='old'
        with self.assertRaisesRegex(ValueError,'CONFLICT'):state.save_run(self.root,b)
        current=state.load_run(self.root);self.assertEqual('current',current['metadata']['independent']);self.assertNotIn('other',current['metadata'])
    def test_detached_snapshot_needs_explicit_expected_hash(self):
        detached=dict(state.load_run(self.root))
        with self.assertRaisesRegex(ValueError,'expected|snapshot'):state.save_run(self.root,detached)
    def test_reads_are_pure_and_copy_retains_cas(self):
        before=(self.root/'state.json').read_bytes();run=copy.deepcopy(state.load_run(self.root));self.assertEqual(before,(self.root/'state.json').read_bytes());run['metadata']['changed']=True;state.save_run(self.root,run)
        with self.assertRaisesRegex(ValueError,'CONFLICT'):state.save_run(self.root,run)
    def test_real_process_lock_is_bounded_and_persistent(self):
        self.assertTrue(hasattr(state.load_run(self.root),'base_sha256'),'CAS snapshot missing')
        ctx=multiprocessing.get_context('fork');ready=ctx.Event();release=ctx.Event();process=ctx.Process(target=hold_lock,args=(self.root,ready,release));process.start();self.addCleanup(lambda:process.kill() if process.is_alive() else None)
        try:
            self.assertTrue(ready.wait(2));run=state.load_run(self.root);run['metadata']['no']='write';before=(self.root/'state.json').read_bytes();started=time.monotonic()
            with self.assertRaisesRegex(ValueError,'BUSY'):state.save_run(self.root,run)
            self.assertLess(time.monotonic()-started,1.5);self.assertEqual(before,(self.root/'state.json').read_bytes())
        finally:release.set();process.join(3)
        inode=(self.root/'.execution.lock').stat().st_ino;state.save_run(self.root,state.load_run(self.root));self.assertEqual(inode,(self.root/'.execution.lock').stat().st_ino)
    def test_symlink_lock_cannot_redirect_writes(self):
        lock=self.root/'.execution.lock';lock.unlink(missing_ok=True);other=self.root/'other';other.write_bytes(b'private');lock.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'[Ss]ymlink'):state.save_run(self.root,state.load_run(self.root))
        self.assertEqual(b'private',other.read_bytes())
    def test_changed_candidate_between_preparation_and_lock_is_not_adopted(self):
        from proposition_runtime import transactions
        path=self.root/'candidate.txt';path.write_text('prepared');before=(self.root/'state.json').read_bytes();real=transactions.run_lock
        @contextmanager
        def change_before_lock(root):
            path.write_text('replaced')
            with real(root):yield
        with patch.object(transactions,'run_lock',change_before_lock):
            with self.assertRaisesRegex(ValueError,'CONFLICT|changed'):state.add_artifact(self.root,'candidate','candidate.txt','internal')
        self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_observed_method_change_before_commit_cannot_be_hidden_by_write(self):
        from proposition_runtime import transactions
        from proposition_runtime.validation import ValidationSession
        method=self.root/'method.txt';method.write_text('versionA');(self.root/'candidate.txt').write_text('prepared');before=(self.root/'state.json').read_bytes();real=transactions.run_lock
        @contextmanager
        def change_method(root):
            method.write_text('versionB')
            with real(root):yield
        with self.assertRaisesRegex(ValueError,'CONFLICT|changed'):
            with ValidationSession():
                state._sha(method)
                with patch.object(transactions,'run_lock',change_method):state.add_artifact(self.root,'candidate','candidate.txt','internal')
        self.assertEqual(before,(self.root/'state.json').read_bytes())
    def test_deep_acyclic_graph_is_not_limited_by_python_recursion(self):
        run=state.load_run(self.root);run['artifacts']={f'n{i:04d}':{'status':'CURRENT','dependencies':([f'artifact:n{i+1:04d}'] if i<1499 else [])} for i in range(1500)}
        failure=None
        try:state._validate_active_graph(run)
        except RecursionError as error:failure=error
        self.assertIsNone(failure,'A bounded valid dependency graph must not overflow Python recursion')
