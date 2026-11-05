"""Consumer installation belongs to its workspace, never the distribution repo."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.source = self.base / 'kit'
        shutil.copytree(ROOT / 'skills', self.source / 'skills',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (self.source / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/install.py', self.source / 'scripts/install.py')
        (self.source / '.venv/bin').mkdir(parents=True)
        (self.source / '.venv/bin/python').symlink_to(sys.executable)
        self.workspace = self.base / 'my-private-workspace'
        self.workspace.mkdir()
        (self.workspace / 'README.md').write_text('My own workspace; keep this file.')
        spec = importlib.util.spec_from_file_location('setup_under_test', ROOT / 'scripts/setup.py')
        self.setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.setup)
        self.setup.__file__ = str(self.source / 'scripts/setup.py')

    def invoke(self, *args, doctor_status='PASS'):
        real_run = subprocess.run
        self.commands=[]

        def external(command, **kwargs):
            self.commands.append(command)
            if str(self.source / 'scripts/install.py') in command:
                return real_run(command, **kwargs)
            if 'doctor' in command:
                return subprocess.CompletedProcess(command, 0 if doctor_status == 'PASS' else 1,
                    stdout=json.dumps({'status': doctor_status, 'scope': 'local_runtime_only'}), stderr='')
            if 'publication-setup' in command:
                return subprocess.CompletedProcess(command,0,stdout=json.dumps({'status':'READY',
                    'authority':'explicit_installation_only','per_run_target':'preview'}),stderr='')
            # Dependency downloads and apt require network/admin, exercised by the
            # separate real installation probe, not by this filesystem test.
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

        output = io.StringIO()
        with patch.object(sys, 'argv', ['setup.py', *map(str, args)]), \
             patch.object(self.setup.subprocess, 'run', side_effect=external), \
             patch.object(self.setup.Path, 'home', return_value=self.base / 'home'), \
             contextlib.redirect_stdout(output):
            code = self.setup.main()
        return code, json.loads(output.getvalue().splitlines()[-1])

    def invoke_supported(self,*args):
        try:return self.invoke(*args)
        except SystemExit as error:self.fail('Required starter options are unavailable (exit '+str(error.code)+')')

    def test_claude_workspace_gets_its_own_skills_entry_and_private_web_profile(self):
        entry=self.workspace/'CLAUDE.md';entry.write_text('Keep my existing project instructions.\n')
        code,result=self.invoke_supported('--workspace',self.workspace,'--host','claude','--owner','fixture-owner')
        self.assertEqual(code,0,result)
        self.assertTrue((self.workspace/'.claude/skills/proposition/SKILL.md').is_file())
        self.assertFalse((self.workspace/'.agents/skills').exists())
        self.assertTrue(entry.read_text().startswith('Keep my existing project instructions.'))
        profile=json.loads((self.workspace/'.vertigo/profile.json').read_text())
        self.assertEqual(profile['parameters']['delivery_format'],'web')
        self.assertEqual(profile['responsible'],'fixture-owner')
        self.assertTrue(profile['responsible_confirmed'])
        self.assertEqual(result['host'],'claude')

    def test_web_browser_setup_installs_both_required_engines_once(self):
        code,result=self.invoke_supported('--workspace',self.workspace,'--host','codex','--browser')
        self.assertEqual(code,0,result)
        commands=[c for c in self.commands if 'playwright' in c and 'install' in c]
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][-2:],['chromium','webkit'])

    def test_publication_setup_is_explicit_once_and_requires_a_workspace_owner(self):
        code,result=self.invoke_supported('--workspace',self.workspace,'--owner','fixture-owner','--with-publication')
        self.assertEqual(code,0,result)
        commands=[c for c in self.commands if 'publication-setup' in c]
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][-2:],['--owner','fixture-owner'])
        self.assertEqual(result['publication']['per_run_target'],'preview')
        with self.assertRaises(SystemExit):
            self.invoke('--workspace',self.workspace,'--with-publication')

    def test_documentary_workspace_profile_remains_explicitly_selectable(self):
        code,result=self.invoke_supported('--workspace',self.workspace,'--delivery-format','documents')
        self.assertEqual(code,0,result)
        profile=json.loads((self.workspace/'.vertigo/profile.json').read_text())
        self.assertEqual(profile['parameters']['delivery_format'],'documents')

    def test_workspace_installs_all_skills_without_changing_source_or_user_files(self):
        before = {str(p.relative_to(self.source)): p.read_bytes()
                  for p in (self.source / 'skills').rglob('*') if p.is_file()}
        code, result = self.invoke('--workspace', self.workspace)
        self.assertEqual(code, 0)
        self.assertEqual((self.workspace / 'README.md').read_text(), 'My own workspace; keep this file.')
        installed = self.workspace / '.agents/skills'
        manifest = json.loads((installed / '.proposition-install.json').read_text())
        self.assertEqual(len(manifest['skills']), 9)
        self.assertEqual({str(p.relative_to(self.source)): p.read_bytes()
                          for p in (self.source / 'skills').rglob('*') if p.is_file()}, before)
        self.assertFalse((self.base / 'home/.codex/skills').exists())
        receipt = json.loads((self.workspace / '.vertigo/setup.json').read_text())
        self.assertEqual(receipt['skills_destination'], str(installed))
        self.assertEqual(receipt['host_capabilities'], 'NOT_VERIFIED_BY_INSTALLER')
        self.assertEqual(receipt['prospect_e2e'], 'NOT_RUN')
        self.assertEqual(result['installation'], 'INSTALLED')

    def test_workspace_inside_distribution_is_refused_before_installation(self):
        (self.source / 'client-output').mkdir()
        with self.assertRaises(SystemExit) as error:
            self.invoke('--workspace', self.source / 'client-output')
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.source / 'client-output/.agents').exists())

    def test_installed_runtime_allows_its_private_git_workspace_but_protects_the_source_kit(self):
        (self.workspace/'.git').mkdir()
        nested=self.workspace/'.vertigo/kit';nested.parent.mkdir()
        shutil.move(self.source,nested);self.source=nested
        self.setup.__file__=str(self.source/'scripts/setup.py')
        for host,folder in [('codex','.agents'),('claude','.claude')]:
            code,result=self.invoke('--workspace',self.workspace,'--host',host)
            self.assertEqual(code,0,result)
            launcher=self.workspace/folder/'skills/proposition/scripts/proposition.py'
            # Dependency installation is doubled in this filesystem fixture. Use
            # the test interpreter with real installed dependencies for the child.
            config=launcher.parents[1]/'installation.json';settings=json.loads(config.read_text())
            settings['runtime_python']=sys.executable;config.write_text(json.dumps(settings))
            command=[sys.executable,str(launcher),'init','https://fixture.example/',
                '--runs-root',str(self.workspace/'outputs'),'--delivery-format','web']
            result=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            root=Path(json.loads(result.stdout)['root'])
            self.assertTrue(root.is_relative_to(self.workspace/'outputs'))
            command[command.index('--runs-root')+1]=str(self.source/'forbidden')
            result=subprocess.run(command,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.source/'forbidden').exists())

    def test_blocked_doctor_is_not_reported_as_a_ready_workflow(self):
        code, result = self.invoke('--workspace', self.workspace, doctor_status='BLOCKED')
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['host_capabilities'], 'NOT_VERIFIED_BY_INSTALLER')

    def test_system_install_requires_explicit_root_linux_context(self):
        with patch.object(self.setup.sys, 'platform', 'linux'), \
             patch.object(self.setup.os, 'geteuid', return_value=1000):
            with self.assertRaises(SystemExit) as error:
                self.invoke('--workspace', self.workspace, '--browser', '--with-system-deps')
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.workspace / '.agents').exists())

    def test_receipt_symlink_cannot_overwrite_an_unrelated_file(self):
        outside = self.base / 'keep.json'
        outside.write_text('Keep my file')
        (self.workspace / '.vertigo').mkdir()
        (self.workspace / '.vertigo/setup.json').symlink_to(outside)
        with self.assertRaises(SystemExit) as error:
            self.invoke('--workspace', self.workspace)
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(outside.read_text(), 'Keep my file')

    def test_fresh_runtime_python_can_execute_after_creation(self):
        shutil.rmtree(self.source / '.venv')
        code, result = self.invoke('--workspace', self.workspace)
        self.assertEqual(code, 0, result)
        python = self.source / '.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        executed = subprocess.run([str(python), '-c', 'print("runtime starts")'],capture_output=True,text=True)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout.strip(), 'runtime starts')


    def test_setup_can_reference_the_cloud_personal_variable_without_copying_its_secret(self):
        code,result=self.invoke_supported('--workspace',self.workspace,'--owner','fixture-owner',
            '--with-publication','--vercel-org','team_fixture',
            '--vercel-credential-ref','env:VERTIGO_VERCEL_TOKEN')
        self.assertEqual(code,0,result)
        command=next(c for c in self.commands if 'publication-setup' in c)
        self.assertEqual(command[command.index('--credential-ref')+1],'env:VERTIGO_VERCEL_TOKEN')


if __name__ == '__main__':
    unittest.main()
