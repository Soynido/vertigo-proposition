"""Local approvals must bind exact plans; uncertain effects must be read back."""
from pathlib import Path
import tempfile
import unittest

try:
    from proposition_runtime import publication
except ImportError:
    publication = None


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "human-decision.txt"
        self.evidence.write_text("Fixture user approves this exact plan.")
        self.payload = {"actor": "fixture-owner", "items": [{"id": "next-action", "destination": "fixture-destination", "action": "append", "content": {"title": "Arrange the next discussion"}}]}

    def module(self):
        self.assertIsNotNone(publication, "Publication contract is not implemented")
        return publication

    def test_no_approval_means_no_write(self):
        p = self.module()
        p.prepare_plan(self.root, self.payload)
        adapter = p.FixtureAdapter(self.root / "fixture-store.json")
        with self.assertRaisesRegex(ValueError, "approval"):
            p.publish_plan(self.root, adapter)
        self.assertEqual(adapter.write_count, 0)

    def test_modified_plan_invalidates_the_old_approval(self):
        p = self.module()
        plan = p.prepare_plan(self.root, self.payload)
        p.approve_plan(self.root, plan["sha256"], "fixture-owner", self.evidence)
        self.payload["items"][0]["content"]["title"] = "A changed action"
        p.prepare_plan(self.root, self.payload)
        with self.assertRaisesRegex(ValueError, "approval"):
            p.publish_plan(self.root, p.FixtureAdapter(self.root / "fixture-store.json"))

    def test_uncertain_write_is_found_before_any_retry(self):
        p = self.module()
        plan = p.prepare_plan(self.root, self.payload)
        p.approve_plan(self.root, plan["sha256"], "fixture-owner", self.evidence)
        adapter = p.FixtureAdapter(self.root / "fixture-store.json", uncertain_once=True)
        first = p.publish_plan(self.root, adapter)
        second = p.publish_plan(self.root, adapter)
        self.assertEqual(first["status"], "VERIFIED")
        self.assertEqual(second["status"], "VERIFIED")
        self.assertEqual(adapter.write_count, 1)
        self.assertEqual(first["scope"], "fixture_only")

    def test_altered_approval_evidence_blocks_writes(self):
        p = self.module()
        plan = p.prepare_plan(self.root, self.payload)
        p.approve_plan(self.root, plan["sha256"], "fixture-owner", self.evidence)
        self.evidence.write_text("Different decision")
        with self.assertRaisesRegex(ValueError, "evidence"):
            p.publish_plan(self.root, p.FixtureAdapter(self.root / "fixture-store.json"))


if __name__ == "__main__":
    unittest.main()
