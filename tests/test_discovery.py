"""Observable collector contracts; every browser request targets a local fixture."""
from __future__ import annotations

import importlib
import hashlib
import json
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills/proposition/scripts"))
try:
    collect = importlib.import_module("proposition_runtime.discovery").collect
except ModuleNotFoundError as exc:
    if not exc.name.startswith("proposition_runtime"):
        raise
    collect = None


class FixtureHandler(SimpleHTTPRequestHandler):
    requests_seen: Counter = Counter()

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.requests_seen[("GET", self.path)] += 1
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/about.html")
            self.end_headers()
        elif self.path == "/inaccessible":
            self.send_error(403, "Fixture access denied")
        elif self.path == "/out-redirect":
            self.send_response(302)
            self.send_header("Location", f"http://localhost:{self.server.server_port}/escape.html")
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        self.requests_seen[("POST", self.path)] += 1
        self.send_error(405)


class DiscoveryTests(unittest.TestCase):
    def test_output_inside_public_distribution_is_refused_before_capture(self):
        module = importlib.import_module('proposition_runtime.discovery')
        output = REPO / ('forbidden-output-' + uuid4().hex)
        self.addCleanup(lambda: output.rmdir() if output.exists() else None)
        with self.assertRaisesRegex(ValueError, 'outside'):
            module._output_directory(output)

    @classmethod
    def setUpClass(cls):
        handler = partial(FixtureHandler, directory=str(Path(__file__).parent / "fixtures/site"))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.assertTrue(callable(collect), "Missing collect: the discovery capability has not been implemented")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name).resolve() / "capture"
        FixtureHandler.requests_seen.clear()

    def test_local_network_is_rejected_without_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            collect(self.base, self.output)
        self.assertFalse(FixtureHandler.requests_seen)

    def test_non_web_credentials_and_sensitive_paths_are_rejected(self):
        for i, url in enumerate(["file:///etc/passwd", "ftp://example.com", "https://user:pass@example.com/", self.base + "/.env", self.base + "/admin", self.base + "/wp-login.php", self.base + "/?action=delete", self.base + "/?token=private"]):
            with self.subTest(url=url), self.assertRaises(ValueError):
                collect(url, self.output / str(i), allow_local=True)
        self.assertFalse(FixtureHandler.requests_seen)

    def test_cross_origin_redirect_is_not_followed_or_counted_as_analyzed(self):
        report = collect(self.base + "/out-redirect", self.output, allow_local=True, max_pages=1)
        self.assertEqual([], report["coverage"]["captured_urls"])
        self.assertFalse(any(path == "/escape.html" for _, path in FixtureHandler.requests_seen))
        self.assertTrue(any(r["reason"] == "cross_origin_request" for r in report["blocked_requests"]))

    def test_asset_redirect_cannot_escape_origin_either(self):
        report = collect(self.base + "/asset-redirect.html", self.output, allow_local=True, max_pages=1)
        self.assertTrue(report["coverage"]["captured_urls"])
        self.assertFalse(any(path == "/escape.html" for _, path in FixtureHandler.requests_seen))
        self.assertTrue(any(r["reason"] == "cross_origin_request" for r in report["blocked_requests"]))

    def test_desktop_mobile_submenus_scroll_and_sources_are_real(self):
        report = collect(self.base + "/", self.output, allow_local=True, max_pages=8)
        analyzed = {p["requested_url"] for p in report["pages"] if p["status"] == "captured"}
        self.assertIn(self.base + "/desktop.html", analyzed)
        self.assertIn(self.base + "/mobile.html", analyzed)
        self.assertIn(self.base + "/nested.html", analyzed)
        self.assertIn(self.base + "/scroll.html", analyzed)
        self.assertEqual({"desktop", "mobile"}, {p["viewport"] for p in report["pages"]})
        self.assertEqual("NOT_RUN", report["semantic_analysis"])
        self.assertTrue(all(p["semantic_analysis"] == "NOT_RUN" for p in report["pages"]))
        root_views = [p for p in report["pages"] if p["requested_url"] == self.base + "/"]
        self.assertTrue(any(e["kind"] == "menu" for p in root_views for e in p["evidence"]))
        self.assertTrue(any(e["kind"] == "scroll" for p in root_views for e in p["evidence"]))
        self.assertTrue(report["sources"])
        for source in report["sources"]:
            self.assertIn("retrieved_at", source)
            for artifact in source["artifacts"]:
                path = self.output / artifact["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(64, len(artifact["sha256"]))
        self.assertEqual(report, json.loads((self.output / "discovery.json").read_text()))

    def test_redirect_and_inaccessible_are_reported_without_false_analysis(self):
        report = collect(self.base + "/", self.output, allow_local=True, max_pages=8)
        redirects = [p for p in report["pages"] if p["requested_url"].endswith("/redirect")]
        self.assertTrue(redirects)
        self.assertTrue(all(p["final_url"] == self.base + "/about.html" for p in redirects))
        denied = [p for p in report["pages"] if p["requested_url"].endswith("/inaccessible")]
        self.assertTrue(denied)
        self.assertTrue(all(p["status"] == "inaccessible" and p["http_status"] == 403 for p in denied))
        self.assertNotIn(self.base + "/inaccessible", report["coverage"]["captured_urls"])

    def test_social_assets_remain_candidates_with_observed_provenance(self):
        report = collect(self.base + "/", self.output, allow_local=True, max_pages=1)
        socials = {c["url"]: c for c in report["social_candidates"]}
        self.assertIn("https://www.linkedin.com/company/fixture-studio/", socials)
        self.assertEqual("candidate", socials["https://www.linkedin.com/company/fixture-studio/"]["status"])
        self.assertIn("jsonld_sameAs", socials["https://www.linkedin.com/company/fixture-studio/"]["methods"])
        self.assertTrue(socials["https://www.instagram.com/fixture.studio/"]["source_ids"])
        assets = {a["url"] for a in report["asset_candidates"]}
        self.assertIn(self.base + "/assets/logo.svg", assets)
        self.assertIn(self.base + "/assets/gallery.svg", assets)
        self.assertNotIn(self.base + "/", assets)
        self.assertNotIn("verified", {c["status"] for c in report["social_candidates"]})

    def test_budget_counts_unique_attempts_but_keeps_multiple_link_entries(self):
        report = collect(self.base + "/", self.output, allow_local=True, max_pages=1)
        self.assertEqual([self.base + "/"], report["coverage"]["attempted_urls"])
        self.assertTrue(report["coverage"]["omitted_urls"])
        pairs = [(p["requested_url"], p["viewport"]) for p in report["pages"]]
        self.assertEqual(len(pairs), len(set(pairs)))
        entries = [e for e in report["link_entries"] if e["url"] == self.base + "/about.html"]
        self.assertGreaterEqual(len(entries), 2)
        self.assertTrue(report["coverage"]["bounded"])
        self.assertFalse(report["coverage"]["exhaustive"])

    def test_hostile_page_cannot_submit_or_request_secret_paths(self):
        report = collect(self.base + "/hostile.html", self.output, allow_local=True, max_pages=2)
        self.assertFalse(any(method == "POST" for method, _ in FixtureHandler.requests_seen))
        self.assertFalse(any(path.startswith(("/.env", "/send", "/admin", "/delete", "/form-target.html")) for _, path in FixtureHandler.requests_seen))
        self.assertTrue(report["blocked_requests"])
        self.assertTrue(all(p["requested_url"].startswith(self.base) for p in report["pages"]))
        self.assertTrue(any("ignore previous instructions" in (self.output / e["text_path"]).read_text().lower() for p in report["pages"] for e in p["evidence"]))

    def test_output_symlink_is_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.output.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            collect(self.base, self.output, allow_local=True, max_pages=1)
        self.assertFalse(list(outside.iterdir()))

    def test_continuation_uses_prior_frontier_without_revisiting_seen_urls(self):
        discovery = importlib.import_module("proposition_runtime.discovery")
        self.assertTrue(callable(getattr(discovery, "continue_collect", None)), "Missing bounded continuation API")
        first = collect(self.base + "/", self.output, allow_local=True, max_pages=1)
        prior_path = self.output / "discovery.json"
        prior_sha = hashlib.sha256(prior_path.read_bytes()).hexdigest()
        second = discovery.continue_collect(prior_path, self.output.parent / "batch-2", allow_local=True, max_pages=2)
        self.assertNotIn(self.base + "/", second["coverage"]["attempted_urls"])
        self.assertEqual(2, len(second["coverage"]["attempted_urls"]))
        self.assertIn(self.base + "/", second["coverage"]["seen_urls"])
        self.assertEqual(prior_sha, second["continuation"]["previous_report_sha256"])
        self.assertTrue(second["continuation"]["previous_source_hashes"])
        self.assertTrue(second["coverage"]["frontier"])
        self.assertTrue({s["id"] for s in first["sources"]}.isdisjoint({s["id"] for s in second["sources"]}))
        self.assertFalse(second["coverage"]["exhaustive"])

    def test_continuation_refuses_changed_previous_proofs_before_network(self):
        discovery = importlib.import_module("proposition_runtime.discovery")
        self.assertTrue(callable(getattr(discovery, "continue_collect", None)), "Missing proof-aware continuation API")
        first = collect(self.base + "/", self.output, allow_local=True, max_pages=1)
        prior_path = self.output / "discovery.json"
        original_report = prior_path.read_bytes()
        changed = json.loads(original_report)
        changed["coverage"]["frontier"] = ["https://example.com/foreign"]
        prior_path.write_text(json.dumps(changed))
        FixtureHandler.requests_seen.clear()
        with self.assertRaises(ValueError):
            discovery.continue_collect(prior_path, self.output.parent / "foreign", allow_local=True, max_pages=2)
        self.assertFalse(FixtureHandler.requests_seen)
        prior_path.write_bytes(original_report)
        artifact = self.output / first["sources"][0]["artifacts"][0]["path"]
        artifact.write_text("altered evidence")
        FixtureHandler.requests_seen.clear()
        with self.assertRaises(ValueError):
            discovery.continue_collect(self.output / "discovery.json", self.output.parent / "batch-2", allow_local=True, max_pages=2)
        self.assertFalse(FixtureHandler.requests_seen)

    def test_empty_known_frontier_does_not_imply_exhaustive_site_analysis(self):
        discovery = importlib.import_module("proposition_runtime.discovery")
        first = collect(self.base + "/desktop.html", self.output, allow_local=True, max_pages=1)
        self.assertFalse(first["coverage"]["frontier"])
        FixtureHandler.requests_seen.clear()
        result = discovery.continue_collect(self.output / "discovery.json", self.output.parent / "empty-batch", allow_local=True)
        self.assertEqual("frontier_exhausted", result["status"])
        self.assertEqual([], result["coverage"]["attempted_urls"])
        self.assertTrue(result["coverage"]["known_frontier_exhausted"])
        self.assertFalse(result["coverage"]["exhaustive"])
        self.assertEqual("NOT_RUN", result["semantic_analysis"])
        self.assertFalse(FixtureHandler.requests_seen)


if __name__ == "__main__":
    unittest.main()
