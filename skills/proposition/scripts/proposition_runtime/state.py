"""Local, hash-bound run state. This module never contacts a network service.

Schemas validate structure; validate_run validates evidence freshness and gates.
PASS is a local evidence decision, not a publication or delivery permission.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
from uuid import uuid4

from jsonschema import Draft202012Validator


RESOURCE_ROOT = Path(__file__).resolve().parent
CONTRACT_ROOT = RESOURCE_ROOT / "contracts"
DATA_ROOT = RESOURCE_ROOT / "data"
DEFAULT_PUBLIC_FIELDS = ("title", "summary", "client_name", "facts.value",
                         "facts.source", "facts.observed_at", "next_step")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_COLLECTIONS = {"source": "sources", "fact": "facts", "artifact": "artifacts",
                "evaluation": "evaluations", "review": "reviews", "stage_review": "stage_reviews",
                "checkpoint": "checkpoints"}
_HEALTHY = {"COLLECTED", "CONFIRMED", "CURRENT", "PASS", "COMPLETE", "APPROVED", "NOT_APPLICABLE"}
PUBLICATION_STAGE = "publication.approved"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _record_digest(record):
    # A separate release approval cannot change the quality of unchanged bytes.
    payload = {key: value for key, value in record.items()
               if not ("path" in record and key in ("approval", "public_allowed"))}
    return _digest(payload)


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Identifiers must be short portable names")
    return value


def _no_symlinks(path):
    absolute = Path(os.path.abspath(path))
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            raise ValueError("Symlink paths are not accepted")
    return absolute


def _external_root(path):
    raw = Path(path).expanduser()
    if raw.is_symlink():
        raise ValueError("Symlink roots are not accepted")
    # Resolve OS directory aliases before establishing the evidence boundary.
    candidate = _no_symlinks(raw.resolve())
    protected = [RESOURCE_ROOT]
    for ancestor in RESOURCE_ROOT.parents:
        if (ancestor / "SKILL.md").is_file() or (ancestor / ".git").exists():
            protected.append(ancestor)
    if any(candidate == boundary or boundary in candidate.parents for boundary in protected):
        raise ValueError("Run data must live outside the checkout")
    return candidate


def _safe_path(root, path, *, exists=True):
    raw = Path(path)
    if ".." in raw.parts:
        raise ValueError("Parent traversal is not accepted")
    candidate = _no_symlinks(raw if raw.is_absolute() else root / raw)
    resolved = candidate.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("Evidence paths must remain inside the run")
    if exists and not resolved.is_file():
        raise ValueError("Evidence file is missing")
    return resolved


@lru_cache(maxsize=16)
def _validator(name):
    try:
        contract = json.loads((CONTRACT_ROOT / f"{name}.schema.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Contract {name} is unavailable") from error
    return Draft202012Validator(contract)


def _schema(name, value):
    errors = sorted(_validator(name).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        first = errors[0]
        raise ValueError(f"Invalid {name}: {'/'.join(map(str, first.path))}: {first.message}")


def _requirements():
    data = json.loads((DATA_ROOT / "requirements.json").read_text(encoding="utf-8"))
    rows = data["requirements"]
    expected = {f"R{i:02}" for i in range(1, 82)}
    if len(rows) != 81 or {row["id"] for row in rows} != expected:
        raise ValueError("The public requirement registry must cover R01 through R81 exactly once")
    return rows


def _stages():
    rows = json.loads((DATA_ROOT / "stages.json").read_text(encoding="utf-8"))["stages"]
    if len(rows) != 13 or len({row["id"] for row in rows}) != 13:
        raise ValueError("The stage registry must contain thirteen distinct named stages")
    return {row["id"]: row for row in rows}


def delivery_scope(state):
    return state["profile"]["parameters"].get("delivery_scope", "full")


def _quality_stages(state):
    return {key: row for key, row in _stages().items()
            if key != PUBLICATION_STAGE
            and not (delivery_scope(state) == "client" and key == "internal.handoffs")}


def _validate_structure(state):
    _schema("run", state)
    _schema("profile", state["profile"])
    for collection, schema in (("sources", "source"), ("facts", "fact"), ("artifacts", "artifact"),
                               ("evaluations", "evaluation"), ("reviews", "quality-review"),
                               ("stage_reviews", "quality-review"),
                               ("checkpoints", "checkpoint")):
        for key, record in state[collection].items():
            _identifier(key)
            _schema(schema, record)
            if record["id"] != key:
                raise ValueError(f"Mismatched identifier in {collection}")
    required_ids = {row["id"] for row in _requirements()}
    if set(state["requirement_ids"]) != required_ids:
        raise ValueError("Run coverage does not match the public registry")
    if not set(state["evaluations"]).issubset(required_ids):
        raise ValueError("Assessment lies outside the stable requirement registry")
    if not set(state["stage_reviews"]).issubset(_stages()):
        raise ValueError("Review lies outside the named stage registry")


def init_run(url, run_root, profile=None, *, creative_mandate=None):
    """Create a new run under run_root, which must be outside the checkout."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("An http(s) URL without credentials is required")
    base = _external_root(run_root)
    selected = {"actor": None, "responsible": None, "responsible_confirmed": False,
                "required_reviewers": ["review-a", "review-b"], "parameters": {}}
    if profile is not None:
        selected.update(deepcopy(profile))
    _schema('profile',selected)
    selected['parameters'].setdefault('proposal_contract',2)
    _schema("profile", selected)
    run_id = f"run-{uuid4().hex}"
    stamp = _now()
    from .experience import initial_exploration_contract
    contract,instruction=initial_exploration_contract(url,creative_mandate,stamp)
    root = base / run_id
    root.mkdir(parents=True, exist_ok=False)
    if instruction is not None:(root/'creative-mandate-input.txt').write_bytes(instruction)
    state = {"schema_version": "1.0", "id": run_id, "root": str(root), "url": url,
             "created_at": stamp, "updated_at": stamp, "profile": selected,
             "requirement_ids": [row["id"] for row in _requirements()],
             "sources": {}, "facts": {}, "artifacts": {}, "evaluations": {},
             "reviews": {}, "stage_reviews": {}, "checkpoints": {},
             "metadata": {"creative_exploration_contract":contract,"creative_reading_contract":1}}
    save_run(root, state)
    return state


