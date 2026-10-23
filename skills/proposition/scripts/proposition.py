"""Portable skill launcher; no slash-command registration is assumed."""
from pathlib import Path
import importlib.util
import json
import os
import sys

root = Path(__file__).resolve().parent
config = root.parent / 'installation.json'
if config.is_file():
    configured = Path(json.loads(config.read_text())['runtime_python'])
    if configured.is_file() and configured != Path(sys.executable) and not os.environ.get('PROPOSITION_REEXEC'):
        os.environ['PROPOSITION_REEXEC'] = '1'
        os.execv(str(configured), [str(configured), str(Path(__file__).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(root))
try:
    from proposition_runtime.cli import main
except ModuleNotFoundError as error:
    raise SystemExit(f'Runtime unavailable ({error.name}); run the repository setup command first.') from error
if __name__ == '__main__':
    raise SystemExit(main())
