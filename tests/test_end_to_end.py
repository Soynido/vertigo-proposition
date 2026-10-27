"""Installed skill -> persisted evidence -> three real PDF -> changed-byte invalidation.

This is a mechanical fixture, not a client proposal or a creative-quality pass.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from proposition_runtime import state

ROOT = Path(__file__).resolve().parents[1]


class EndToEndTests(unittest.TestCase):
    def test_clean_installed_skill_exports_three_audiences_without_fake_final_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            spec = importlib.util.spec_from_file_location('installer_e2e', ROOT/'scripts/install.py')
            installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
            installed = base/'skills'
            result = installer.install_repo(ROOT, installed)
            self.assertEqual(len(result['skills']),9)
            launcher = installed/'proposition/scripts/proposition.py'
            def command(*args, success=True):
                result = subprocess.run([sys.executable,str(launcher),*map(str,args)],cwd=base,text=True,capture_output=True)
                self.assertEqual(result.returncode == 0, success, result.stdout+result.stderr)
                return json.loads(result.stdout)
            run = command('init','https://fixture.example','--runs-root',base/'runs')
            run_dir = Path(run['root'])
            source = run_dir/'evidence.txt'; source.write_text('Fictional company evidence, not a real prospect.')
            state.add_source(run_dir,'fixture',source,kind='observation')
            for audience in ('client','sales','technical'):
                folder = run_dir/audience; folder.mkdir()
                (folder/'index.html').write_text(f'''<!doctype html><html lang="fr"><meta charset="utf-8">
                <style>@page{{size:A4 landscape;margin:18mm}}body{{font:20px sans-serif}}h1{{font-size:48px}}</style>
                <h1>Fixture de vérification — {audience}</h1><p>Source éditable. Contrôle mécanique uniquement.</p>
                <p>Aucun dossier client réel, aucune proposition créative validée.</p></html>''')
                export = command('export',folder/'index.html',folder/'document.pdf','--audience',audience)
                self.assertEqual(export['page_count'],1)
                report = command('inspect',folder/'document.pdf','--output',folder/'inspection','--audience',audience)
                self.assertEqual(report['scope'],'mechanical_only')
                self.assertEqual(report['visual_review'],'NOT_RUN')
                self.assertTrue((folder/'inspection/page-001.png').is_file())
                state.add_artifact(run_dir,f'{audience}-source',f'{audience}/index.html',audience,['source:fixture'])
                state.add_artifact(run_dir,f'{audience}-pdf',f'{audience}/document.pdf',audience,[f'artifact:{audience}-source'])
            receipt = command('receipt',run_dir)
            self.assertEqual(receipt['counts']['artifacts'],6)
            self.assertNotEqual(receipt['quality'],'PASS')
            client_source = run_dir/'client/index.html'
            client_source.write_text(client_source.read_text().replace('Source éditable','Source modifiée'))
            original_pdf=(run_dir/'client/document.pdf').read_bytes()
            command('export',client_source,run_dir/'client/document.pdf','--audience','client',success=False)
            self.assertEqual((run_dir/'client/document.pdf').read_bytes(),original_pdf)
            export = command('export',client_source,run_dir/'client/document-r2.pdf','--audience','client')
            invalidated = state.invalidate_changed(run_dir)
            self.assertIn('artifact:client-source',invalidated['invalidated'])
            self.assertIn('artifact:client-pdf',invalidated['invalidated'])
            # New-kit handoffs consume the client revision, even when their bytes are unchanged.
            self.assertEqual(state.load_run(run_dir)['artifacts']['sales-pdf']['status'],'STALE')
            self.assertFalse((run_dir/'publication-receipt.json').exists())


if __name__ == '__main__': unittest.main()
