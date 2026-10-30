"""Bounded, source-preserving public website discovery with a local browser.

No account login, form submission, paid API, or ownership inference is performed.
GET endpoints can themselves have side effects: this is a conservative browser
policy, not a server-side guarantee of HTTP semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import uuid

from urllib.parse import parse_qsl, unquote, urljoin, urlsplit, urlunsplit

DEFAULT_MAX_PAGES = 10
HARD_MAX_PAGES = 30
MAX_MENU_ACTIONS = 8
MAX_SCROLL_STEPS = 40
NAVIGATION_TIMEOUT_MS = 12000
SOCIAL_HOSTS = {
    "instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "tiktok.com", "pinterest.com", "threads.net",
    "threads.com", "bsky.app", "vimeo.com",
}
SENSITIVE_SEGMENTS = {
    ".env", ".git", ".ssh", ".aws", ".well-known%2f", "admin", "wp-admin",
    "login", "signin", "sign-in", "logout", "signout", "account", "checkout",
    "cart", "delete", "remove", "destroy", "send", "submit", "private",
    "secret", "secrets", "credentials", "oauth", "callback", "token", "wp-login", "auth",
}
SENSITIVE_QUERY = re.compile(r"(?:token|secret|password|passwd|auth|credential|api.?key|session|signature|^code$)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _url(value: str, *, allow_local: bool, resolve: bool = True) -> str:
    try:
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Control characters in URLs are excluded")
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("Only absolute HTTP(S) URLs are supported")
        if parts.username or parts.password:
            raise ValueError("Credentials in URLs are not allowed")
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
        decoded = parts.path
        for _ in range(3):
            decoded = unquote(decoded)
        segments = [s.lower() for s in decoded.replace("\\", "/").split("/") if s]
        if any(s in SENSITIVE_SEGMENTS or s.split(".")[0] in SENSITIVE_SEGMENTS or s.startswith(".env") for s in segments):
            raise ValueError("Sensitive or potentially mutating path is excluded")
        query = parse_qsl(parts.query)
        if any(SENSITIVE_QUERY.search(k) for k, _ in query):
            raise ValueError("Sensitive URL parameters are excluded")
        if any(k.lower() in {"action", "do", "cmd", "operation"} and v.lower() in SENSITIVE_SEGMENTS | {"create", "update", "save"} for k, v in query):
            raise ValueError("Potentially mutating query is excluded")
        literal = None
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            pass
        addresses = [literal] if literal else []
        if resolve and not literal:
            addresses = [ipaddress.ip_address(r[4][0]) for r in socket.getaddrinfo(host, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)]
        if host == "localhost" and not allow_local:
            raise ValueError("Local network access requires allow_local=True")
        for address in addresses:
            if not address.is_global and not (allow_local and address.is_loopback):
                raise ValueError("Non-public network address is excluded")
        authority = f"[{host}]" if ":" in host else host
        if port and not ((parts.scheme == "https" and port == 443) or (parts.scheme == "http" and port == 80)):
            authority += f":{port}"
        return urlunsplit((parts.scheme.lower(), authority, parts.path or "/", parts.query, ""))
    except (OSError, UnicodeError) as exc:
        raise ValueError("URL host could not be safely resolved") from exc


def _origin(url: str) -> tuple:
    p = urlsplit(url)
    return p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80)


def _social(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS)


def _host_rule(url: str, allow_local: bool) -> str | None:
    """Pin a validated hostname to one validated address in Chromium's resolver."""
    host = urlsplit(url).hostname
    try:
        ipaddress.ip_address(host)
        return None  # IP literals do not perform a second DNS lookup in Chrome.
    except ValueError:
        pass
    addresses = {r[4][0] for r in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
    if not addresses:
        raise ValueError("No address available for browser hostname pinning")
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global and not (allow_local and address.is_loopback):
            raise ValueError("Hostname changed to a non-public address")
    chosen = sorted(addresses, key=lambda a: (ipaddress.ip_address(a).version, a))[0]
    if ":" in chosen:
        chosen = f"[{chosen}]"
    return f"MAP {host} {chosen}"


def _output_directory(value: str | Path) -> Path:
    path = Path(value).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Output directory and ancestors must not be symbolic links")
    resolved = path.resolve()
    package = Path(__file__).resolve().parent
    protected = {package}
    protected.update(parent for parent in package.parents
                     if (parent / '.git').exists() or (parent / 'SKILL.md').is_file())
    if any(resolved == boundary or boundary in resolved.parents for boundary in protected):
        raise ValueError('Collected evidence must remain outside the checkout, skill and runtime package')
    path.mkdir(parents=True, exist_ok=True)
    if (path / "discovery.json").exists():
        raise ValueError("Use a fresh output directory; existing discovery evidence is immutable")
    return path


def _artifact(root: Path, path: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def write_proof(root, stem, kind, content, storage):
    """Publish exact UTF-8 bytes; only TXT/HTML may share a blob."""
    from .state import _no_symlinks
    from .telemetry import counter
    if kind not in ('txt','html') or storage not in ('expanded','content_addressed') or not re.fullmatch('[A-Za-z0-9_-]+',stem):
        raise ValueError('Invalid proof publication')
    raw=content.encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
    folder=_no_symlinks(Path(root)/'sources'/('blobs' if storage=='content_addressed' else ''))
    folder.mkdir(exist_ok=True)
    target=folder/((digest if storage=='content_addressed' else stem)+'.'+kind)
    _no_symlinks(target)
    temporary=folder/('.publish-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream: stream.write(raw)
        try:
            os.link(temporary,target,follow_symlinks=False)
            counter('evidence.write',bytes=len(raw),files=1)
        except FileExistsError:
            _no_symlinks(target)
            if not target.is_file() or target.stat().st_size!=len(raw) or _artifact(Path(root),target)['sha256']!=digest:
                raise ValueError('Existing proof integrity mismatch')
    finally:
        temporary.unlink(missing_ok=True)
    return target


SNAPSHOT_JS = r"""() => {
  const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
  const links = [...document.querySelectorAll('a[href]')].filter(visible).map(e => ({url:e.href,text:e.innerText.slice(0,300)}));
  const assets = [...document.querySelectorAll('img,video,source,link[rel~="icon"],meta[property="og:image"]')].map(e => ({url:e.currentSrc || e.src || e.href || e.content || '',kind:e.tagName.toLowerCase(),alt:e.alt || ''}));
  const backgrounds = [...document.querySelectorAll('body *')].filter(visible).slice(0,2000).flatMap(e => [...getComputedStyle(e).backgroundImage.matchAll(/url\(["']?([^"')]+)["']?\)/g)].map(m => ({url:new URL(m[1],location.href).href,kind:'css_background',alt:''})));
  const jsonld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(e => e.textContent);
  return {title:document.title,text:document.body?.innerText || '',links,assets:assets.concat(backgrounds),jsonld,scroll_y:scrollY,height:document.documentElement.scrollHeight,viewport_height:innerHeight,visible_images:[...document.images].filter(e=>{let r=e.getBoundingClientRect();return r.width&&r.height&&r.bottom>0&&r.top<innerHeight&&r.left<innerWidth&&r.right>0}).map(e=>({alt:e.alt||'',loaded:e.complete&&e.naturalWidth>0}))};
}"""


def _sync(coroutine_factory, async_name):
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine_factory())
    raise RuntimeError(f"An event loop is active; await {async_name} instead")


def collect(url: str, output_dir: str | Path, *, allow_local=False, max_pages=None,
            panel_scan='legacy', image_wait_policy='legacy', proof_storage='expanded', concurrency=1) -> dict:
    """Sync wrapper; unique URL budget, fresh desktop/mobile contexts, no nested loop."""
    return _sync(lambda: acollect(url, output_dir, allow_local=allow_local, max_pages=max_pages,
                panel_scan=panel_scan, image_wait_policy=image_wait_policy,
                proof_storage=proof_storage, concurrency=concurrency), 'acollect')


async def acollect(url: str, output_dir: str | Path, *, allow_local=False, max_pages=None,
                   panel_scan='legacy', image_wait_policy='legacy', proof_storage='expanded', concurrency=1) -> dict:
    """Native async public collector. Cancellation writes partial proof, then propagates."""
    from .async_discovery import collect as run
    return await run(url, output_dir, allow_local=allow_local, max_pages=max_pages,
                     panel_scan=panel_scan, image_wait_policy=image_wait_policy,
                     proof_storage=proof_storage, concurrency=concurrency)


def continue_collect(prior_report: str | Path, output_dir: str | Path, *, allow_local=False, max_pages=None,
                     panel_scan='legacy', image_wait_policy='legacy', proof_storage='expanded', concurrency=1) -> dict:
    """Sync continuation wrapper. Prior proofs are validated before any DNS/network."""
    return _sync(lambda: acontinue_collect(prior_report, output_dir, allow_local=allow_local, max_pages=max_pages,
                 panel_scan=panel_scan, image_wait_policy=image_wait_policy,
                 proof_storage=proof_storage, concurrency=concurrency), 'acontinue_collect')


async def acontinue_collect(prior_report: str | Path, output_dir: str | Path, *, allow_local=False, max_pages=None,
                           panel_scan='legacy', image_wait_policy='legacy', proof_storage='expanded', concurrency=1) -> dict:
    from .async_discovery import collect as run
    initial, inputs = _continuation_inputs(prior_report, allow_local=allow_local)
    return await run(initial, output_dir, allow_local=allow_local, max_pages=max_pages,
                     panel_scan=panel_scan, image_wait_policy=image_wait_policy,
                     proof_storage=proof_storage, concurrency=concurrency, **inputs)


def _continuation_inputs(prior_report, *, allow_local):
    path = Path(prior_report).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("Prior report must be a regular file without symbolic links")
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Prior report exceeds the continuation byte budget")
    raw = path.read_bytes()
    try:
        prior = json.loads(raw)
        if prior.get("schema_version") not in {"1.0", "2.0"}:
            raise ValueError("Unsupported discovery report")
        source_hashes = [];descriptors={};verified={}
        for source in prior["sources"]:
            for artifact in source["artifacts"]:
                name = artifact["path"]
                if not isinstance(name, str) or "\\" in name or ":" in name or "\0" in name:
                    raise ValueError("Unsafe previous artifact path")
                relative = PurePosixPath(name)
                if relative.is_absolute() or any(part in {"", ".", ".."} for part in name.split("/")):
                    raise ValueError("Previous artifact escapes its report directory")
                if name in descriptors and artifact!=descriptors[name]:
                    raise ValueError('Contradictory previous proof descriptor')
                descriptors[name]=dict(artifact)
                proof = path.parent / name
                if any(p.is_symlink() for p in (proof, *proof.parents)) or not proof.is_file():
                    raise ValueError("Previous proof is missing or traverses a symbolic link")
                if name not in verified:
                    digest = hashlib.sha256()
                    with proof.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
                    verified[name]=digest.hexdigest()
                if verified[name] != artifact["sha256"] or proof.stat().st_size != artifact["bytes"]:
                    raise ValueError("Previous proof integrity mismatch")
                source_hashes.append({"source_id": source["id"], "path": name, "sha256": verified[name]})
        initial = _url(prior["input_url"], allow_local=allow_local, resolve=False)
        coverage = prior["coverage"]
        seen = coverage.get("seen_urls", coverage["attempted_urls"])
        frontier = coverage.get("frontier", coverage["omitted_urls"])
        known = coverage["discovered_urls"]
        previous_captured = coverage.get("cumulative_captured_urls", coverage.get("captured_urls", []))
        for values in (seen, frontier, known, previous_captured):
            if not isinstance(values, list):
                raise ValueError("Invalid continuation URL inventory")
            for value in values:
                if _url(value, allow_local=allow_local, resolve=False) != value or _origin(value) != _origin(initial):
                    raise ValueError("Continuation URLs must be normalized and share the original origin")
        pending = coverage.get("pending_states", [])
        for item in pending:
            if (not isinstance(item, dict) or item.get("viewport") not in {"desktop", "mobile"}
                    or _url(item.get("url", ""), allow_local=allow_local, resolve=False) != item["url"]
                    or _origin(item["url"]) != _origin(initial)):
                raise ValueError("Invalid pending navigation obligation")
            if item.get("attempts", 1) >= 2:
                raise ValueError("Pending state retry budget exhausted; use an evidenced host supplement or checkpoint")
        ancestors = prior.get("continuation", {}).get("ancestor_report_hashes", [])
        if not isinstance(ancestors, list) or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in ancestors):
            raise ValueError("Invalid continuation hash lineage")
        previous_sha = hashlib.sha256(raw).hexdigest()
        context = {"previous_report_sha256": previous_sha, "previous_source_hashes": source_hashes,
                   "ancestor_report_hashes": [*ancestors, previous_sha]}
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid or incomplete previous discovery proof") from exc
    return initial, dict(seeds=frontier, seen_urls=seen, known_urls=known, continuation=context,
                         previous_captured=previous_captured, pending_states=pending)
