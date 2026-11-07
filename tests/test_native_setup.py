"""Reject an altered isolated transport instead of using a global executable."""
import hashlib,json,os
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
try:
    from proposition_runtime import native_setup as ns
except ImportError:ns=None

class NativeSetupTests(unittest.TestCase):
    def test_changed_native_binary_is_rejected_even_if_wrapper_is_unchanged(self):
        self.assertIsNotNone(ns,'Pinned native installer is missing')
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CACHE_HOME':str(Path(tmp).resolve())}):
            source,cache,version=ns._paths();base=cache/'node_modules/@openai/codex';base.mkdir(parents=True)
            exe=base/'codex.js';exe.write_text('wrapper');exe.chmod(0o700)
            native=base/'vendor/bin/codex';native.parent.mkdir(parents=True);native.write_bytes(b'native')
            (base/'package.json').write_text(json.dumps({'version':version,'bin':{'codex':'codex.js'}}))
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            (cache/'CLI-CHECK.json').write_text(json.dumps({'version':version,'lock_sha256':sha(source/'package-lock.json'),
                'executable_sha256':sha(exe),'native_files':{native.relative_to(cache).as_posix():sha(native)}}))
            self.assertEqual(str(exe),ns.locate_codex_cli())
            native.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Native executable'):ns.locate_codex_cli()

if __name__=='__main__':unittest.main()
