"""Exact-plan local attestations and a file-backed fixture adapter.

No live publication connector or private platform credentials are bundled.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_plan(run_dir: Path) -> dict:
    plan = json.loads((Path(run_dir) / "publication/plan.json").read_text())
    body = {k: v for k, v in plan.items() if k != "sha256"}
    if hashlib.sha256(canonical(body)).hexdigest() != plan["sha256"]:
        raise ValueError("Stored plan fingerprint changed")
    return plan


def prepare_plan(run_dir: Path, payload: dict) -> dict:
    if not isinstance(payload.get("actor"), str) or not payload["actor"].strip():
        raise ValueError("Plan requires an authenticated-actor reference")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Plan requires explicit items")
    ids = set()
    for item in items:
        if not isinstance(item, dict) or any(not item.get(k) for k in ("id", "destination", "action", "content")):
            raise ValueError("Each item needs id, destination, action and exact content")
        if item["id"] in ids:
            raise ValueError("Duplicate plan item")
        ids.add(item["id"])
    plan = {"version": 1, "actor": payload["actor"], "items": items}
    plan["sha256"] = hashlib.sha256(canonical(plan)).hexdigest()
    directory = Path(run_dir) / "publication"
    previous = directory / "plan.json"
    approval = directory / "approval.json"
    if previous.exists() and read_plan(run_dir)["sha256"] != plan["sha256"]:
        approval.unlink(missing_ok=True)
    write_json(previous, plan)
    return plan


def approve_plan(run_dir: Path, plan_hash: str, actor: str, evidence: Path) -> dict:
    run_dir, evidence = Path(run_dir).resolve(), Path(evidence).resolve()
    plan = read_plan(run_dir)
    if plan_hash != plan["sha256"] or actor != plan["actor"]:
        raise ValueError("Approval actor or plan hash does not match")
    if not evidence.is_relative_to(run_dir) or not evidence.is_file():
        raise ValueError("Approval evidence must be a file within this run")
    approval = {"plan_sha256": plan_hash, "actor": actor, "evidence": evidence.relative_to(run_dir).as_posix(), "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(), "authority": "local_human_attestation_not_server_identity"}
    write_json(run_dir / "publication/approval.json", approval)
    return approval


class FixtureAdapter:
    """Local deterministic storage only; does not contact a real service."""
    def __init__(self, path: Path, *, uncertain_once: bool = False):
        self.path = Path(path)
        self.uncertain_once = uncertain_once

    def _state(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {"writes": 0, "records": {}}

    @property
    def write_count(self):
        return self._state()["writes"]

    def capabilities(self):
        return {"mode": "fixture", "write": True, "external_effects": False}

    def lookup(self, key: str):
        return self._state()["records"].get(key)

    def write(self, item: dict, key: str):
        state = self._state()
        if key not in state["records"]:
            state["writes"] += 1
            state["records"][key] = {"id": key, "item": item, "content_sha256": hashlib.sha256(canonical(item)).hexdigest()}
            write_json(self.path, state)
        if self.uncertain_once:
            self.uncertain_once = False
            return {"status": "UNCERTAIN"}
        return {"status": "SUCCESS", "id": key}

    def readback(self, identifier):
        return self.lookup(identifier)


def publish_plan(run_dir: Path, adapter: FixtureAdapter) -> dict:
    run_dir = Path(run_dir).resolve()
    plan = read_plan(run_dir)
    approval_path = run_dir / "publication/approval.json"
    if not approval_path.is_file():
        raise ValueError("Exact human approval is missing")
    approval = json.loads(approval_path.read_text())
    if approval.get("plan_sha256") != plan["sha256"] or approval.get("actor") != plan["actor"]:
        raise ValueError("Plan approval is stale")
    evidence = (run_dir / approval["evidence"]).resolve()
    if not evidence.is_relative_to(run_dir) or not evidence.is_file() or hashlib.sha256(evidence.read_bytes()).hexdigest() != approval["evidence_sha256"]:
        raise ValueError("Approval evidence changed or is unavailable")
    if adapter.capabilities().get("mode") != "fixture":
        raise ValueError("Live publication requires a separately authorized private connector")
    results = []
    for item in plan["items"]:
        key = hashlib.sha256(canonical([plan["sha256"], item["id"]])).hexdigest()
        existing = adapter.lookup(key)
        if existing is None:
            outcome = adapter.write(item, key)
            # Never repeat an uncertain create. A later run must look up the same key.
            if outcome.get("status") not in {"SUCCESS", "UNCERTAIN"}:
                results.append({"item_id": item["id"], "status": "FAILED"})
                continue
        checked = adapter.readback(key)
        expected = hashlib.sha256(canonical(item)).hexdigest()
        status = "VERIFIED" if checked and checked.get("content_sha256") == expected else "UNCERTAIN"
        results.append({"item_id": item["id"], "idempotency_key": key, "status": status})
    receipt = {"status": "VERIFIED" if all(r["status"] == "VERIFIED" for r in results) else "PARTIAL", "scope": "fixture_only", "real_publication": "NOT_RUN", "quality": "NOT_CERTIFIED_BY_THIS_OPERATION", "plan_sha256": plan["sha256"], "items": results}
    write_json(run_dir / "publication/receipt.json", receipt)
    return receipt