def load_run(run_dir):
    """Read and structurally validate persisted state; never infer a PASS."""
    root = _external_root(run_dir)
    path = _safe_path(root, "state.json")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Run state cannot be read") from error
    _validate_structure(result)
    if Path(result["root"]) != root or result["id"] != root.name:
        raise ValueError("Run identity does not match its directory")
    return result


def save_run(run_dir, state):
    """Validate then atomically replace state.json, preserving run identity."""
    root = _external_root(run_dir)
    _validate_structure(state)
    if Path(state["root"]) != root or state["id"] != root.name:
        raise ValueError("State belongs to a different run")
    target = _safe_path(root, "state.json", exists=False)
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        if previous.get("id") != state["id"]:
            raise ValueError("Cannot replace a different run")
        contract=previous.get('metadata',{}).get('creative_exploration_contract')
        if contract is not None and state.get('metadata',{}).get('creative_exploration_contract')!=contract:
            raise ValueError('Initialized creative exploration contract cannot be changed or removed')
        reading=previous.get('metadata',{}).get('creative_reading_contract')
        if reading is not None and state.get('metadata',{}).get('creative_reading_contract')!=reading:
            raise ValueError('Initialized creative reading contract cannot be changed or removed')
    payload = deepcopy(state)
    payload["updated_at"] = _now()
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical(payload) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _resolve(state, reference):
    if not isinstance(reference, str) or ":" not in reference:
        return None
    kind, identifier = reference.split(":", 1)
    return state.get(_COLLECTIONS.get(kind, ""), {}).get(identifier)


def _dependency_closure(state, references):
    pending = list(references)
    visited = set()
    while pending:
        reference = pending.pop()
        if reference in visited:
            continue
        visited.add(reference)
        record = _resolve(state, reference)
        if record:
            pending.extend(record.get("dependencies", []))
    return visited


def _dependency_hashes(state, dependencies):
    hashes = {}
    for reference in dependencies:
        record = _resolve(state, reference)
        if record is None:
            raise ValueError(f"Missing dependency: {reference}")
        hashes[reference] = _record_digest(record)
    return hashes


def _bind(state, record, dependencies):
    record["dependencies"] = list(dict.fromkeys(dependencies))
    record["dependency_hashes"] = _dependency_hashes(state, record["dependencies"])
    record["profile_hash"] = _digest(state["profile"])
    return record


