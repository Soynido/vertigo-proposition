"""State boundaries: real temporary files, no providers and no external writes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "skills" / "proposition" / "scripts"))
try:
    from proposition_runtime import state
except ImportError:
    state = None


class StateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(state, "The durable state runtime has not been implemented")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)

    def new_run(self):
        return state.init_run(
            "https://example.test/",
            self.base / "runs",
            {"actor": "operator", "responsible": "project-owner",
             "responsible_confirmed": True,
             "required_reviewers": ["review-a", "review-b"]},
        )

    def write(self, run, name, content):
        path = Path(run["root"]) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def complete_run(self, scores_b=None, include_stages=True):
        run = self.new_run()
        self.write(run, "sources/page.txt", "Public fixture observation")
        state.add_source(run["root"], "page", "sources/page.txt", kind="public")
        state.add_fact(run["root"], "offer", "A public fixture offer", ["page"],
                       audience="client", public_allowed=True)
        for audience in ("client", "sales", "technical"):
            self.write(run, f"exports/{audience}.pdf", f"Fixture {audience} file")
            state.add_artifact(run["root"], f"{audience}-pdf", f"exports/{audience}.pdf",
                               audience, ["fact:offer"])
        from creative_fixture import install_preservation
        install_preservation(state.load_run(run['root']))
        for number in range(1, 82):
            state.record_evaluation(run["root"], f"R{number:02}", {
                "status": "PASS", "applicable": True,
                "evidence": ["artifact:client-pdf"], "unknowns": [],
                "reason": "Fixture evidence assessed for this requirement",
            })
        artifacts = state.load_run(run["root"])["artifacts"]
        reviewed = {f"artifact:{name}": record["sha256"]
                    for name, record in artifacts.items()}
        for reviewer, scores in (("review-a", [2, 2, 2, 2, 2]),
                                 ("review-b", scores_b or [2, 2, 2, 2, 1])):
            receipt = {
                "run_id": run["id"], "reviewer_id": reviewer,
                "author_id": "operator", "context_isolated": True,
                "author_context_inherited": False, "verdict_shared": False,
                "method": "fresh-context", "artifact_hashes": reviewed,
            }
            self.write(run, f"reviews/{reviewer}.json", json.dumps(receipt))
            state.add_artifact(run["root"], f"receipt-{reviewer}",
                               f"reviews/{reviewer}.json", "internal", list(reviewed))
            state.record_evaluation(run["root"], "quality", {
                "reviewer_id": reviewer, "status": "PASS", "scores": scores,
                "independence": {"receipt_id": f"receipt-{reviewer}"},
                "evidence": list(reviewed), "unknowns": [],
            })
        if include_stages and hasattr(state, "record_stage_review"):
            for stage in json.loads((state.DATA_ROOT / "stages.json").read_text())["stages"]:
                self.stage_review(run, stage["id"], reviewed)
        return state.load_run(run["root"])

    def stage_review(self, run, stage_id, reviewed=None, scores=None):
        if reviewed is None:
            artifacts = state.load_run(run["root"])["artifacts"]
            reviewed = {f"artifact:{name}": record["sha256"]
                        for name, record in artifacts.items() if name.endswith("-pdf")}
        receipt = {
            "run_id": run["id"], "reviewer_id": "stage-reviewer", "author_id": "operator",
            "stage_id": stage_id, "context_isolated": True,
            "author_context_inherited": False, "verdict_shared": False,
            "method": "fresh-context", "artifact_hashes": reviewed,
        }
        receipt_id = f"stage-{stage_id}"
        self.write(run, f"reviews/{receipt_id}.json", json.dumps(receipt))
        state.add_artifact(run["root"], receipt_id, f"reviews/{receipt_id}.json", "internal", list(reviewed))
        return state.record_stage_review(run["root"], stage_id, {
            "reviewer_id": "stage-reviewer", "status": "PASS",
            "scores": scores or [2, 2, 2, 2, 1],
            "independence": {"receipt_id": receipt_id}, "evidence": list(reviewed), "unknowns": [],
            "criterion_evidence": {
                criterion["id"]: list(reviewed)
                for stage in json.loads((state.DATA_ROOT / "stages.json").read_text())["stages"]
                if stage["id"] == stage_id for criterion in stage["criteria"]
            },
        })

    def assert_blocked(self, run, code=None):
        report = state.validate_run(run["root"])
        self.assertNotEqual(report["status"], "PASS", report)
        if code:
            self.assertIn(code, {issue["code"] for issue in report["issues"]})
        return report

    def test_initialization_is_durable_and_starts_blocked(self):
        run = self.new_run()
        self.assertTrue((Path(run["root"]) / "state.json").is_file())
        loaded = state.load_run(run["root"])
        self.assertEqual(loaded["id"], run["id"])
        self.assert_blocked(run, "missing_evaluation")

    def test_packet_preserves_relative_resources_for_editable_sources(self):
        run = self.complete_run()
        self.write(run, 'client/index.html', '<link rel="stylesheet" href="assets/theme.css"><h1>Editable</h1>')
        self.write(run, 'client/assets/theme.css', 'h1 {color: navy}')
        for identifier,path in [('html-source','client/index.html'),('theme','client/assets/theme.css')]:
            state.add_artifact(run['root'], identifier, path, 'client', ['fact:offer'])
        current = state.load_run(run['root'])
        for identifier in ('html-source','theme'):
            record=current['artifacts'][identifier]
            record['public_allowed']=True
            record['approval']={'actor':'operator','sha256':record['sha256']}
        state.save_run(run['root'],current)
        output=self.base/'packet'
        state.build_public_packet(run['root'],output,['html-source','theme'])
        self.assertTrue((output/'index.html').is_file())
        self.assertEqual((output/'assets/theme.css').read_text(),'h1 {color: navy}')

    def test_registry_uses_only_the_shared_named_stages(self):
        registry = json.loads((state.DATA_ROOT / "requirements.json").read_text())
        allowed = {"discovery.site", "discovery.channels", "company.v1", "analysis.specialists",
                   "company.v2", "brief.public", "creative.direction", "client.composition",
                   "review.client", "internal.handoffs", "export.documents", "verify.final",
                   "publication.approved"}
        for requirement in registry["requirements"]:
            self.assertIn(requirement.get("stage_id"), allowed)

    def test_run_inside_checkout_is_rejected(self):
        with self.assertRaises(ValueError):
            state.init_run("https://example.test/", REPOSITORY / "forbidden-run")

    def test_save_rejects_structural_corruption(self):
        run = self.new_run()
        run["sources"] = []
        with self.assertRaises(ValueError):
            state.save_run(run["root"], run)
        self.assertIsInstance(state.load_run(run["root"])["sources"], dict)

    def test_save_rejects_foreign_run_identity(self):
        run = self.new_run()
        another = self.new_run()
        with self.assertRaises(ValueError):
            state.save_run(run["root"], another)

    def test_save_rejects_assessments_outside_the_stable_registry(self):
        run = self.new_run()
        self.write(run, "observation.txt", "Public fixture")
        state.add_source(run["root"], "page", "observation.txt")
        state.record_evaluation(run["root"], "R01", {"evidence": ["source:page"]})
        run = state.load_run(run["root"])
        run["evaluations"]["R99"] = dict(run["evaluations"]["R01"], id="R99")
        with self.assertRaises(ValueError):
            state.save_run(run["root"], run)

    def test_load_rejects_symlink_state_file(self):
        run = self.new_run()
        path = Path(run["root"]) / "state.json"
        saved = path.read_text()
        path.unlink()
        outside = self.base / "outside.json"
        outside.write_text(saved)
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            state.load_run(run["root"])

    def test_artifact_traversal_and_symlink_are_rejected(self):
        run = self.new_run()
        (self.base / "private.txt").write_text("Private fixture")
        with self.assertRaises(ValueError):
            state.add_artifact(run["root"], "outside", "../../private.txt", "client")
        (Path(run["root"]) / "link.txt").symlink_to(self.base / "private.txt")
        with self.assertRaises(ValueError):
            state.add_artifact(run["root"], "linked", "link.txt", "client")

    def test_source_symlink_is_rejected(self):
        run = self.new_run()
        private = self.base / "unrelated.txt"
        private.write_text("Unrelated fixture")
        (Path(run["root"]) / "source.txt").symlink_to(private)
        with self.assertRaises(ValueError):
            state.add_source(run["root"], "source", "source.txt")

    def test_all_81_identifiers_are_required_not_only_present_subset(self):
        run = self.complete_run()
        self.assertEqual(state.validate_run(run["root"])["status"], "PASS")
        del run["evaluations"]["R81"]
        state.save_run(run["root"], run)
        self.assert_blocked(run, "missing_evaluation")

    def test_unknown_fact_cannot_pass(self):
        run = self.complete_run()
        run["facts"]["offer"]["status"] = "UNKNOWN"
        state.save_run(run["root"], run)
        self.assert_blocked(run)

    def test_missing_source_cannot_pass(self):
        run = self.complete_run()
        del run["sources"]["page"]
        state.save_run(run["root"], run)
        self.assert_blocked(run)

    def test_unsupported_fact_cannot_pass_even_if_file_exists(self):
        run = self.complete_run()
        run["facts"]["offer"]["source_ids"] = []
        run["facts"]["offer"]["dependencies"] = []
        run["facts"]["offer"]["dependency_hashes"] = {}
        state.save_run(run["root"], run)
        self.assert_blocked(run, "unsupported_fact")

    def test_pass_without_evidence_cannot_pass(self):
        run = self.complete_run()
        state.record_evaluation(run["root"], "R12", {"status": "PASS", "evidence": []})
        self.assert_blocked(run, "missing_evidence")

    def test_evidence_cannot_be_detached_from_its_dependency_hash(self):
        run = self.complete_run()
        evaluation = run["evaluations"]["R12"]
        evaluation["evidence"] = ["source:never-collected"]
        evaluation["dependencies"] = []
        evaluation["dependency_hashes"] = {}
        state.save_run(run["root"], run)
        self.assert_blocked(run)

    def test_always_required_requirement_cannot_be_waived_by_a_reason(self):
        run = self.complete_run()
        state.record_evaluation(run["root"], "R12", {
            "status": "NOT_APPLICABLE", "applicable": False,
            "reason": "A convenient omission", "evidence": ["artifact:client-pdf"],
        })
        self.assert_blocked(run, "unjustified_non_applicability")

    def test_conditional_requirement_can_be_inapplicable_with_reason_and_evidence(self):
        run = self.complete_run()
        state.record_evaluation(run["root"], "R27", {
            "status": "NOT_APPLICABLE", "applicable": False,
            "reason": "No content management system is present in this fixture",
            "evidence": ["source:page"],
        })
        self.assertEqual(state.validate_run(run["root"])["status"], "PASS")

    def test_unknown_and_unjustified_not_applicable_cannot_pass(self):
        for evaluation in ({"status": "UNKNOWN", "evidence": ["artifact:client-pdf"]},
                           {"status": "NOT_APPLICABLE", "applicable": False,
                            "evidence": [], "reason": ""}):
            with self.subTest(evaluation=evaluation):
                run = self.complete_run()
                state.record_evaluation(run["root"], "R12", evaluation)
                self.assert_blocked(run)

    def test_quality_scores_are_not_averaged_between_reviewers(self):
        run = self.complete_run(scores_b=[2, 2, 2, 1, 1])
        self.assert_blocked(run, "review_score")

    def test_final_gate_cannot_pass_without_stage_scores(self):
        run = self.complete_run(include_stages=False)
        self.assert_blocked(run, "missing_stage_review")

    def test_stage_requires_score_even_when_its_requirements_pass(self):
        run = self.complete_run(include_stages=False)
        report = state.stage_report(run["root"], "company.v2")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIsNone(report["score"])

    def test_stage_eight_blocks_and_nine_passes_independently(self):
        run = self.complete_run(include_stages=False)
        self.stage_review(run, "company.v2", scores=[2, 2, 2, 1, 1])
        self.assertEqual(state.stage_report(run["root"], "company.v2")["status"], "BLOCKED")
        self.stage_review(run, "company.v2", scores=[2, 2, 2, 2, 1])
        report = state.stage_report(run["root"], "company.v2")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["score"], 9)
        self.assertNotEqual(state.validate_run(run["root"])["status"], "PASS")

    def test_stage_artifact_change_invalidates_stage_score(self):
        run = self.complete_run(include_stages=False)
        self.stage_review(run, "company.v2")
        self.write(run, "exports/client.pdf", "Changed reviewed fixture")
        self.assertEqual(state.stage_report(run["root"], "company.v2")["status"], "STALE")

    def test_stage_receipt_cannot_be_reused_for_another_stage(self):
        run = self.complete_run(include_stages=False)
        review = self.stage_review(run, "company.v2")
        state.record_stage_review(run["root"], "company.v1", review)
        report = state.stage_report(run["root"], "company.v1")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("review_independence", {issue["code"] for issue in report["issues"]})

    def test_stage_score_without_evidence_for_each_criterion_is_blocked(self):
        run = self.complete_run(include_stages=False)
        self.stage_review(run, "company.v2")
        updated = state.load_run(run["root"])
        updated["stage_reviews"]["company.v2"].pop("criterion_evidence", None)
        state.save_run(run["root"], updated)
        report = state.stage_report(run["root"], "company.v2")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("missing_criterion_evidence", {issue["code"] for issue in report["issues"]})

    def test_preparation_quality_can_pass_while_publication_is_not_run(self):
        run = self.complete_run()
        registry = json.loads((state.DATA_ROOT / "requirements.json").read_text())["requirements"]
        for row in registry:
            if row["stage_id"] == "publication.approved":
                run["evaluations"].pop(row["id"], None)
        run["stage_reviews"].pop("publication.approved", None)
        state.save_run(run["root"], run)
        report = state.validate_run(run["root"])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["publication"]["status"], "NOT_RUN")
        self.assertIsNone(report["publication"]["score"])
        self.assertEqual(report["coverage"]["required"], 81)

    def initial_context(self):
        run = self.new_run()
        self.write(run, "source.txt", "Authorized client fixture material")
        state.add_source(run["root"], "input", "source.txt", kind="client")
        state.add_fact(run["root"], "offer", "Fixture offer", ["input"], audience="client", public_allowed=True)
        self.write(run, "brief.txt", "Approved fixture creative input")
        artifact = state.add_artifact(run["root"], "brief", "brief.txt", "client", ["fact:offer"])
        state.record_evaluation(run["root"], "R78", {
            "status": "PASS", "evidence": ["artifact:brief"], "reason": "Autonomous fixture brief inspected",
        })
        from experience_fixture import prepare_inputs
        prepare_inputs(state.load_run(run["root"]))
        self.stage_review(run, "brief.public", {"artifact:brief": artifact["sha256"]})
        run = state.load_run(run["root"])
        for key,row in run["artifacts"].items():
            row["public_allowed"] = True
            row["approval"] = {"actor": "operator", "sha256": row["sha256"]}
        state.save_run(run["root"], run)
        return run

    def test_context_packet_is_possible_before_final_documents_exist(self):
        run = self.initial_context()
        self.assertNotEqual(state.validate_run(run["root"])["status"], "PASS")
        receipt = state.build_context_packet(run["root"], self.base / "creative", ["brief", "creative-inputs", "method-claude-seo", "method-impeccable", "method-apple-design", "method-scroll-craft"])
        self.assertEqual(receipt["status"], "PREPARED")
        self.assertEqual(receipt["scope"], "creative_input")
        self.assertEqual((self.base / "creative/brief.txt").read_text(), "Approved fixture creative input")
        self.assertFalse(any((Path(run["root"]) / "exports").glob("*.pdf")))

    def test_context_packet_cannot_drop_the_named_creative_methods(self):
        run = self.initial_context()
        with self.assertRaises(ValueError):
            state.build_context_packet(run["root"], self.base / "creative", ["brief"])

    def test_stale_brief_prevents_a_context_packet(self):
        run = self.initial_context()
        self.write(run, "brief.txt", "Changed after brief review")
        with self.assertRaises(ValueError):
            state.build_context_packet(run["root"], self.base / "creative", ["brief", "creative-inputs", "method-claude-seo", "method-impeccable", "method-apple-design", "method-scroll-craft"])
        self.assertFalse((self.base / "creative").exists())

    def test_review_id_without_hashed_receipt_cannot_pass(self):
        run = self.complete_run()
        run["reviews"]["review-b"]["independence"] = {"receipt_id": "absent"}
        state.save_run(run["root"], run)
        self.assert_blocked(run)

    def test_receipt_declaring_shared_author_context_cannot_pass(self):
        run = self.complete_run()
        path = Path(run["root"]) / "reviews/review-b.json"
        receipt = json.loads(path.read_text())
        receipt["author_context_inherited"] = True
        path.write_text(json.dumps(receipt))
        state.add_artifact(run["root"], "receipt-review-b", "reviews/review-b.json", "internal",
                           list(receipt["artifact_hashes"]))
        review = run["reviews"]["review-b"]
        state.record_evaluation(run["root"], "quality", review)
        self.assert_blocked(run, "review_independence")

    def test_modified_file_invalidates_transitive_evidence_and_survives_reload(self):
        run = self.complete_run()
        self.write(run, "sources/page.txt", "Changed public fixture")
        receipt = state.invalidate_changed(run["root"])
        self.assertEqual(receipt["status"], "STALE")
        loaded = state.load_run(run["root"])
        self.assertEqual(loaded["sources"]["page"]["status"], "STALE")
        self.assertEqual(loaded["facts"]["offer"]["status"], "STALE")
        self.assertEqual(loaded["artifacts"]["client-pdf"]["status"], "STALE")
        self.assertEqual(loaded["evaluations"]["R01"]["status"], "STALE")
        self.assertEqual(loaded["reviews"]["review-a"]["status"], "STALE")
        self.assert_blocked(run)

    def test_changed_profile_parameters_invalidate_derived_artifacts(self):
        run = self.complete_run()
        run["profile"]["parameters"]["scope_variant"] = "revised"
        state.save_run(run["root"], run)
        self.assert_blocked(run)
        loaded = state.load_run(run["root"])
        self.assertEqual(loaded["artifacts"]["client-pdf"]["status"], "STALE")

    def test_plan_change_invalidates_hash_bound_checkpoint_approval(self):
        run = self.new_run()
        self.write(run, "plans/publication.json", '{"operation":"local-plan"}')
        artifact = state.add_artifact(run["root"], "publication-plan", "plans/publication.json", "internal")
        state.record_checkpoint(run["root"], "publication-approval", "publication.approved", {
            "status": "APPROVED", "dependencies": ["artifact:publication-plan"],
            "approval": {"actor": "operator", "plan_ref": "artifact:publication-plan",
                         "plan_sha256": artifact["sha256"]},
        })
        self.write(run, "plans/publication.json", '{"operation":"changed-plan"}')
        state.invalidate_changed(run["root"])
        loaded = state.load_run(run["root"])
        self.assertEqual(loaded["checkpoints"]["publication-approval"]["status"], "STALE")

    def test_checkpoint_rejects_plan_changed_before_approval(self):
        run = self.new_run()
        self.write(run, "plan.json", '{"operation":"first"}')
        artifact = state.add_artifact(run["root"], "plan", "plan.json", "internal")
        self.write(run, "plan.json", '{"operation":"different"}')
        with self.assertRaises(ValueError):
            state.record_checkpoint(run["root"], "approval", "publication.approved", {
                "status": "APPROVED", "approval": {"actor": "operator",
                    "plan_ref": "artifact:plan", "plan_sha256": artifact["sha256"]},
            })

    def test_projection_uses_nested_allowlist_not_blacklist(self):
        data = {"title": "Public title", "private_notes": "Internal fixture",
                "facts": [{"value": "Public value", "private_notes": "Hidden value"}],
                "new_secret": "A previously unknown field"}
        projected = state.project_public(data, ("title", "facts.value"))
        self.assertEqual(projected, {"title": "Public title", "facts": [{"value": "Public value"}]})

    def test_projection_does_not_copy_an_unqualified_container(self):
        projected = state.project_public({"facts": {"value": "Public", "secret": "Hidden"}}, ("facts",))
        self.assertNotIn("secret", json.dumps(projected))

    def test_projection_does_not_override_explicit_private_classification(self):
        projected = state.project_public({"facts": [
            {"value": "Internal offer", "audience": "sales", "public_allowed": False},
            {"value": "Cleared public observation", "audience": "client", "public_allowed": True},
        ]}, ("facts.value",))
        self.assertEqual(projected, {"facts": [{"value": "Cleared public observation"}]})

    def test_projection_allows_an_explicit_scalar_list(self):
        projected = state.project_public({"tags": ["public", "fixture"]}, ("tags",))
        self.assertEqual(projected, {"tags": ["public", "fixture"]})

    def test_packet_rejects_internal_and_unapproved_artifacts(self):
        run = self.complete_run()
        for files in (["sales-pdf"], ["client-pdf"]):
            with self.subTest(files=files), self.assertRaises(ValueError):
                state.build_public_packet(run["root"], self.base / "packet", files)
        self.assertFalse((self.base / "packet").exists())

    def approve_client(self, run):
        run = state.load_run(run["root"])
        artifact = run["artifacts"]["client-pdf"]
        artifact["public_allowed"] = True
        artifact["approval"] = {"actor": "operator", "sha256": artifact["sha256"]}
        state.save_run(run["root"], run)
        return run

    def test_approved_public_packet_contains_only_explicit_files_and_safe_manifest(self):
        run = self.approve_client(self.complete_run())
        receipt = state.build_public_packet(run["root"], self.base / "packet", ["client-pdf"])
        self.assertEqual(receipt["status"], "PREPARED")
        packet = self.base / "packet"
        self.assertEqual({p.name for p in packet.iterdir()}, {"client.pdf", "manifest.json"})
        expected=(Path(run["root"])/"exports/client.pdf").read_bytes()
        self.assertEqual((packet / "client.pdf").read_bytes(), expected)
        manifest = json.loads((packet / "manifest.json").read_text())
        self.assertEqual(manifest["files"][0]["sha256"],
                         hashlib.sha256(expected).hexdigest())
        self.assertNotIn(str(self.base), json.dumps(manifest))
        self.assertNotIn("sales", json.dumps(manifest))

    def test_changed_approved_artifact_cannot_be_packaged(self):
        run = self.approve_client(self.complete_run())
        self.write(run, "exports/client.pdf", "Changed after approval")
        with self.assertRaises(ValueError):
            state.build_public_packet(run["root"], self.base / "packet", ["client-pdf"])
        self.assertFalse((self.base / "packet").exists())

    def test_packet_output_symlink_is_rejected(self):
        run = self.approve_client(self.complete_run())
        target = self.base / "unrelated"
        target.mkdir()
        (self.base / "packet").symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            state.build_public_packet(run["root"], self.base / "packet", ["client-pdf"])
        self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
