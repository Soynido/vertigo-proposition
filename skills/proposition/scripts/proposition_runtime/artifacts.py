"""Passive local PDF export and byte-specific mechanical inspection.

A mechanical PASS is never a creative, factual or diffusion approval.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import zipfile
from urllib.parse import unquote, urlsplit


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root: Path, relative: str) -> Path:
    path = (root / unquote(relative)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Resource escapes source root")
    if not path.is_file():
        raise ValueError(f"Missing local resource: {relative}")
    return path


class PassiveHTML(HTMLParser):
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.styles = False
        self.css = []
        self.assets = set()

    def resource(self, value: str) -> None:
        if value.startswith("data:"):
            if not value.startswith(("data:image/", "data:font/", "data:application/font", "data:application/x-font")):
                raise ValueError("Unsupported data resource")
            return
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            raise ValueError("External resources are not allowed in a passive export")
        if not parsed.path:
            return
        path = inside(self.root, parsed.path)
        self.assets.add(path)
        if path.suffix.lower() == ".css":
            self.check_css(path.read_text(), path.parent)
        elif path.suffix.lower() == ".svg":
            nested = PassiveHTML(path.parent)
            nested.feed(path.read_text())

    def check_css(self, css: str, base: Path | None = None) -> None:
        if re.search(r"@import|expression\s*\(|javascript:", css, flags=re.I):
            raise ValueError("External or active CSS import is not allowed")
        for raw in re.findall(r"url\(\s*['\"]?([^'\")]+)", css, flags=re.I):
            if base is not None and base != self.root and not urlsplit(raw).scheme and not raw.startswith("#"):
                resolved = inside(base, raw)
                if not resolved.is_relative_to(self.root):
                    raise ValueError("CSS resource escapes source root")
                self.assets.add(resolved)
            else:
                self.resource(raw)

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "iframe", "object", "embed", "form", "input", "textarea", "select", "video", "audio", "foreignobject", "base"}:
            raise ValueError(f"Refusing active HTML element: {tag}")
        self.styles = tag == "style" or self.styles
        for key, value in attrs:
            if key.lower().startswith("on") or key == "srcdoc":
                raise ValueError("Refusing active HTML attribute")
            if value is None:
                continue
            if re.search(r"^\s*(javascript|vbscript):", value, re.I):
                raise ValueError("Refusing active URL")
            if key == "style":
                self.check_css(value)
            if key in {"src", "poster", "xlink:href"} or (key == "href" and tag != "a"):
                self.resource(value)
            if key == "srcset":
                raise ValueError("Use one explicit local image per placement for PDF export")

    def handle_endtag(self, tag):
        if tag == "style":
            self.styles = False

    def handle_data(self, data):
        if self.styles:
            self.check_css(data)


def export_pdf(source: Path, output: Path, *, audience: str = "client") -> dict:
    from playwright.sync_api import sync_playwright
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file():
        raise ValueError("Source HTML is missing")
    checker = PassiveHTML(source.parent)
    checker.feed(source.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            channel = os.environ.get('PROPOSITION_BROWSER_CHANNEL', 'chrome')
            browser = p.chromium.launch(headless=True, **({'channel': channel} if channel != 'chromium' else {}))
        except Exception:
            browser = p.chromium.launch(headless=True)
        context = browser.new_context(java_script_enabled=False, service_workers="block")
        def route(request_route):
            parsed = urlsplit(request_route.request.url)
            if parsed.scheme == "file":
                target = Path(unquote(parsed.path)).resolve()
                if target == source or target in checker.assets:
                    return request_route.continue_()
            if parsed.scheme == "data":
                return request_route.continue_()
            return request_route.abort()
        context.route("**/*", route)
        page = context.new_page()
        try:
            page.goto(source.as_uri(), wait_until="load", timeout=30000)
            page.evaluate("() => document.fonts.ready")
            broken = page.locator("img").evaluate_all("images => images.filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute('src'))")
            if broken:
                raise ValueError("Some source images did not load")
            page.pdf(path=str(output), print_background=True, prefer_css_page_size=True, tagged=True)
        finally:
            context.close()
            browser.close()
    from pypdf import PdfReader
    return {"path": str(output), "sha256": sha256(output), "source_sha256": sha256(source), "page_count": len(PdfReader(output).pages), "audience": audience, "scope": "export_only"}


def inspect_pdf(pdf: Path, output_dir: Path, *, audience: str = "client", max_pages: int | None = None) -> dict:
    from pypdf import PdfReader
    import pypdfium2 as pdfium
    pdf, output_dir = Path(pdf).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(pdf)
    issues, pages, texts = [], [], []
    if max_pages is not None and (type(max_pages) is not int or max_pages < 1):
        raise ValueError("max_pages must be a positive integer or None")
    if audience == "client" and max_pages is not None and len(reader.pages) > max_pages:
        issues.append({"code": "client_page_limit", "detail": f"Client document exceeds the configured {max_pages} pages"})
    if not reader.pages:
        issues.append({"code": "empty_document"})
    # Actions may be attached to pages, annotations or chained dictionaries,
    # not only the catalog. Inspect the actual reachable object graph.
    stack, visited, active_paths = [(reader.trailer['/Root'], 'catalog')], set(), []
    forbidden_keys = {'/OpenAction','/AA','/AcroForm','/JavaScript','/JS','/EmbeddedFiles','/XFA','/RichMediaContent'}
    forbidden_actions = {'/JavaScript','/Launch','/SubmitForm','/ImportData','/GoToR','/GoToE',
                         '/Rendition','/Movie','/Sound','/RichMediaExecute','/ResetForm'}
    while stack:
        node, location = stack.pop()
        if hasattr(node, 'get_object'):
            node = node.get_object()
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, dict):
            if any(key in node for key in forbidden_keys) or node.get('/S') in forbidden_actions:
                active_paths.append(location)
            if '/URI' in node and urlsplit(str(node['/URI'])).scheme.lower() not in {'http','https','mailto','tel'}:
                active_paths.append(location + '/URI')
            stack.extend((value,location+'/'+str(key)) for key,value in node.items())
        elif isinstance(node, (list,tuple)):
            stack.extend((value,location+f'[{i}]') for i,value in enumerate(node))
    if active_paths:
        issues.append({'code':'active_pdf','locations':sorted(set(active_paths))})
    rendered = pdfium.PdfDocument(str(pdf))
    try:
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            texts.append(text)
            if not text.strip():
                issues.append({"code": "no_extractable_text", "page": index + 1})
            image_name = f"page-{index + 1:03}.png"
            render_page = rendered[index]
            bitmap = render_page.render(scale=1.5)
            bitmap.to_pil().save(output_dir / image_name)
            bitmap.close()
            render_page.close()
            fonts = list((page.get("/Resources", {}).get("/Font", {}) or {}).keys())
            pages.append({"number": index + 1, "image": image_name, "image_sha256": sha256(output_dir / image_name), "text_characters": len(text), "width": float(page.mediabox.width), "height": float(page.mediabox.height), "font_resources": fonts})
    finally:
        rendered.close()
    result = {"status": "FAIL" if issues else "PASS", "scope": "mechanical_only", "visual_review": "NOT_RUN", "path": str(pdf), "sha256": sha256(pdf), "page_count": len(pages), "pages": pages, "text": "\n\n".join(texts), "issues": issues}
    (output_dir / "inspection.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def package_client(root: Path, output: Path, files: list[str]) -> dict:
    root, output = Path(root).resolve(), Path(output).resolve()
    resolved = [(relative, inside(root, relative)) for relative in files]
    if len({p for _, p in resolved}) != len(resolved):
        raise ValueError("Duplicate file in client package")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, path in resolved:
            archive.write(path, Path(relative).as_posix())
    return {"path": str(output), "sha256": sha256(output), "files": [{"path": relative, "sha256": sha256(path)} for relative, path in resolved]}
