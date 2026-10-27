"""Explicit local setup. Review this file before running an unfamiliar checkout."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--dest', type=Path, help='Explicit skills destination; legacy default is ~/.codex/skills')
    target.add_argument('--workspace', type=Path, help='Own workspace: install into its .agents/skills, outside the source kit')
    parser.add_argument('--browser', action='store_true', help='Download the pinned Playwright Chromium build')
    parser.add_argument('--with-upstream', action='store_true', help='Fetch pinned open source skill distributions without executing them')
    parser.add_argument('--with-presentations', action='store_true', help='Install the locked python-pptx profile and test authoring, editing and rendering')
    parser.add_argument('--with-system-deps', action='store_true', help='Explicitly install Linux browser/LibreOffice packages; requires root, never invokes sudo')
    parser.add_argument('--update', action='store_true')
    a = parser.parse_args()
    if sys.version_info < (3,11): parser.error('Python 3.11 or newer is required')
    root = Path(__file__).resolve().parents[1]
    workspace = a.workspace.expanduser() if a.workspace else None
    if workspace:
        if workspace.is_symlink() or not workspace.is_dir():
            parser.error('--workspace must be an existing non-symlink directory')
        workspace = workspace.resolve()
        if workspace.is_relative_to(root):
            parser.error('The workspace must be outside the distribution checkout')
        for folder in (workspace / '.agents', workspace / '.agents/skills', workspace / '.vertigo', workspace / '.vertigo/setup.json'):
            if folder.is_symlink():
                parser.error('Workspace installation directories cannot be symlinks')
    destination = (workspace / '.agents/skills' if workspace else
                   (a.dest or Path.home() / '.codex/skills').expanduser())
    if destination.resolve().is_relative_to(root):
        parser.error('Install skills outside the distribution checkout')
    if a.with_system_deps:
        if sys.platform != 'linux' or not hasattr(os, 'geteuid') or os.geteuid() != 0:
            parser.error('--with-system-deps requires an explicitly authorized root Linux setup; no automatic elevation')
        if not (a.browser or a.with_presentations):
            parser.error('--with-system-deps requires --browser or --with-presentations')
        if a.with_presentations and not shutil.which('apt-get'):
            parser.error('The explicit system presentation install requires apt-get; install a renderer separately')
    runtime = root / '.venv'
    if runtime.is_symlink(): parser.error('The local runtime cannot be a symlink')
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    launcher = destination.resolve() / 'proposition/scripts/proposition.py'
    report = {'status': 'BLOCKED', 'installation': 'NOT_COMPLETED', 'scope': 'installation_and_local_tools_only',
              'source_checkout': str(root), 'skills_destination': str(destination.resolve()),
              'launcher': str(launcher), 'host_capabilities': 'NOT_VERIFIED_BY_INSTALLER',
              'prospect_e2e': 'NOT_RUN', 'profile': 'presentations' if a.with_presentations else 'core',
              'required_mcp': [], 'source_write_access_required': False}
    for key, revision in (('source_commit', 'HEAD'), ('source_tree', 'HEAD^{tree}')):
        try:
            resolved = subprocess.run(['git','-C',str(root),'rev-parse',revision],
                                      capture_output=True,text=True,check=True,timeout=5)
            report[key] = resolved.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            report[key] = None
    try:
        changed = subprocess.run(['git','-C',str(root),'status','--porcelain'],
                                 capture_output=True,text=True,check=True,timeout=5)
        report['source_worktree_dirty'] = bool(changed.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        report['source_worktree_dirty'] = None
    phase = 'venv'
    try:
        if not python.is_file():
            venv.EnvBuilder(with_pip=not bool(shutil.which('uv')), symlinks=os.name != 'nt').create(runtime)
        phase = 'dependencies'
        lock = root / ('requirements-presentations.lock' if a.with_presentations else 'requirements.lock')
        if shutil.which('uv'):
            command = ['uv','pip','install','--python',str(python),'--require-hashes','-r',str(lock)]
        else:
            command = [str(python),'-m','pip','install','--require-hashes','-r',str(lock)]
        subprocess.run(command,check=True)
        phase = 'browser'
        if a.browser:
            command = [str(python),'-m','playwright','install']
            if a.with_system_deps: command.append('--with-deps')
            subprocess.run(command + ['chromium'],check=True)
        phase = 'presentation_renderer'
        if a.with_system_deps and a.with_presentations:
            subprocess.run(['apt-get','update'],check=True,timeout=600)
            subprocess.run(['apt-get','install','-y','--no-install-recommends',
                            'libreoffice-impress','fonts-dejavu-core'],check=True,timeout=900)
        phase = 'skills'
        command = [str(python),str(root/'scripts/install.py'),'--dest',str(destination),'--source',str(root)]
        if a.update: command.append('--update')
        subprocess.run(command,check=True)
        report['installation'] = 'INSTALLED'
        phase = 'upstream'
        if a.with_upstream:
            subprocess.run([str(python),str(launcher),'upstream','fetch'],check=True)
        phase = 'doctor'
        command = [str(python),str(launcher),'doctor']
        if a.with_presentations: command.append('--presentations')
        checked = subprocess.run(command,check=False,capture_output=True,text=True,timeout=150)
        report['doctor_exit'] = checked.returncode
        report['doctor'] = json.loads(checked.stdout)
        report['status'] = 'PASS' if checked.returncode == 0 and report['doctor']['status'] == 'PASS' else 'BLOCKED'
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        report['error'] = str(error)
    report['phase'] = phase
    report['checked_at'] = datetime.now(timezone.utc).isoformat()
    report['next'] = ('Verify remaining host capabilities; then publish the Cloud environment or reload local skills. '
                      'A fresh task receives only repository URL + website URL. Keep the source checkout for its runtime.')
    if workspace:
        receipt = workspace / '.vertigo/setup.json'
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2) + '\n')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
