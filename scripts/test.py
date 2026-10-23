"""Run repository tests against the current source tree, not an old wheel."""
import argparse
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "skills/proposition/scripts"))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pattern", nargs="?", default="test_*.py")
args = parser.parse_args()
suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern=args.pattern)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