def add_source(run_dir, source_id, path=None, *, kind="public", locator=None,
               status="COLLECTED", audience="internal", required=True):
    """Register a collected local copy or an explicit unavailable source."""
    state = load_run(run_dir)
    record = _source_record(state, source_id, path, kind=kind, locator=locator,
                            status=status, audience=audience, required=required)
    state['sources'][source_id] = record
    save_run(run_dir,state)
    return record


def _source_record(state, source_id, path=None, *, kind='public', locator=None,
                   status='COLLECTED', audience='internal', required=True):
    """Build and validate without writing; used by atomic evidence bundles."""
    root = Path(state["root"])
    evidence = _safe_path(root, path) if path is not None else None
    record = {"id": _identifier(source_id), "kind": kind, "locator": locator,
              "path": evidence.relative_to(root).as_posix() if evidence else None,
              "sha256": _sha(evidence) if evidence else None, "status": status,
              "audience": audience, "required": required, "observed_at": _now()}
    _schema("source", record)
    return record


def add_fact(run_dir, fact_id, value, source_ids, *, status="CONFIRMED",
             audience="internal", public_allowed=False, required=True):
    """Register provenance without making private/public visibility equivalent."""
    state = load_run(run_dir)
    source_ids = [identifier.removeprefix("source:") for identifier in source_ids]
    record = {"id": _identifier(fact_id), "value": value, "source_ids": source_ids,
              "status": status, "audience": audience, "public_allowed": public_allowed,
              "required": required, "recorded_at": _now()}
    _bind(state, record, [f"source:{identifier}" for identifier in source_ids])
    _schema("fact", record)
    state["facts"][fact_id] = record
    save_run(run_dir, state)
    return record


def add_artifact(run_dir, artifact_id, path, audience, dependencies=()):
    """Hash a local file. Registration alone grants no quality/release approval."""
    state = load_run(run_dir)
    record = _artifact_record(state,artifact_id,path,audience,dependencies)
    state['artifacts'][artifact_id] = record
    save_run(run_dir,state)
    return record


def _artifact_record(state, artifact_id, path, audience, dependencies=()):
    root = Path(state["root"])
    evidence = _safe_path(root, path)
    record = {"id": _identifier(artifact_id), "path": evidence.relative_to(root).as_posix(),
              "sha256": _sha(evidence), "size_bytes": evidence.stat().st_size,
              "audience": audience, "status": "CURRENT", "public_allowed": False,
              "approval": None, "recorded_at": _now()}
    _bind(state, record, dependencies)
    _schema("artifact", record)
    return record


def record_evaluation(run_dir, requirement_id, evaluation):
    """Record Rxx completeness, or 'quality' plus a required reviewer's receipt."""
    state = load_run(run_dir)
    record = deepcopy(evaluation)
    record.setdefault("status", "UNKNOWN")
    record.setdefault("evidence", [])
    record.setdefault("unknowns", [])
    dependencies = list(record.pop("dependencies", [])) + list(record["evidence"])
    record.pop("dependency_hashes", None)
    record["recorded_at"] = _now()
    if requirement_id == "quality":
        reviewer = _identifier(record.get("reviewer_id", ""))
        record["id"] = reviewer
        record.setdefault("scores", [0, 0, 0, 0, 0])
        record.setdefault("independence", {})
        receipt_id = record["independence"].get("receipt_id")
        if receipt_id in state["artifacts"]:
            dependencies.append(f"artifact:{receipt_id}")
        _bind(state, record, dependencies)
        _schema("quality-review", record)
        state["reviews"][reviewer] = record
    else:
        if requirement_id not in state["requirement_ids"]:
            raise ValueError("Unknown requirement identifier")
        record["id"] = requirement_id
        record.setdefault("applicable", True)
        record.setdefault("reason", "")
        _bind(state, record, dependencies)
        _schema("evaluation", record)
        state["evaluations"][requirement_id] = record
    save_run(run_dir, state)
    return record


