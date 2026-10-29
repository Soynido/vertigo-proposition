"""Retrieve pinned public trees or explicit source selections as inert cache data.

No shell, installer, upstream Python, skill instruction, or build step is run.
Receipts record transport provenance and local integrity, not signed attestations
or evidence of a skill's native/adapted execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit

LOCK_PATH = Path(__file__).parent / "data/upstream-lock.json"
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_FILES = 10000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected HTTP redirect is refused")


def _download(url: str, limit: int) -> bytes:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"api.github.com", "codeload.github.com"} or parts.username or parts.password or parts.port:
        raise ValueError("Only exact public GitHub HTTPS endpoints are permitted")
    request = urllib.request.Request(url, headers={"User-Agent": "vertigo-proposition-source-cache/1", "Accept": "application/vnd.github+json" if parts.hostname == "api.github.com" else "application/octet-stream"})
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected response redirect is refused")
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Download exceeds the configured byte budget")
    return content


def _relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        raise ValueError("Unsafe repository path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError("Repository path escapes its source tree")
    return path.as_posix()


def _families() -> list[dict]:
    data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("families"), list):
        raise ValueError("Unsupported upstream lock")
    seen = set()
    for item in data["families"]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", item["id"]) or item["id"] in seen:
            raise ValueError("Invalid or duplicate family ID")
        seen.add(item["id"])
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", item["repository"]):
            raise ValueError("Invalid repository identity")
        if not re.fullmatch(r"[0-9a-f]{40}", item["commit"]):
            raise ValueError("Every upstream must be pinned to a full immutable commit")
        if not item.get("license_files") or not item.get("entrypoints"):
            raise ValueError("License and entrypoint contracts are required")
        required = item["license_files"] + item["entrypoints"] + item.get("reference_files", [])
        for path in required:
            _relative(path)
        selection = item.get("source_paths")
        if selection is not None:
            if (not isinstance(selection, list) or not selection or
                    not all(isinstance(p, str) for p in selection) or len(set(selection)) != len(selection)):
                raise ValueError("Source selection must be an explicit nonempty path list")
            for path in selection:
                _relative(path)
            if not all(_selected(path, item) for path in required):
                raise ValueError("Source selection must cover entrypoints, references and licenses")
    return data["families"]


def _selected(name: str, spec: dict) -> bool:
    paths = spec.get("source_paths")
    return paths is None or any(name == p or name.startswith(p + "/") for p in paths)


def _cache_root(cache: str | Path | None) -> Path:
    cache_home = Path(os.environ["XDG_CACHE_HOME"]) if os.environ.get("XDG_CACHE_HOME") else Path.home() / ".cache"
    default = cache_home / "vertigo-proposition" / "upstreams"
    path = Path(cache or os.environ.get("PROPOSITION_UPSTREAM_CACHE", default)).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Cache paths must not traverse symbolic links")
    resolved = path.resolve()
    package = Path(__file__).resolve().parent
    protected = {package}
    protected.update(parent for parent in package.parents
                     if (parent / ".git").exists() or (parent / "SKILL.md").is_file())
    if any(resolved == root or root in resolved.parents for root in protected):
        raise ValueError("Upstream cache must remain outside the checkout, skill and runtime package")
    return resolved


def _checked(path: Path) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symbolic links are refused in the cache")


def _tree(metadata: dict, spec: dict) -> dict[str, dict]:
    if metadata.get("truncated") is not False:
        raise ValueError("Truncated or incomplete GitHub tree metadata")
    entries = metadata.get("tree")
    if not isinstance(entries, list) or len(entries) > MAX_FILES * 2:
        raise ValueError("Invalid or oversized repository inventory")
    files = {}
    for entry in entries:
        name = _relative(entry["path"])
        # Unselected objects are metadata only: never fetch, follow or materialize them.
        # Full-tree families retain the strict rejection of every link/submodule.
        if not _selected(name, spec):
            continue
        if entry.get("mode") == "120000" or entry.get("type") == "commit":
            raise ValueError("Upstream symlinks and submodules are refused")
        if entry.get("type") == "tree":
            continue
        if entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}:
            raise ValueError("Unsupported upstream object mode")
        if name in files or not re.fullmatch(r"[0-9a-f]{40}", entry.get("sha", "")):
            raise ValueError("Duplicate path or invalid Git blob identity")
        size = entry.get("size")
        if not isinstance(size, int) or size < 0 or size > MAX_FILE_BYTES:
            raise ValueError("Invalid or oversized upstream file")
        files[name] = entry
    if len(files) > MAX_FILES or sum(f["size"] for f in files.values()) > MAX_EXPANDED_BYTES:
        raise ValueError("Repository exceeds extraction budgets")
    for name in spec["entrypoints"] + spec["license_files"] + spec.get("reference_files", []):
        if name not in files:
            raise ValueError("Pinned entrypoint or license is absent: " + name)
    for prefix in spec.get("source_paths", []):
        if not any(name == prefix or name.startswith(prefix + "/") for name in files):
            raise ValueError("Selected source path is absent: " + prefix)
    return files


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _base(spec: dict, root: Path) -> dict:
    destination = root / spec["id"] / spec["commit"]
    return {"id": spec["id"], "repository": spec["repository"], "commit": spec["commit"],
            "license": spec["license"], "entrypoints": spec["entrypoints"],
            "source_scope": "selected_paths" if spec.get("source_paths") else "complete_tree",
            "source_paths": spec.get("source_paths"),
            "present": False, "complete": False, "state": "absent", "installed": False,
            "execution_status": "unknown", "native_execution": "not_observed", "adapted_execution": "not_observed",
            "source_path": str(destination / "source"), "receipt_path": str(destination / "receipt.json")}


def _inspect(spec: dict, root: Path) -> dict:
    record = _base(spec, root)
    destination = Path(record["receipt_path"]).parent
    _checked(destination)
    if not destination.exists():
        return record
    record.update(present=True, state="incomplete")
    try:
        for path in destination.rglob("*"):
            _checked(path)
            if not path.is_file() and not path.is_dir():
                raise ValueError("Special filesystem objects are refused")
        receipt = json.loads((destination / "receipt.json").read_text(encoding="utf-8"))
        metadata_path = destination / "tree.json"
        if _sha(metadata_path) != receipt["metadata_sha256"]:
            raise ValueError("Tree metadata integrity mismatch")
        files = _tree(json.loads(metadata_path.read_text(encoding="utf-8")), spec)
        if receipt["commit"] != spec["commit"] or receipt["repository"] != spec["repository"]:
            raise ValueError("Cache provenance does not match the lock")
        if receipt.get("source_paths") != spec.get("source_paths"):
            raise ValueError("Cache source selection differs from the lock")
        inventory = receipt["inventory"]
        if not isinstance(inventory, list) or {i["path"] for i in inventory} != set(files) or len(inventory) != len(files):
            raise ValueError("Receipt inventory does not match the complete pinned tree")
        source = destination / "source"
        actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
        if actual != set(files):
            raise ValueError("Source cache has missing or unexpected files")
        for item in inventory:
            name = _relative(item["path"])
            path = source / name
            content = path.read_bytes()
            git_sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            if git_sha != files[name]["sha"] or len(content) != files[name]["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError("Cached source integrity mismatch: " + name)
        record.update(complete=True, state="complete", file_count=len(files),
                      receipt_sha256=_sha(destination / "receipt.json"), licenses=receipt["licenses"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record.update(state="corrupt", error=str(exc)[:400])
    return record


def status(cache: str | Path | None = None) -> dict:
    """Read and rehash cache data without fetching or installing anything."""
    root = _cache_root(cache)
    families = [_inspect(spec, root) for spec in _families()]
    return {"schema_version": 1, "status": "COMPLETE" if families and all(f["complete"] for f in families) else "PARTIAL", "cache": str(root), "families": families}


def _fetch_one(spec: dict, root: Path) -> dict:
    current = _inspect(spec, root)
    if current["complete"]:
        return current
    if current["present"]:
        current["error"] = "Existing cache is incomplete or modified; choose a fresh cache"
        return current
    stage = None
    try:
        repository, commit = spec["repository"], spec["commit"]
        metadata_url = f"https://api.github.com/repos/{repository}/git/trees/{commit}?recursive=1"
        archive_url = f"https://codeload.github.com/{repository}/tar.gz/{commit}"
        metadata_bytes = _download(metadata_url, MAX_METADATA_BYTES)
        metadata = json.loads(metadata_bytes)
        files = _tree(metadata, spec)
        selection = spec.get("source_paths")
        archive_bytes = None if selection else _download(archive_url, MAX_DOWNLOAD_BYTES)
        root.mkdir(parents=True, exist_ok=True)
        _checked(root)
        stage = Path(tempfile.mkdtemp(prefix="." + spec["id"] + "-", dir=root))
        source = stage / "source"
        source.mkdir(mode=0o700)
        expected_prefix = repository.split("/")[1] + "-" + commit
        seen = set()
        total = 0
        inventory = []
        blob_sources = []
        if selection:
            for relative, entry in sorted(files.items()):
                url = f"https://api.github.com/repos/{repository}/git/blobs/{entry['sha']}"
                blob = json.loads(_download(url, min(MAX_DOWNLOAD_BYTES, entry['size'] * 2 + 16384)))
                if (blob.get("encoding") != "base64" or blob.get("sha") != entry["sha"] or
                        blob.get("size") != entry["size"] or not isinstance(blob.get("content"), str)):
                    raise ValueError("Selected blob metadata differs from the pinned tree")
                content = base64.b64decode(blob["content"].replace("\n", "").replace("\r", ""), validate=True)
                git_sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                if len(content) != entry["size"] or git_sha != entry["sha"]:
                    raise ValueError("Selected blob differs from the pinned tree")
                output = source / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as target:
                    target.write(content)
                output.chmod(0o600)
                seen.add(relative)
                inventory.append({"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                                  "git_blob_sha1": git_sha, "git_mode": entry["mode"], "transport_transform": None})
                blob_sources.append({"path": relative, "url": url})
        else:
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
                for member in archive:
                    raw = member.name.rstrip("/")
                    name = _relative(raw)
                    parts = PurePosixPath(name).parts
                    if parts[0] != expected_prefix:
                        raise ValueError("Unexpected archive root or pinned revision")
                    if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                        raise ValueError("Archive links and special files are refused")
                    if member.isdir():
                        continue
                    relative = "/".join(parts[1:])
                    _relative(relative)
                    if relative not in files or relative in seen:
                        raise ValueError("Archive has unexpected or duplicate files")
                    if member.size > MAX_FILE_BYTES:
                        raise ValueError("Archive file exceeds the byte budget: " + relative)
                    total += member.size
                    if total > MAX_EXPANDED_BYTES or len(seen) >= MAX_FILES:
                        raise ValueError("Archive exceeds extraction budgets")
                    stream = archive.extractfile(member)
                    content = stream.read(MAX_FILE_BYTES + 1) if stream else b""
                    git_sha = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
                    transform = None
                    if len(content) != member.size:
                        raise ValueError("Archive file is truncated: " + relative)
                    if git_sha != files[relative]["sha"]:
                        canonical = content.replace(b"\r\n", b"\n")
                        canonical_sha = hashlib.sha1(f"blob {len(canonical)}\0".encode() + canonical).hexdigest()
                        if canonical_sha == files[relative]["sha"] and len(canonical) == files[relative]["size"]:
                            content, git_sha = canonical, canonical_sha
                            transform = "crlf_to_exact_git_blob"
                    if len(content) != files[relative]["size"] or git_sha != files[relative]["sha"]:
                        raise ValueError("Archive blob differs from pinned Git metadata")
                    output = source / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with output.open("xb") as target:
                        target.write(content)
                    output.chmod(0o600)  # Preserve source mode in inventory, not executable permission.
                    seen.add(relative)
                    inventory.append({"path": relative, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "git_blob_sha1": git_sha, "git_mode": files[relative]["mode"], "transport_transform": transform})
        if seen != set(files):
            raise ValueError("Archive is missing files from the complete pinned tree")
        notices = [i for i in inventory if re.match(r"(?i)^(license|licence|notice|copying)([._-]|$)", PurePosixPath(i["path"]).name)]
        receipt = {"schema_version": 1, "family": spec["id"], "repository": repository, "commit": commit,
                   "fetched_at": datetime.now(timezone.utc).isoformat(), "metadata_url": metadata_url,
                   "archive_url": None if selection else archive_url,
                   "archive_sha256": None if selection else hashlib.sha256(archive_bytes).hexdigest(),
                   "source_paths": selection, "blob_sources": blob_sources,
                   "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
                   "inventory": sorted(inventory, key=lambda i: i["path"]), "licenses": notices,
                   "execution_status": "unknown", "native_execution": "not_observed", "adapted_execution": "not_observed", "installed": False}
        (stage / "tree.json").write_bytes(metadata_bytes)
        (stage / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        destination = Path(current["receipt_path"]).parent
        destination.parent.mkdir(parents=True, exist_ok=True)
        _checked(destination)
        if destination.exists():
            raise ValueError("Cache destination appeared during fetch; refusing overwrite")
        stage.rename(destination)
        stage = None
        return _inspect(spec, root)
    except Exception as exc:
        current.update(state="unavailable", error=str(exc)[:400], complete=False)
        return current
    finally:
        if stage is not None:
            shutil.rmtree(stage)


def fetch(family: str | None = None, cache: str | Path | None = None) -> dict:
    """Fetch one locked family, or all default families, as inert source data."""
    specs = _families()
    if family is not None and family not in {spec["id"] for spec in specs}:
        raise ValueError("Unknown locked upstream family: " + str(family))
    root = _cache_root(cache)
    selected = [s for s in specs if (s["id"] == family if family is not None else s.get("default", True))]
    families = [_fetch_one(spec, root) for spec in selected]
    return {"schema_version": 1, "status": "COMPLETE" if families and all(f["complete"] for f in families) else "PARTIAL", "cache": str(root), "families": families}
