"""Explicit local setup. Review this file before running an unfamiliar checkout."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=Path.home() / '.codex/skills')
    parser.add_argument('--browser', action='store_true', help='Download the pinned Playwright Chromium build')
    parser.add_argument('--with-upstream', action='store_true', help='Fetch pinned open source skill distributions without executing them')
    parser.add_argument('--update', action='store_true')
    a = parser.parse_args()
    if sys.version_info < (3,11): parser.error('Python 3.11 or newer is required')
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.venv'
    if runtime.is_symlink(): parser.error('The local runtime cannot be a symlink')
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file(): venv.EnvBuilder(with_pip=True).create(runtime)
    if shutil.which('uv'):
        command = ['uv','pip','install','--python',str(python),'--require-hashes','-r',str(root / 'requirements.lock')]
    else:
        command = [str(python),'-m','pip','install','--require-hashes','-r',str(root / 'requirements.lock')]
    subprocess.run(command,check=True)
    if a.browser:
        subprocess.run([str(python),'-m','playwright','install','chromium'],check=True)
    command = [str(python),str(root/'scripts/install.py'),'--dest',str(a.dest),'--source',str(root)]
    if a.update: command.append('--update')
    subprocess.run(command,check=True)
    launcher = a.dest.expanduser().resolve() / 'proposition/scripts/proposition.py'
    if a.with_upstream:
        subprocess.run([str(python),str(launcher),'upstream','fetch'],check=True)
    result = subprocess.run([str(python),str(launcher),'doctor'],check=False)
    print(json.dumps({'installation':'INSTALLED','launcher':str(launcher),'doctor_exit':result.returncode,
                      'next':'Reload skills in Codex; invoke $proposition with the client URL. Keep this checkout for its runtime.'}))
    return result.returncode


if __name__ == '__main__': raise SystemExit(main())