def record_checkpoint(run_dir, checkpoint_id, stage_id, checkpoint):
    """Persist a local checkpoint; an approval must bind an actor and plan hash."""
    stages = json.loads((DATA_ROOT / "stages.json").read_text())["stages"]
    if stage_id not in {stage["id"] for stage in stages}:
        raise ValueError("Unknown named stage")
    state = load_run(run_dir)
    record = deepcopy(checkpoint)
    record.update(id=_identifier(checkpoint_id), stage_id=stage_id, recorded_at=_now())
    record.setdefault("status", "WAITING")
    record.setdefault("required", False)
    record.setdefault("approval", None)
    dependencies = list(record.pop("dependencies", []))
    if record["approval"]:
        dependencies.append(record["approval"]["plan_ref"])
    _bind(state, record, dependencies)
    _schema("checkpoint", record)
    if record["status"] == "APPROVED" and not _valid_approval(state, record.get("approval")):
        raise ValueError("Approval does not bind the current plan and an actor")
    state["checkpoints"][checkpoint_id] = record
    save_run(run_dir, state)
    return record


def record_stage_review(run_dir, stage_id, review):
    """Record one explicit scored review for a named stage, never infer a score."""
    if stage_id not in _stages():
        raise ValueError("Unknown named stage")
    state = load_run(run_dir)
    record = deepcopy(review)
    record.update(id=stage_id, stage_id=stage_id, recorded_at=_now())
    record["reviewer_id"] = _identifier(record.get("reviewer_id", ""))
    record.setdefault("status", "UNKNOWN")
    record.setdefault("scores", [0, 0, 0, 0, 0])
    record.setdefault("independence", {})
    record.setdefault("evidence", [])
    record.setdefault("unknowns", [])
    for references in record.get("criterion_evidence", {}).values():
        record["evidence"].extend(reference for reference in references if reference not in record["evidence"])
    dependencies = list(record.pop("dependencies", [])) + list(record["evidence"])
    record.pop("dependency_hashes", None)
    receipt_id = record["independence"].get("receipt_id")
    if receipt_id in state["artifacts"]:
        dependencies.append(f"artifact:{receipt_id}")
    _bind(state, record, dependencies)
    _schema("quality-review", record)
    state["stage_reviews"][stage_id] = record
    save_run(run_dir, state)
    return record


def _valid_approval(state, approval):
    if not isinstance(approval, dict) or not approval.get("actor"):
        return False
    artifact = _resolve(state, approval.get("plan_ref"))
    if not (artifact and artifact.get("status") == "CURRENT"
            and artifact.get("sha256") == approval.get("plan_sha256")):
        return False
    try:
        path = _safe_path(Path(state["root"]), artifact["path"])
        return _sha(path) == approval["plan_sha256"]
    except (OSError, ValueError):
        return False


def _stale_reasons(state, root, record):
    reasons = []
    dependencies = record.get("dependencies", [])
    if "dependencies" in record:
        expected = set(record.get("evidence", []))
        expected.update(f"source:{source_id}" for source_id in record.get("source_ids", []))
        if record.get("approval") and "plan_ref" in record["approval"]:
            expected.add(record["approval"]["plan_ref"])
        if not expected.issubset(dependencies) or set(record.get("dependency_hashes", {})) != set(dependencies):
            reasons.append("unbound_evidence")
    if record.get("profile_hash") and record["profile_hash"] != _digest(state["profile"]):
        reasons.append("profile_changed")
    if "path" in record:
        try:
            path = _safe_path(root, record["path"]) if record["path"] else None
            if path is None or _sha(path) != record.get("sha256"):
                reasons.append("file_changed_or_missing")
        except (OSError, ValueError):
            reasons.append("file_changed_or_missing")
    for reference in dependencies:
        dependency = _resolve(state, reference)
        if (dependency is None or dependency.get("status") not in _HEALTHY
                or record.get("dependency_hashes", {}).get(reference) != _record_digest(dependency)):
            reasons.append("dependency_changed_or_missing")
    if record.get("status") == "APPROVED" and not _valid_approval(state, record.get("approval")):
        reasons.append("approval_plan_changed")
    return reasons


def invalidate_changed(run_dir):
    """Persist STALE transitively; never refresh a hash to hide an old decision."""
    state = load_run(run_dir)
    root = Path(state["root"])
    invalidated = []
    changed = True
    while changed:
        changed = False
        for kind, collection in _COLLECTIONS.items():
            for identifier, record in state[collection].items():
                if record["status"] == "STALE":
                    continue
                if kind == "source" and not record.get("path") and record["status"] != "COLLECTED":
                    continue
                if _stale_reasons(state, root, record):
                    record["status"] = "STALE"
                    invalidated.append(f"{kind}:{identifier}")
                    changed = True
    if invalidated:
        save_run(root, state)
    return {"status": "STALE" if invalidated else "UNCHANGED", "invalidated": invalidated}


