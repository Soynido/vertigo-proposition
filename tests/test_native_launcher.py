"""A launcher's private re-exec marker must not poison a different process."""
import json,os
from pathlib import Path
import shutil,subprocess,sys,tempfile,unittest,venv

class NativeLauncherTests(unittest.TestCase):
    def test_inherited_marker_does_not_skip_the_installed_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();scripts=root/'skill/scripts';scripts.mkdir(parents=True)
            source=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
            shutil.copyfile(source,scripts/'proposition.py')
            venv.EnvBuilder(with_pip=False,symlinks=os.name!='nt').create(root/'configured')
            target=root/'configured'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            (root/'skill/installation.json').write_text(json.dumps({'runtime_python':str(target)}))
            package=scripts/'proposition_runtime';package.mkdir();(package/'__init__.py').write_text('')
            (package/'cli.py').write_text('import json,sys\ndef main():\n print(json.dumps({"interpreter":sys.executable}))\n return 0\n')
            result=subprocess.run([sys.executable,str(scripts/'proposition.py')],env=dict(os.environ,PROPOSITION_REEXEC='1'),
                capture_output=True,text=True,timeout=10)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual(str(target),json.loads(result.stdout)['interpreter'])

if __name__=='__main__':unittest.main()
