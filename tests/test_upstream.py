"""Network fixtures verify cache integrity, never pretend an upstream was run."""
from __future__ import annotations

import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills/proposition/scripts"))
try:
    upstream = importlib.import_module("proposition_runtime.upstream")
except ModuleNotFoundError as exc:
    if exc.name != "proposition_runtime.upstream":
        raise
    upstream = None


class Response(io.BytesIO):
    def __init__(self, payload, url):
        super().__init__(payload)
        self.url = url

    def geturl(self):
        return self.url


class UpstreamTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(upstream, "Missing pinned upstream cache capability")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / "cache"
        self.commit = "1" * 40
        self.family = {"id": "fixture-pack", "repository": "fixture-owner/public-pack", "commit": self.commit,
                       "license": "MIT", "license_files": ["LICENSE"],
                       "entrypoints": ["skills/demo/SKILL.md"], "default": True}
        self.lock = self.root / "lock.json"
        self.lock.write_text(json.dumps({"schema_version": 1, "families": [self.family]}))
        self.addCleanup(patch.stopall)
        patch.object(upstream, "LOCK_PATH", self.lock).start()
        self.files = {
            "LICENSE": b"MIT License\nPublic test fixture only.\n",
            "README.md": b"A network test fixture, not an installed skill.\n",
            "skills/demo/SKILL.md": b"---\nname: fixture-demo\ndescription: Test fixture only\n---\n",
            "references/details.md": b"Keep the complete dependency subtree.\n",
            "install.sh": f"#!/bin/sh\ntouch '{self.root / 'EXECUTED'}'\n".encode(),
        }

    def tree(self, files=None):
        return {"sha": "2" * 40, "truncated": False, "tree": [
            {"path": name, "mode": "100644", "type": "blob", "size": len(data),
             "sha": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}
            for name, data in (self.files if files is None else files).items()]}

    def archive(self, files=None, malicious=None):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, data in (self.files if files is None else files).items():
                item = tarfile.TarInfo("public-pack-" + self.commit + "/" + name)
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
            if malicious:
                item = tarfile.TarInfo(malicious[0])
                item.type = malicious[1]
                item.linkname = "../../ESCAPED"
                archive.addfile(item, io.BytesIO())
        return output.getvalue()

    def network(self, tree=None, archive=None, redirect=False):
        metadata = json.dumps(self.tree() if tree is None else tree).encode()
        package = self.archive() if archive is None else archive

        def opened(_opener, request, *args, **kwargs):
            url = request.full_url if hasattr(request, "full_url") else request
            payload = metadata if "api.github.com" in url else package
            return Response(payload, "https://unexpected.example/archive" if redirect else url)

        return patch("urllib.request.OpenerDirector.open", autospec=True, side_effect=opened)

    def test_status_absent_is_not_installed_or_executed_and_does_not_fetch(self):
        with self.network() as network:
            report = upstream.status(cache=self.cache)
        self.assertFalse(self.cache.exists())
        self.assertFalse(report["families"][0]["present"])
        self.assertEqual("unknown", report["families"][0]["execution_status"])
        self.assertFalse(report["families"][0]["installed"])
        self.assertEqual(0, network.call_count)

    def test_default_cache_uses_persistent_home_or_xdg_with_explicit_overrides(self):
        home = self.root / "fixture-home"
        xdg = self.root / "fixture-xdg"
        override = self.root / "environment-cache"
        with self.network() as network, patch.dict(upstream.os.environ, {"HOME": str(home)}, clear=True):
            report = upstream.status()
            self.assertEqual(home / ".cache/vertigo-proposition/upstreams", Path(report["cache"]))
            upstream.os.environ["XDG_CACHE_HOME"] = str(xdg)
            self.assertEqual(xdg / "vertigo-proposition/upstreams", Path(upstream.status()["cache"]))
            upstream.os.environ["PROPOSITION_UPSTREAM_CACHE"] = str(override)
            self.assertEqual(override, Path(upstream.status()["cache"]))
            self.assertEqual(self.cache, Path(upstream.status(cache=self.cache)["cache"]))
        self.assertEqual(0, network.call_count)
        self.assertFalse(home.exists())
        self.assertFalse(xdg.exists())

    def test_fetch_preserves_full_inventory_licenses_and_never_runs_installers(self):
        with self.network() as network:
            report = upstream.fetch(cache=self.cache)
        self.assertEqual("COMPLETE", report.get("status"))
        item = report["families"][0]
        self.assertTrue(item["complete"])
        self.assertFalse(item["installed"])
        self.assertEqual("unknown", item["execution_status"])
        manifest = json.loads(Path(item["receipt_path"]).read_text())
        self.assertEqual(set(self.files), {f["path"] for f in manifest["inventory"]})
        self.assertTrue(manifest["licenses"])
        source = Path(item["source_path"])
        self.assertEqual(self.files["references/details.md"], (source / "references/details.md").read_bytes())
        self.assertEqual(hashlib.sha256(self.files["LICENSE"]).hexdigest(), next(f["sha256"] for f in manifest["inventory"] if f["path"] == "LICENSE"))
        self.assertFalse((self.root / "EXECUTED").exists())
        self.assertEqual(2, network.call_count)
        with self.network() as network:
            self.assertTrue(upstream.status(cache=self.cache)["families"][0]["complete"])
            self.assertTrue(upstream.fetch(cache=self.cache)["families"][0]["complete"])
        self.assertEqual(0, network.call_count)

    def test_modified_file_invalidates_completeness_without_claiming_execution(self):
        with self.network():
            item = upstream.fetch(cache=self.cache)["families"][0]
        (Path(item["source_path"]) / "README.md").write_text("changed")
        result = upstream.status(cache=self.cache)["families"][0]
        self.assertTrue(result["present"])
        self.assertFalse(result["complete"])
        self.assertEqual("corrupt", result["state"])
        self.assertEqual("unknown", result["execution_status"])

    def test_truncated_tree_and_symlink_or_submodule_metadata_are_rejected(self):
        for kind in ("truncated", "symlink", "submodule"):
            tree = self.tree()
            if kind == "truncated":
                tree["truncated"] = True
            else:
                tree["tree"].append({"path": "unsafe", "type": "blob" if kind == "symlink" else "commit", "mode": "120000" if kind == "symlink" else "160000", "sha": "3" * 40})
            with self.subTest(kind=kind), self.network(tree=tree) as network:
                report = upstream.fetch(cache=self.cache / kind)
                self.assertEqual("PARTIAL", report.get("status"))
                self.assertFalse(report["families"][0]["complete"])
                self.assertEqual("unavailable", report["families"][0]["state"])
                self.assertEqual(1, network.call_count)

    def test_missing_entrypoint_and_license_are_rejected(self):
        for missing in ("LICENSE", "skills/demo/SKILL.md"):
            files = dict(self.files)
            files.pop(missing)
            with self.subTest(missing=missing), self.network(tree=self.tree(files), archive=self.archive(files)):
                result = upstream.fetch(cache=self.cache / missing.replace("/", "_"))["families"][0]
                self.assertFalse(result["complete"])
                self.assertEqual("unavailable", result["state"])

    def test_archive_escape_symlink_and_hardlink_never_write_outside_cache(self):
        attacks = [("../../ESCAPED", tarfile.REGTYPE), ("/ESCAPED", tarfile.REGTYPE),
                   ("public-pack-" + self.commit + "/link", tarfile.SYMTYPE),
                   ("public-pack-" + self.commit + "/hard", tarfile.LNKTYPE)]
        for i, attack in enumerate(attacks):
            with self.subTest(attack=attack), self.network(archive=self.archive(malicious=attack)):
                result = upstream.fetch(cache=self.cache / str(i))["families"][0]
                self.assertFalse(result["complete"])
        self.assertFalse((self.root / "ESCAPED").exists())

    def test_wrong_blob_or_missing_archive_file_is_not_complete(self):
        for variant in ("modified", "missing"):
            files = dict(self.files)
            if variant == "modified":
                files["README.md"] = b"not the pinned blob"
            else:
                files.pop("references/details.md")
            with self.subTest(variant=variant), self.network(archive=self.archive(files)):
                result = upstream.fetch(cache=self.cache / variant)["families"][0]
                self.assertFalse(result["complete"])

    def test_archive_line_endings_are_only_recovered_when_exact_git_hash_matches(self):
        files = dict(self.files)
        files["README.md"] = files["README.md"].replace(b"\n", b"\r\n")
        with self.network(archive=self.archive(files)):
            result = upstream.fetch(cache=self.cache)["families"][0]
        self.assertTrue(result["complete"], result.get("error"))
        self.assertEqual(self.files["README.md"], (Path(result["source_path"]) / "README.md").read_bytes())
        receipt = json.loads(Path(result["receipt_path"]).read_text())
        entry = next(i for i in receipt["inventory"] if i["path"] == "README.md")
        self.assertEqual("crlf_to_exact_git_blob", entry["transport_transform"])

    def test_unknown_family_inside_repo_cache_and_symlink_are_refused(self):
        with self.network() as network:
            with self.assertRaises(ValueError):
                upstream.fetch(family="not-a-family", cache=self.cache)
            with self.assertRaises(ValueError):
                upstream.fetch(cache=REPO / "cache")
            outside = self.root / "outside"
            outside.mkdir()
            self.cache.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                upstream.fetch(cache=self.cache)
        self.assertEqual(0, network.call_count)
        self.assertFalse(list(outside.iterdir()))

    def test_unexpected_redirect_is_rejected_without_installation(self):
        with self.network(redirect=True):
            result = upstream.fetch(cache=self.cache)["families"][0]
        self.assertEqual("unavailable", result["state"])
        self.assertFalse(result["complete"])

    def test_relocated_package_and_skill_boundaries_do_not_depend_on_parent_depth(self):
        skill = self.root / "arbitrary/deep/portable-skill"
        package = skill / "scripts/proposition_runtime"
        package.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Public fixture skill boundary")
        module_path = package / "upstream.py"
        module_path.write_text("Public fixture location only")
        with patch.object(upstream, "__file__", str(module_path)):
            with self.assertRaises(ValueError):
                upstream.status(cache=package / "cache")
            with self.assertRaises(ValueError):
                upstream.status(cache=skill / "cache")
            report = upstream.status(cache=self.root / "outside-skill")
        self.assertFalse(report["families"][0]["present"])


if __name__ == "__main__":
    unittest.main()