def _review_receipt_issues(state, root, review, stage_id=None):
    receipt_id = review.get("independence", {}).get("receipt_id")
    artifact = state["artifacts"].get(receipt_id)
    if not artifact or artifact["status"] != "CURRENT":
        return ["A current hashed independence receipt is required"]
    try:
        path = _safe_path(root, artifact["path"])
        if _sha(path) != artifact["sha256"]:
            return ["Independence receipt changed"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        _schema("review-receipt", receipt)
    except (ValueError, OSError, json.JSONDecodeError):
        return ["Independence receipt is malformed"]
    if (receipt["run_id"] != state["id"] or receipt["reviewer_id"] != review["reviewer_id"]
            or receipt["reviewer_id"] == state["profile"].get("actor")
            or receipt["author_id"] != state["profile"].get("actor")
            or not receipt["context_isolated"] or receipt["author_context_inherited"]
            or receipt["verdict_shared"]):
        return ["The receipt does not establish an isolated review of this run"]
    if receipt.get("stage_id") != stage_id:
        return ["The receipt belongs to a different review scope or stage"]
    reviewed = receipt["artifact_hashes"]
    evidence_artifacts = {ref for ref in review["evidence"] if ref.startswith("artifact:")}
    if not evidence_artifacts or not evidence_artifacts.issubset(reviewed):
        return ["The receipt must identify hashes of every reviewed artifact"]
    for reference, sha in reviewed.items():
        target = _resolve(state, reference)
        if not target or target.get("status") != "CURRENT" or target.get("sha256") != sha:
            return ["The review applies to a different artifact version"]
    return []


def _stage_report(state, stage_id):
    stage = _stages().get(stage_id)
    if stage is None:
        raise ValueError("Unknown named stage")
    if stage_id == "internal.handoffs" and delivery_scope(state) == "client":
        return {"stage_id": stage_id, "status": "NOT_APPLICABLE", "score": None,
                "issues": [], "reason": "Internal deliverables excluded by explicit client scope"}
    requirements = [row for row in _requirements() if row["stage_id"] == stage_id]
    issues = []
    if stage_id in {'discovery.channels','company.v1','company.v2','analysis.specialists','brief.public','creative.direction','client.composition','verify.final'}:
        from .history import inspect_history
        for message in inspect_history(state)['issues']:
            issues.append({'code':'historical_provenance','id':stage_id,'message':message})

    def issue(code, identifier, message):
        issues.append({"code": code, "id": identifier, "message": message})

    for requirement in requirements:
        evaluation = state["evaluations"].get(requirement["id"])
        if evaluation is None:
            issue("missing_evaluation", requirement["id"], "Stage requirement has no assessment")
            continue
        if evaluation["status"] == "STALE":
            issue("stale_evidence", requirement["id"], "Stage evidence is stale")
        elif evaluation["status"] == "NOT_APPLICABLE":
            if (requirement.get("applicability") != "conditional" or evaluation["applicable"]
                    or not evaluation["reason"].strip() or not evaluation["evidence"]):
                issue("unjustified_non_applicability", requirement["id"], "Stage applicability is unproven")
        elif evaluation["status"] != "PASS" or not evaluation["applicable"]:
            issue("requirement_not_passed", requirement["id"], "Stage requirement has not passed")
        if not evaluation["evidence"] or evaluation["unknowns"]:
            issue("missing_evidence", requirement["id"], "Stage needs evidence without decisive unknowns")
    if stage_id in {"creative.direction", "client.composition", "export.documents"}:
        from .preservation import inspect_preservation
        preservation = inspect_preservation(state, selection_only=stage_id == "creative.direction")
        for message in preservation["issues"]:
            issue("creative_preservation", stage_id, message)
    if stage_id in {"creative.direction", "client.composition", "export.documents", "verify.final"}:
        from .experience import inspect_experience
        for message in inspect_experience(state, stage_id)["issues"]:
            issue("creative_experience", stage_id, message)
    review = state["stage_reviews"].get(stage_id)
    score = None
    if review is None:
        issue("missing_stage_review", stage_id, "A scored isolated stage review is required")
    else:
        score = sum(review["scores"])
        criterion_evidence = review.get("criterion_evidence", {})
        if set(criterion_evidence) != {row["id"] for row in stage["criteria"]}:
            issue("missing_criterion_evidence", stage_id, "Every stage criterion needs its own evidence references")
        for criterion in stage["criteria"]:
            references = criterion_evidence.get(criterion["id"], [])
            if not references or any(
                not reference.startswith("artifact:") or reference not in review["evidence"]
                or _resolve(state, reference) is None or _resolve(state, reference)["status"] != "CURRENT"
                for reference in references
            ):
                issue("missing_criterion_evidence", stage_id, "Criterion evidence must name current reviewed artifacts")
        if review["status"] == "STALE":
            issue("stale_evidence", stage_id, "Stage review no longer matches its inputs")
        elif review["status"] != "PASS" or review["unknowns"]:
            issue("stage_review_not_passed", stage_id, "The explicit stage review has not passed")
        if score < stage["gate"]["minimum_score"]:
            issue("stage_review_score", stage_id, "The stage score must be at least 9/10")
        for index, criterion in enumerate(stage["criteria"]):
            exploration_required=(stage_id=='creative.direction' and criterion['id']=='options'
                                  and state.get('metadata',{}).get('creative_exploration_contract') is not None)
            if (criterion["id"] in stage["gate"].get("required_full_scores", []) or exploration_required) and review["scores"][index] != 2:
                issue("stage_critical_score", stage_id, "Critical criterion requires 2/2: " + criterion["id"])
        for message in _review_receipt_issues(state, Path(state["root"]), review, stage_id):
            issue("review_independence", stage_id, message)
    status = "STALE" if any(row["code"] == "stale_evidence" for row in issues) else "BLOCKED"
    return {"stage_id": stage_id, "status": status if issues else "PASS", "score": score,
            "issues": issues, "requirement_ids": [row["id"] for row in requirements],
            "criteria": stage["criteria"], "expected_evidence": stage["expected_evidence"],
            "quality_rubric": "candidate-not-human-calibrated"}


def stage_report(run_dir, stage_id):
    """Evaluate this stage alone; other stage/final reviews need not yet exist."""
    invalidate_changed(run_dir)
    return _stage_report(load_run(run_dir), stage_id)


def next_stage(run_dir):
    """Return the first unpassed active stage from registered evidence, never sidecars."""
    invalidate_changed(run_dir)
    state = load_run(run_dir)
    for stage_id in _quality_stages(state):
        report = _stage_report(state, stage_id)
        if report["status"] != "PASS":
            return {"status": "BLOCKED", "scope": delivery_scope(state),
                    "stage_id": stage_id, "score": report["score"],
                    "issues": report["issues"], "can_promote": False}
    final = validate_run(run_dir)
    return {"status": final["status"], "scope": delivery_scope(state),
            "stage_id": None if final["status"] == "PASS" else "final.reviews",
            "issues": final["issues"], "can_promote": final["status"] == "PASS"}


def validate_run(run_dir):
    """Return {status, issues}; no averaging, no default PASS, no external action."""
    try:
        invalidate_changed(run_dir)
        state = load_run(run_dir)
    except (ValueError, OSError) as error:
        return {"status": "BLOCKED", "issues": [{"code": "invalid_state", "message": str(error)}]}
    issues = []
    root = Path(state["root"])
    active_stages = _quality_stages(state)
    active_requirements = [row for row in _requirements()
                           if row["stage_id"] in active_stages or row["stage_id"] == PUBLICATION_STAGE]
    publication_ids = {row["id"] for row in _requirements() if row["stage_id"] == PUBLICATION_STAGE}
    quality_roots = [f"evaluation:{identifier}" for identifier in state["evaluations"]
                     if identifier not in publication_ids]
    quality_roots += [f"review:{identifier}" for identifier in state["reviews"]]
    quality_roots += [f"stage_review:{identifier}" for identifier in state["stage_reviews"]
                      if identifier != PUBLICATION_STAGE]
    publication_roots = [f"evaluation:{identifier}" for identifier in state["evaluations"]
                         if identifier in publication_ids]
    publication_roots += [f"stage_review:{PUBLICATION_STAGE}"]
    publication_roots += [f"checkpoint:{identifier}" for identifier, record in state["checkpoints"].items()
                         if record["stage_id"] == PUBLICATION_STAGE]
    quality_refs = _dependency_closure(state, quality_roots)
    publication_only = _dependency_closure(state, publication_roots) - quality_refs

    def issue(code, identifier, message):
        issues.append({"code": code, "id": identifier, "message": message})

    if not state["profile"].get("responsible") or not state["profile"].get("responsible_confirmed"):
        issue("responsible_unconfirmed", "profile", "A confirmed responsible person is required")
    if not state["profile"].get("actor"):
        issue("actor_unknown", "profile", "The invoking actor must be identified")
    for kind, collection in _COLLECTIONS.items():
        for identifier, record in state[collection].items():
            reference = f"{kind}:{identifier}"
            if (reference in publication_only
                    or (record.get("metadata", {}).get("scope") == "publication" and reference not in quality_refs)):
                continue
            if not record.get("required", True):
                continue
            if record["status"] not in _HEALTHY:
                issue("stale_evidence" if record["status"] == "STALE" else "unknown_evidence",
                      f"{kind}:{identifier}", "Evidence is not current and confirmed")
            if kind == "fact":
                if not record["source_ids"] or record["value"] is None:
                    issue("unsupported_fact", identifier, "A fact needs a value and source provenance")
                for source_id in record["source_ids"]:
                    source = state["sources"].get(source_id)
                    if source is None or source["status"] != "COLLECTED":
                        issue("missing_source", identifier, "A fact's source is missing or unavailable")
    for requirement in active_requirements:
        if requirement["stage_id"] == PUBLICATION_STAGE:
            continue
        identifier = requirement["id"]
        evaluation = state["evaluations"].get(identifier)
        if evaluation is None:
            issue("missing_evaluation", identifier, "Requirement has no evidence assessment")
            continue
        if evaluation["unknowns"]:
            issue("decisive_unknown", identifier, "Unresolved unknowns cannot pass the gate")
        if evaluation["status"] == "NOT_APPLICABLE":
            if (requirement.get("applicability", "always") != "conditional" or evaluation["applicable"]
                    or not evaluation["reason"].strip() or not evaluation["evidence"]):
                issue("unjustified_non_applicability", identifier, "Non-applicability needs a reason and evidence")
        elif evaluation["status"] != "PASS" or not evaluation["applicable"]:
            issue("requirement_not_passed", identifier, "Applicable requirement has not passed")
        if not evaluation["evidence"]:
            issue("missing_evidence", identifier, "A status alone is not evidence")
    for reviewer in state["profile"]["required_reviewers"]:
        review = state["reviews"].get(reviewer)
        if review is None:
            issue("missing_review", reviewer, "Required independent review is absent")
            continue
        if review["status"] != "PASS" or review["unknowns"]:
            issue("review_not_passed", reviewer, "Required review has not passed")
        if sum(review["scores"]) < 9:
            issue("review_score", reviewer, "Each required reviewer must independently score at least 9/10")
        for message in _review_receipt_issues(state, root, review):
            issue("review_independence", reviewer, message)
    stage_reports = {}
    for stage_id in active_stages:
        report = _stage_report(state, stage_id)
        stage_reports[stage_id] = {"status": report["status"], "score": report["score"]}
        issues.extend(report["issues"])
    publication = _stage_report(state, PUBLICATION_STAGE)
    publication["review_status"] = publication["status"]
    if PUBLICATION_STAGE not in state["stage_reviews"]:
        publication["status"] = "NOT_RUN"
    publication["scope"] = "external_persistence_review"
    publication["execution"] = "NOT_REPORTED_BY_THIS_LOCAL_RUNTIME"
    return {"status": ("STALE" if any(i["code"] == "stale_evidence" for i in issues)
                       else "BLOCKED") if issues else "PASS", "issues": issues,
            "scope": delivery_scope(state),
            "excluded_stages": ["internal.handoffs"] if delivery_scope(state) == "client" else [],
            "coverage": {"required": len(active_requirements), "recorded": len(state["evaluations"]),
                         "preparation_required": len(active_requirements) - len(publication_ids)},
            "stages": stage_reports,
            "publication": publication,
            "quality_rubric": "candidate-not-human-calibrated"}


def project_public(data, allowed_fields=DEFAULT_PUBLIC_FIELDS):
    """Project explicitly named scalar paths, including paths inside lists.

    A container name alone never copies its children. Field selection does not
    certify that an allowed scalar is safe; its provenance still needs review.
    """
    tree = {}
    for field in allowed_fields:
        if not isinstance(field, str) or not field or any(not _ID.fullmatch(p) for p in field.split(".")):
            raise ValueError("Public allowlist entries must be dotted field paths")
        branch = tree
        for part in field.split("."):
            branch = branch.setdefault(part, {})
        branch[None] = True

    omitted = object()

    def select(value, permitted):
        if isinstance(value, dict):
            if (value.get("audience") in ("sales", "technical", "internal")
                    or value.get("public_allowed") is False):
                return omitted
            result = {}
            for key, child in value.items():
                if key not in permitted:
                    continue
                if isinstance(child, dict) and not any(k is not None for k in permitted[key]):
                    continue
                selected = select(child, permitted[key])
                if selected is not omitted:
                    result[key] = selected
            return result
        if isinstance(value, list):
            selected = [select(child, permitted) for child in value
                        if not isinstance(child, (dict, list)) or any(k is not None for k in permitted)]
            return [child for child in selected if child is not omitted]
        return deepcopy(value) if permitted.get(None) else None
    selected = select(data, tree)
    return {} if selected is omitted else selected


def build_public_packet(run_dir, output_dir, files):
    """Prepare explicit approved client/public files locally; never publish them."""
    report = validate_run(run_dir)
    if report["status"] != "PASS":
        raise ValueError("The quality gate has not passed for the current evidence")
    return _build_packet(run_dir, output_dir, files, "final_delivery")


def build_context_packet(run_dir, output_dir, files):
    """Prepare approved creative inputs after the brief gate, before final work."""
    if stage_report(run_dir, "brief.public")["status"] != "PASS":
        raise ValueError("The current public brief has not passed its stage gate")
    from .experience import require_packet_methods
    require_packet_methods(load_run(run_dir), files)
    return _build_packet(run_dir, output_dir, files, "creative_input")


def _build_packet(run_dir, output_dir, files, scope):
    state = load_run(run_dir)
    root = Path(state["root"])
    destination = _external_root(output_dir)
    if destination.exists():
        raise ValueError("Packet output must be a new directory")
    if not files:
        raise ValueError("An explicit artifact allowlist is required")
    selected = []
    for requested in files:
        artifact = state["artifacts"].get(requested)
        if artifact is None:
            artifact = next((row for row in state["artifacts"].values() if row["path"] == str(requested)), None)
        if not artifact or artifact["audience"] not in ("client", "public") or not artifact["public_allowed"]:
            raise ValueError("Only explicitly allowed client/public artifacts may enter the packet")
        approval = artifact.get("approval")
        if not approval or not approval.get("actor") or approval.get("sha256") != artifact["sha256"]:
            raise ValueError("The public artifact needs approval bound to its exact hash")
        source = _safe_path(root, artifact["path"])
        if artifact["status"] != "CURRENT" or _sha(source) != artifact["sha256"]:
            raise ValueError("The public artifact changed after assessment")
        if scope == "creative_input":
            linked = _dependency_closure(state, [f"artifact:{artifact['id']}"])
            if not any(reference.startswith(("source:", "fact:")) for reference in linked):
                raise ValueError("A creative input needs linked current source or fact provenance")
        selected.append((source, artifact))
    # Keep the relative resource tree, so HTML/CSS/font/media links still work.
    # A shared leading folder is stripped for a convenient standalone packet.
    common = Path(os.path.commonpath([str(source.parent) for source, _ in selected]))
    filenames = {'manifest.json'}
    named = []
    for source, artifact in selected:
        name = source.relative_to(common).as_posix()
        if name in filenames:
            raise ValueError('Packet filenames must be unique')
        filenames.add(name)
        named.append((source,artifact,name))
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".packet-", dir=destination.parent))
    try:
        manifest = {"status": "PREPARED", "scope": scope, "files": []}
        for source, artifact, name in named:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if _sha(target) != artifact["sha256"]:
                raise ValueError("The artifact changed while preparing the packet")
            manifest["files"].append({"name": name, "sha256": artifact["sha256"],
                                      "size_bytes": target.stat().st_size})
        _schema("packet", manifest)
        (staging / "manifest.json").write_bytes(_canonical(manifest) + b"\n")
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"status": "PREPARED", "root": str(destination), "files": manifest["files"],
            "scope": scope, "publication": "NOT_REQUESTED"}
