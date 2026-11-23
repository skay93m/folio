"""Unified static + headless Playwright verifier for Folio targets."""

from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import http.server
import re
import socketserver
import threading
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

from folio.catalogue import CatalogueValidationError, validate_catalogue

STATIC_JS_DIR = Path(__file__).resolve().parent / "static" / "folio" / "js"

_SERIF_CONTAINER_CLASSES = frozenset({"article", "sk-section-block", "sk-section-list"})
_SERIF_TEXT_TAGS = frozenset({"p", "li", "blockquote"})
_FAUX_TAGS = frozenset({"em", "strong", "i", "b"})
_TOKEN_OVERRIDE_RE = re.compile(r"--(?:sk|bs)-[a-z0-9-]+\s*:", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of running static and Playwright verification against a target."""

    passed: bool
    target: str
    checks: tuple[str, ...]
    errors: tuple[str, ...]


class _StaticHTMLScanner(HTMLParser):
    """Parse HTML to detect inline JS backticks, unapproved style overrides, and faux Serif tags."""

    def __init__(self, source_name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_name = source_name
        self.errors: list[str] = []
        self._stack: list[tuple[str, set[str]]] = []
        self._in_script = False
        self._in_style = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if tag_l in _FAUX_TAGS and self._inside_serif_prose():
            self.errors.append(
                f"{self.source_name}: forbidden faux-style tag <{tag_l}> inside Serif reading prose"
            )

        self._stack.append((tag_l, classes))
        if tag_l == "script":
            self._in_script = True
            self._buf = []
        elif tag_l == "style":
            self._in_style = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l == "script" and self._in_script:
            script_text = "".join(self._buf)
            if "`" in script_text:
                self.errors.append(
                    f"{self.source_name}: unescaped JS template-literal backtick found in inline <script>"
                )
            self._in_script = False
            self._buf = []
        elif tag_l == "style" and self._in_style:
            style_text = "".join(self._buf)
            if _TOKEN_OVERRIDE_RE.search(style_text):
                self.errors.append(
                    f"{self.source_name}: unapproved inline <style> token override detected"
                )
            self._in_style = False
            self._buf = []

        for idx in range(len(self._stack) - 1, -1, -1):
            if self._stack[idx][0] == tag_l:
                del self._stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_script or self._in_style:
            self._buf.append(data)

    def _inside_serif_prose(self) -> bool:
        in_serif_container = any(
            bool(classes & _SERIF_CONTAINER_CLASSES) for _, classes in self._stack
        )
        if not in_serif_container:
            return False
        return any(
            tag in _SERIF_TEXT_TAGS or "abstract" in classes or "sk-section-list" in classes
            for tag, classes in self._stack
        )


def scan_html_static(html: str, source_name: str) -> list[str]:
    """Run static HTML checks on a single document string."""
    scanner = _StaticHTMLScanner(source_name)
    scanner.feed(html)
    scanner.close()
    return scanner.errors


def scan_package_js_static() -> list[str]:
    """Ensure packaged Folio JS files contain zero template-literal backticks."""
    errors: list[str] = []
    if not STATIC_JS_DIR.exists():
        return errors
    for js_file in sorted(STATIC_JS_DIR.glob("*.js")):
        content = js_file.read_text(encoding="utf-8")
        if "`" in content:
            errors.append(
                f"{js_file.name}: unescaped JS template-literal backtick found"
            )
    return errors


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def _serve_directory(directory: Path) -> tuple[_ThreadingServer, str]:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = _ThreadingServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def _fetch_url_html(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _discover_http_targets(base_url: str) -> list[str]:
    cleaned = base_url.rstrip("/")
    if "?" in base_url or cleaned.endswith(".html"):
        return [base_url]
    # Check if base_url serves the Folio gallery + catalogue
    try:
        probe = _fetch_url_html(f"{cleaned}/catalogue/")
        if "SK Design System" in probe:
            return [
                f"{cleaned}/?page=launchpad",
                f"{cleaned}/?page=homepage",
                f"{cleaned}/?page=reading",
                f"{cleaned}/?page=dashboard",
                f"{cleaned}/?page=search",
                f"{cleaned}/?page=work",
                f"{cleaned}/?page=queue",
                f"{cleaned}/catalogue/",
                f"{cleaned}/catalogue/primary-action/",
            ]
    except Exception:
        pass
    return [base_url]


def _run_playwright_checks(urls: Iterable[str]) -> tuple[list[str], list[str]]:
    from playwright.sync_api import sync_playwright

    checks: list[str] = []
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for url in urls:
                for width, height, label in ((1280, 800, "desktop"), (375, 812, "mobile-375"), (390, 844, "mobile-390")):
                    page.set_viewport_size({"width": width, "height": height})
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_function("() => document.fonts.ready")
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth > window.innerWidth"
                    )
                    if overflow:
                        errors.append(f"{url} ({label}): horizontal overflow detected")
                    else:
                        checks.append(f"no-overflow:{label}:{url}")

                page.set_viewport_size({"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle")
                page.wait_for_function("() => document.fonts.ready")

                has_sk_tokens = page.evaluate(
                    "() => Boolean(getComputedStyle(document.documentElement).getPropertyValue('--sk-paper').trim())"
                )
                if has_sk_tokens:
                    theme_val = page.evaluate("() => document.documentElement.dataset.bsTheme")
                    bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
                    if theme_val == "light" and bg != "rgb(247, 246, 242)":
                        errors.append(f"{url}: expected Light #F7F6F2 canvas, got {bg}")
                    elif theme_val == "dark" and bg != "rgb(23, 25, 28)":
                        errors.append(f"{url}: expected D1 Dark #17191C canvas, got {bg}")

                    body_font = page.evaluate("() => getComputedStyle(document.body).fontFamily")
                    if "IBM Plex Sans" not in body_font:
                        errors.append(f"{url}: expected IBM Plex Sans on body, got {body_font}")

                    serif_font = page.evaluate(
                        """() => {
                            const el = document.querySelector('.article p, .sk-section-block p');
                            return el ? getComputedStyle(el).fontFamily : '';
                        }"""
                    )
                    if serif_font and "IBM Plex Serif" not in serif_font:
                        errors.append(f"{url}: expected IBM Plex Serif on reading prose, got {serif_font}")

                    mono_font = page.evaluate(
                        """() => {
                            const el = document.querySelector('code, .eyebrow, .sk-meta-line');
                            return el ? getComputedStyle(el).fontFamily : '';
                        }"""
                    )
                    if mono_font and "IBM Plex Mono" not in mono_font:
                        errors.append(f"{url}: expected IBM Plex Mono on metadata/code, got {mono_font}")

                    footer_pos = page.evaluate(
                        """() => {
                            const f = document.querySelector('.sk-site-footer');
                            return f ? getComputedStyle(f).position : '';
                        }"""
                    )
                    if footer_pos and footer_pos != "static":
                        errors.append(f"{url}: expected static footer, got {footer_pos}")

                    # Verify D1 Dark theme via toggle when present
                    if page.locator("#theme-toggle").count() > 0:
                        page.click("#theme-toggle")
                        dark_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
                        if dark_bg != "rgb(23, 25, 28)":
                            errors.append(f"{url}: expected D1 Dark #17191C after toggle, got {dark_bg}")
                        page.click("#theme-toggle")

                    # Verify keyboard focus visibility via real Tab navigation
                    page.keyboard.press("Tab")
                    focus_ok = page.evaluate(
                        """() => {
                            const el = document.activeElement;
                            if (!el || el === document.body) return true;
                            const st = getComputedStyle(el);
                            return st.outlineStyle !== 'none' || st.boxShadow !== 'none';
                        }"""
                    )
                    if not focus_ok:
                        errors.append(f"{url}: keyboard focus outline not visible")

                    # Verify @media print across all 3 print modes
                    for mode in ("colour", "greyscale", "black-white"):
                        page.evaluate(f"() => {{ document.documentElement.dataset.printMode = '{mode}'; }}")
                        page.emulate_media(media="print")
                        print_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
                        if print_bg != "rgb(255, 255, 255)":
                            errors.append(f"{url} (print {mode}): expected white background, got {print_bg}")
                        header_hidden = page.evaluate(
                            """() => {
                                const h = document.querySelector('.site-header');
                                return !h || getComputedStyle(h).display === 'none';
                            }"""
                        )
                        if not header_hidden:
                            errors.append(f"{url} (print {mode}): .site-header must be hidden in print")
                    page.emulate_media(media="screen")
                    checks.append(f"sk-tokens-f3-print:{url}")
        finally:
            browser.close()

    return checks, errors


def verify_target(
    target: str | Path,
    *,
    run_playwright: bool = True,
    check_catalogue: bool = True,
) -> VerificationResult:
    """Run static source/HTML checks and optional headless Playwright verification."""
    checks: list[str] = []
    errors: list[str] = []

    if check_catalogue:
        try:
            validate_catalogue()
            checks.append("catalogue:valid")
        except CatalogueValidationError as exc:
            errors.append(f"catalogue validation failed: {exc}")

    js_errors = scan_package_js_static()
    if js_errors:
        errors.extend(js_errors)
    else:
        checks.append("package-js:no-backticks")

    target_str = str(target)
    playwright_urls: list[str] = []
    server: _ThreadingServer | None = None

    try:
        if target_str.startswith(("http://", "https://")):
            urls = _discover_http_targets(target_str)
            for url in urls:
                html = _fetch_url_html(url)
                errors.extend(scan_html_static(html, url))
            checks.append(f"static-html:{len(urls)}")
            playwright_urls = urls
        else:
            path = Path(target_str).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Verification target does not exist: {path}")
            if path.is_file():
                html = path.read_text(encoding="utf-8")
                errors.extend(scan_html_static(html, path.name))
                checks.append(f"static-html:{path.name}")
                if run_playwright:
                    server, base = _serve_directory(path.parent)
                    playwright_urls = [f"{base}/{path.name}"]
            else:
                html_files = sorted(path.rglob("*.html"))
                if not html_files:
                    errors.append(f"No HTML files found in {path}")
                for html_file in html_files:
                    rel = html_file.relative_to(path).as_posix()
                    errors.extend(scan_html_static(html_file.read_text(encoding="utf-8"), rel))
                checks.append(f"static-html:{len(html_files)}")
                if run_playwright and html_files:
                    server, base = _serve_directory(path)
                    playwright_urls = [
                        f"{base}/{f.relative_to(path).as_posix()}" for f in html_files
                    ]

        if run_playwright and playwright_urls:
            try:
                asyncio.get_running_loop()
                has_loop = True
            except RuntimeError:
                has_loop = False
            if has_loop:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pw_checks, pw_errors = pool.submit(
                        _run_playwright_checks, playwright_urls
                    ).result()
            else:
                pw_checks, pw_errors = _run_playwright_checks(playwright_urls)
            checks.extend(pw_checks)
            errors.extend(pw_errors)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    return VerificationResult(
        passed=not errors,
        target=target_str,
        checks=tuple(checks),
        errors=tuple(errors),
    )
