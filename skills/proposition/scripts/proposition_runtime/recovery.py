"""Explicit, bounded local input staging; no crawling or hidden retries."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata


def _copy(source, target):
    digest = hashlib.sha256()
    with open(source, 'rb') as incoming, open(target, 'xb') as outgoing:
        for chunk in iter(lambda: incoming.read(1024 * 1024), b''):
            outgoing.write(chunk)
            digest.update(chunk)
    print(digest.hexdigest())


def prepare_inputs(run_dir, manifest, output_dir, *, timeout_seconds=5):
    """Only listed run-relative paths are read, each by a killable child process."""
    from . import state
    root = Path(state.load_run(run_dir)['root'])
    entries = json.loads(Path(manifest).read_text())['inputs']
    if not isinstance(entries, list) or not entries or len(entries) > 64:
        raise ValueError('List 1–64 necessary inputs, not a recursive corpus')
    if not 0 < timeout_seconds <= 30:
        raise ValueError('Input timeout must be positive and at most 30 seconds')
    names = set(); filenames={'input-receipt.json'}
    for row in entries:
        state._identifier(row['id'])
        if row['id'] in names or not re.fullmatch(r'[0-9a-f]{64}', row['sha256']):
            raise ValueError('Inputs need unique IDs and expected SHA-256 values')
        names.add(row['id'])
        source=state._safe_path(root, row['path'], exists=False)
        filename=unicodedata.normalize('NFC',row['id']+source.suffix).casefold()
        if filename in filenames:raise ValueError('Staged input filenames collide')
        filenames.add(filename)
    if any(name+'.partial' in filenames for name in filenames):
        raise ValueError('A temporary input name collides with a retained file')
    output = state._external_root(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    report = {'status':'PASS', 'scope':'listed_inputs_only', 'inputs':[]}
    for row in entries:
        started = time.monotonic()
        source = state._safe_path(root, row['path'], exists=False)
        target = output / (row['id'] + source.suffix)
        pending = target.with_name(target.name + '.partial')
        item = {'id':row['id'], 'source':row['path'], 'status':'UNAVAILABLE'}
        try:
            result = subprocess.run([sys.executable, str(Path(__file__)), str(source), str(pending)],
                                    capture_output=True, text=True, timeout=timeout_seconds)
            if result.returncode != 0:
                raise ValueError('Input could not be opened or copied')
            if result.stdout.strip() != row['sha256']:
                raise ValueError('Input hash differs from approved evidence')
            os.link(pending,target)
            pending.unlink()
            item.update(status='READY', path=target.name, sha256=row['sha256'])
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            pending.unlink(missing_ok=True)
            item['reason'] = 'Input read deadline exceeded' if isinstance(error, subprocess.TimeoutExpired) else str(error)
            report['status'] = 'PARTIAL'
        item['elapsed_seconds'] = round(time.monotonic()-started, 3)
        report['inputs'].append(item)
    with (output/'input-receipt.json').open('x') as receipt:
        receipt.write(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    _copy(sys.argv[1], sys.argv[2])
