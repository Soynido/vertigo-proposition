"""Installation must preserve shared resources and protect local edits."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

INSTALL_PATH = Path(__file__).parents[1] / "scripts" / "install.py"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        self.dest = self.base / "installed"
        for name in ("proposition", "proposition-discovery"):
            p = self.source / "skills" / name
            p.mkdir(parents=True)
            (p / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Test discovery.\n---\n")
        resources = self.source / "skills/proposition/scripts/proposition_runtime/contracts"
        resources.mkdir(parents=True)
        (resources / "fact.json").write_text('{"required":["source_id"]}')
        if INSTALL_PATH.exists():
            spec = importlib.util.spec_from_file_location("installation", INSTALL_PATH)
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        else:
            self.module = None

    def install(self, **kwargs):
        self.assertIsNotNone(self.module, "Installer has not been implemented")
        return self.module.install_repo(self.source, self.dest, **kwargs)

    def test_two_skills_keep_the_shared_contract_and_python_runtime(self):
        self.install()
        self.assertTrue((self.dest / "proposition-discovery/SKILL.md").is_file())
        self.assertEqual(json.loads((self.dest / "proposition/scripts/proposition_runtime/contracts/fact.json").read_text())["required"], ["source_id"])
        self.assertIn("runtime_python", json.loads((self.dest / "proposition/installation.json").read_text()))

    def test_update_refuses_to_replace_a_locally_modified_skill(self):
        self.install()
        skill = self.dest / "proposition/SKILL.md"
        skill.write_text("My own local instructions")
        with self.assertRaisesRegex(ValueError, "modified"):
            self.install(update=True)
        self.assertEqual(skill.read_text(), "My own local instructions")

    def test_symlink_resource_cannot_package_a_private_sibling(self):
        private = self.base / "private.txt"
        private.write_text("PRIVATE_SENTINEL")
        (self.source / "skills/proposition/private-link.txt").symlink_to(private)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.install()
        self.assertFalse(self.dest.exists())

    def test_failed_update_restores_every_previous_skill_and_manifest(self):
        self.install()
        before = {str(p.relative_to(self.dest)): p.read_bytes() for p in self.dest.rglob('*') if p.is_file()}
        (self.source / 'skills/proposition/SKILL.md').write_text('updated')
        original = self.module.shutil.move
        def fail_new_main(src, dst, *args, **kwargs):
            if 'proposition-install-' in str(src) and Path(src).name == 'proposition':
                raise OSError('injected disk failure')
            return original(src, dst, *args, **kwargs)
        with patch.object(self.module.shutil, 'move', side_effect=fail_new_main):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                self.install(update=True)
        after = {str(p.relative_to(self.dest)): p.read_bytes() for p in self.dest.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
