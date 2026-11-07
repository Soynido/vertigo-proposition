"""Explicit isolated transport installation; no global CLI or auth mutation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from . import state
from .transactions import read_json
from .publication import write_json


def _paths():
    source=Path(__file__).parents[2]/'resources/toolchain/codex'
    version=read_json(source/'package.json')['dependencies']['@openai/codex']
    cache=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'vertigo-proposition/tools'/('codex-'+state._sha(source/'package-lock.json')[:20])
    return source,state._external_root(cache),version


def locate_codex_cli():
    source,cache,version=_paths();receipt=read_json(cache/'CLI-CHECK.json')
    package=read_json(cache/'node_modules/@openai/codex/package.json')
    exe=state._safe_path(cache,'node_modules/@openai/codex/'+package['bin']['codex'])
    if (package['version']!=version or receipt.get('version')!=version
            or receipt.get('lock_sha256')!=state._sha(source/'package-lock.json')
            or receipt.get('executable_sha256')!=state._sha(exe) or not os.access(exe,os.X_OK)):
        raise ValueError('Pinned native toolchain changed; no global CLI substitution')
    if not receipt.get('native_files'):raise ValueError('Native executable inventory is missing')
    for name,expected in receipt['native_files'].items():
        if state._sha(state._safe_path(cache,name))!=expected:raise ValueError('Native executable changed')
    return str(exe)


def ensure_codex_cli():
    source,cache,version=_paths()
    if cache.exists():return locate_codex_cli()
    if not shutil.which('node') or not shutil.which('npm'):raise ValueError('Native setup requires Node and npm')
    cache.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.codex-tools-',dir=cache.parent) as tmp:
        staging=Path(tmp)/'package';staging.mkdir()
        for name in ('package.json','package-lock.json'):shutil.copyfile(source/name,staging/name)
        result=subprocess.run(['npm','ci','--prefix',str(staging),'--ignore-scripts','--no-audit','--no-fund'],capture_output=True,timeout=180)
        if result.returncode:raise ValueError('Pinned native installation failed')
        exe=staging/'node_modules/@openai/codex/bin/codex.js'
        result=subprocess.run([str(exe),'--version'],capture_output=True,text=True,timeout=15)
        if result.returncode or result.stdout.strip()!='codex-cli '+version:raise ValueError('Native version failed verification')
        native={p.relative_to(staging).as_posix():state._sha(p) for p in (staging/'node_modules/@openai').rglob('*')
            if p.is_file() and not p.is_symlink() and ('vendor' in p.parts or p.suffix=='.node')}
        if not native:raise ValueError('Native executable is missing')
        write_json(staging/'CLI-CHECK.json',{'version':version,'lock_sha256':state._sha(source/'package-lock.json'),
            'executable_sha256':state._sha(exe),'native_files':native,'scope':'installation_only'})
        try:os.rename(staging,cache)
        except FileExistsError:pass
    return locate_codex_cli()
