import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


class DistributionTests(unittest.TestCase):
    def test_scan_cannot_pass_different_bytes_from_the_git_index(self):
        script = Path(__file__).parents[1]/'scripts/check_distribution.py'
        spec = importlib.util.spec_from_file_location('distribution_check',script)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            subprocess.run(['git','init','-q',str(root)],check=True)
            for name in ['proposition']+[f'fixture-{i}' for i in range(8)]:
                folder=root/'skills'/name; folder.mkdir(parents=True)
                (folder/'SKILL.md').write_text(f'---\nname: {name}\ndescription: Test fixture.\n---\n')
            package=root/'skills/proposition/scripts/proposition_runtime'
            (package/'data').mkdir(parents=True); (package/'contracts').mkdir()
            (package/'data/requirements.json').write_text(json.dumps({'requirements':[{'id':f'R{i:02}'} for i in range(1,82)]}))
            selected=root/'selected.txt'
            selected.write_text('gh'+'p_'+'A'*40)
            subprocess.run(['git','add','.'],cwd=root,check=True)
            selected.write_text('Safe working copy; unsafe index retained')
            report=module.check(root)
            self.assertNotEqual(report['status'],'PASS')
            self.assertTrue(any('index' in issue.lower() or 'secret' in issue.lower() for issue in report['issues']))


if __name__=='__main__': unittest.main()
