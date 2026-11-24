"""Unified static + headless Playwright verifier for Folio targets."""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from folio.catalogue import CatalogueValidationError, validate_catalogue
from folio.server import _serve_directory, _ThreadingServer

STATIC_DIR = Path(__file__).resolve().parent / "static" / "folio"
STATIC_JS_DIR = STATIC_DIR / "js"
DEFAULT_TOKENS_CSS_PATH = STATIC_DIR / "css" / "sk-design-system.css"

_SERIF_CONTAINER_CLASSES = frozenset({"article", "sk-section-block", "sk-section-list"})
_SERIF_TEXT_TAGS = frozenset({"p", "li", "blockquote"})
_FAUX_TAGS = frozenset({"em", "strong", "i", "b"})
_ASSET_LINK_TAGS = frozenset({"link", "script", "img", "source", "video", "audio", "iframe", "embed", "object"})
_TOKEN_OVERRIDE_RE = re.compile(r"--(?:sk|bs)-[a-z0-9-]+\s*:", re.IGNORECASE)

_CONTRAST_JS = """() => {
  function parseColor(str) {
    const m = str && str.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);
    if (!m) return null;
    return {
      r: Number(m[1]),
      g: Number(m[2]),
      b: Number(m[3]),
      a: m[4] === undefined ? 1 : Number(m[4])
    };
  }
  function composite(fg, bg) {
    const a = fg.a;
    return {
      r: fg.r * a + bg.r * (1 - a),
      g: fg.g * a + bg.g * (1 - a),
      b: fg.b * a + bg.b * (1 - a),
      a: 1
    };
  }
  function resolveBg(el) {
    const layers = [];
    let cur = el;
    while (cur) {
      const c = parseColor(getComputedStyle(cur).backgroundColor);
      if (c && c.a > 0) {
        layers.push(c);
        if (c.a >= 0.999) break;
      }
      cur = cur.parentElement;
    }
    let acc = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = layers.length - 1; i >= 0; i--) {
      acc = composite(layers[i], acc);
    }
    return acc;
  }
  function relLum(c) {
    const chan = [c.r, c.g, c.b].map(v => {
      const s = v / 255;
      return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * chan[0] + 0.7152 * chan[1] + 0.0722 * chan[2];
  }
  function contrast(fg, bg) {
    const l1 = relLum(fg);
    const l2 = relLum(bg);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  const selector = ".status-success, .status-warning, .status-error, .status-info, .status-neutral, .btn-primary";
  const failures = [];
  let checked = 0;
  document.querySelectorAll(selector).forEach(el => {
    const st = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0 || st.visibility === "hidden" || st.display === "none") {
      return;
    }
    const bg = resolveBg(el);
    const rawFg = parseColor(st.color);
    if (!rawFg) return;
    const fg = rawFg.a < 1 ? composite(rawFg, bg) : rawFg;
    const ratio = contrast(fg, bg);
    checked += 1;
    if (ratio < 4.5) {
      failures.push({
        className: el.className,
        text: (el.textContent || "").trim().slice(0, 40),
        ratio: Number(ratio.toFixed(2)),
        fg: st.color,
        bg: "rgb(" + Math.round(bg.r) + ", " + Math.round(bg.g) + ", " + Math.round(bg.b) + ")"
      });
    }
  });
  return { checked, failures };
}"""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of running static and Playwright verification against a target."""

    passed: bool
    target: str
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def drifted(self) -> bool:
        return not self.passed


class _StaticHTMLScanner(HTMLParser):
    """Parse HTML to detect inline JS backticks, style overrides, faux Serif tags, and script refs."""

    def __init__(self, source_name: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source_name = source_name
        self.errors: list[str] = []
        self.script_srcs: list[str] = []
        self._stack: list[tuple[str, set[str]]] = []
        self._in_script = False
        self._in_style = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())

        if tag_l in _FAUX_TAGS and self._inside_serif_prose():
            self.errors.append(f"{self.source_name}: forbidden faux-style tag <{tag_l}> inside Serif reading prose")

        if tag_l in _ASSET_LINK_TAGS:
            for attr_name in ("href", "src", "data"):
                raw_val = (attr_map.get(attr_name) or "").strip()
                if raw_val.lower().startswith("file://"):
                    self.errors.append(
                        f"{self.source_name}: forbidden file:// asset link in <{tag_l} {attr_name}>: {raw_val}"
                    )

        inline_style = (attr_map.get("style") or "").lower()
        if "file://" in inline_style:
            self.errors.append(f"{self.source_name}: forbidden file:// asset link in inline style attribute")

        self._stack.append((tag_l, classes))
        if tag_l == "script":
            src = (attr_map.get("src") or "").strip()
            if src:
                self.script_srcs.append(src)
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
                self.errors.append(f"{self.source_name}: unapproved inline <style> token override detected")
            if "file://" in style_text.lower():
                self.errors.append(f"{self.source_name}: forbidden file:// asset link in inline <style>")
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
        in_serif_container = any(bool(classes & _SERIF_CONTAINER_CLASSES) for _, classes in self._stack)
        if not in_serif_container:
            return False
        return any(
            tag in _SERIF_TEXT_TAGS or "abstract" in classes or "sk-section-list" in classes
            for tag, classes in self._stack
        )


def _is_vendor_js(path_or_url: str) -> bool:
    parsed = urllib.parse.urlparse(path_or_url).path
    parts = [part.lower() for part in Path(parsed).parts if part]
    if "vendor" in parts:
        return True
    name = parts[-1] if parts else ""
    return name.startswith("bootstrap")


def _scan_js_text(content: str, source_name: str) -> list[str]:
    if "`" in content:
        return [f"{source_name}: unescaped JS template-literal backtick found"]
    return []


def _scan_html_and_collect_scripts(html: str, source_name: str) -> tuple[list[str], list[str]]:
    scanner = _StaticHTMLScanner(source_name)
    scanner.feed(html)
    scanner.close()
    return scanner.errors, scanner.script_srcs


def scan_html_static(html: str, source_name: str) -> list[str]:
    """Run static HTML checks on a single document string."""
    errors, _ = _scan_html_and_collect_scripts(html, source_name)
    return errors


def scan_package_js_static() -> list[str]:
    """Ensure packaged Folio JS files contain zero template-literal backticks."""
    errors: list[str] = []
    if not STATIC_JS_DIR.exists():
        return errors
    for js_file in sorted(STATIC_JS_DIR.glob("*.js")):
        errors.extend(_scan_js_text(js_file.read_text(encoding="utf-8"), js_file.name))
    return errors


def _scan_local_js_files(js_files: Iterable[Path], *, base_dir: Path | None = None) -> tuple[list[str], int]:
    errors: list[str] = []
    seen: set[Path] = set()
    for js_file in js_files:
        resolved = js_file.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        rel = (
            resolved.relative_to(base_dir.resolve()).as_posix()
            if base_dir and resolved.is_relative_to(base_dir.resolve())
            else resolved.name
        )
        if _is_vendor_js(rel):
            continue
        errors.extend(_scan_js_text(resolved.read_text(encoding="utf-8"), rel))
    return errors, len(seen)


def _resolve_local_script_paths(
    script_srcs: Iterable[str],
    html_dir: Path,
    root_dir: Path,
) -> list[Path]:
    resolved: list[Path] = []
    for src in script_srcs:
        if src.startswith(("http://", "https://", "//", "data:")):
            continue
        cleaned = src.split("#", 1)[0].split("?", 1)[0]
        if not cleaned.endswith(".js"):
            continue
        candidate = (root_dir / cleaned.lstrip("/")) if cleaned.startswith("/") else (html_dir / cleaned)
        if candidate.is_file():
            resolved.append(candidate)
    return resolved


def _fetch_url_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _discover_http_targets(base_url: str) -> list[str]:
    cleaned = base_url.rstrip("/")
    if "?" in base_url or cleaned.endswith(".html"):
        return [base_url]
    try:
        probe = _fetch_url_text(f"{cleaned}/catalogue/")
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


def _scan_http_targets(base_url: str) -> tuple[list[str], list[str], list[str]]:
    urls = _discover_http_targets(base_url)
    errors: list[str] = []
    js_urls: set[str] = set()
    base_netloc = urllib.parse.urlparse(base_url).netloc

    for url in urls:
        html = _fetch_url_text(url)
        html_errors, script_srcs = _scan_html_and_collect_scripts(html, url)
        errors.extend(html_errors)
        for src in script_srcs:
            abs_url = urllib.parse.urljoin(url, src)
            parsed = urllib.parse.urlparse(abs_url)
            if parsed.netloc == base_netloc and parsed.path.endswith(".js") and not _is_vendor_js(parsed.path):
                js_urls.add(abs_url)

    for js_url in sorted(js_urls):
        errors.extend(_scan_js_text(_fetch_url_text(js_url), js_url))

    checks = [f"static-html:{len(urls)}", f"external-js:{len(js_urls)}"]
    return urls, checks, errors


def _check_viewports_overflow(page: Any, url: str) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    errors: list[str] = []
    for width, height, label in ((1280, 800, "desktop"), (375, 812, "mobile-375"), (390, 844, "mobile-390")):
        page.set_viewport_size({"width": width, "height": height})
        overflow = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        if overflow:
            errors.append(f"{url} ({label}): horizontal overflow detected")
        else:
            checks.append(f"no-overflow:{label}:{url}")
    page.set_viewport_size({"width": 1280, "height": 800})
    return checks, errors


def _check_sk_tokens_and_fonts(page: Any, url: str) -> list[str]:
    errors: list[str] = []
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
    return errors


def _check_contrast_for_current_theme(page: Any, url: str, theme_label: str) -> list[str]:
    result = page.evaluate(_CONTRAST_JS)
    errors: list[str] = []
    for fail in result["failures"]:
        errors.append(
            f"{url} ({theme_label}): WCAG AA contrast {fail['ratio']}:1 < 4.5:1 on "
            f"{fail['className']!r} ({fail['text']!r}, fg={fail['fg']}, bg={fail['bg']})"
        )
    return errors


def _check_wcag_contrast_both_themes(page: Any, url: str) -> list[str]:
    errors: list[str] = []
    initial_theme = page.evaluate("() => document.documentElement.dataset.bsTheme || 'light'")
    opposite_theme = "dark" if initial_theme == "light" else "light"

    errors.extend(_check_contrast_for_current_theme(page, url, initial_theme))

    has_toggle = page.locator("#theme-toggle").count() > 0
    if has_toggle:
        page.click("#theme-toggle")
        toggled_bg = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
        expected_bg = "rgb(23, 25, 28)" if opposite_theme == "dark" else "rgb(247, 246, 242)"
        if toggled_bg != expected_bg:
            errors.append(f"{url}: expected {opposite_theme} canvas {expected_bg} after toggle, got {toggled_bg}")
    else:
        page.evaluate("(t) => { document.documentElement.dataset.bsTheme = t; }", opposite_theme)

    errors.extend(_check_contrast_for_current_theme(page, url, opposite_theme))

    if has_toggle:
        page.click("#theme-toggle")
    else:
        page.evaluate("(t) => { document.documentElement.dataset.bsTheme = t; }", initial_theme)
    return errors


def _check_keyboard_focus(page: Any, url: str) -> list[str]:
    page.evaluate("() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); }")
    reached_visible_control = False
    for _ in range(10):
        page.keyboard.press("Tab")
        info = page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body || el === document.documentElement) {
                    return { valid: false, reason: 'focus landed on body/document' };
                }
                const st = getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                const outlineOk = st.outlineStyle !== 'none' && parseFloat(st.outlineWidth || '0') > 0;
                const shadowOk = st.boxShadow !== 'none';
                const visible = rect.width > 0 && rect.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
                return {
                    valid: outlineOk || shadowOk,
                    visible: visible,
                    isSkip: el.classList.contains('skip'),
                    tag: el.tagName.toLowerCase(),
                    reason: (outlineOk || shadowOk) ? '' : 'keyboard focus outline not visible'
                };
            }"""
        )
        if not info["valid"]:
            return [f"{url}: {info['reason']} ({info.get('tag', 'body')})"]
        if info["visible"] and not info["isSkip"]:
            reached_visible_control = True
            break
    if not reached_visible_control:
        return [f"{url}: Tab navigation did not reach a visible interactive control"]
    return []


def _check_print_modes(page: Any, url: str) -> list[str]:
    errors: list[str] = []
    initial_print = page.evaluate("() => document.documentElement.dataset.printMode || 'colour'")
    for mode in ("colour", "greyscale", "black-white"):
        page.evaluate("(m) => { document.documentElement.dataset.printMode = m; }", mode)
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
    page.evaluate("(m) => { document.documentElement.dataset.printMode = m; }", initial_print)
    return errors


def _is_ignored_favicon(req_url: str) -> bool:
    return urllib.parse.urlparse(req_url).path == "/favicon.ico"


def _run_playwright_checks(urls: Iterable[str]) -> tuple[list[str], list[str]]:
    from playwright.sync_api import sync_playwright

    checks: list[str] = []
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for url in urls:
                failed_assets: list[str] = []
                parsed_target = urllib.parse.urlsplit(url)
                target_origin = (parsed_target.scheme, parsed_target.netloc)

                def on_request(
                    req: Any,
                    target_url: str = url,
                    origin: tuple[str, str] = target_origin,
                    out: list[str] = failed_assets,
                ) -> None:
                    req_url = req.url
                    if req_url.startswith(("http://", "https://")):
                        req_parsed = urllib.parse.urlsplit(req_url)
                        if (req_parsed.scheme, req_parsed.netloc) != origin:
                            out.append(
                                f"{target_url}: external network request forbidden (offline invariant): {req_url}"
                            )

                def on_request_failed(req: Any, target_url: str = url, out: list[str] = failed_assets) -> None:
                    if not _is_ignored_favicon(req.url):
                        out.append(f"{target_url}: failed asset request {req.url} ({req.failure or 'requestfailed'})")

                def on_response(resp: Any, target_url: str = url, out: list[str] = failed_assets) -> None:
                    if resp.status >= 400 and not _is_ignored_favicon(resp.url):
                        out.append(f"{target_url}: failed asset request {resp.url} (HTTP {resp.status})")

                page.on("request", on_request)
                page.on("requestfailed", on_request_failed)
                page.on("response", on_response)
                try:
                    page.set_viewport_size({"width": 1280, "height": 800})
                    page.goto(url, wait_until="load")
                    page.wait_for_function("() => document.fonts.ready")

                    mermaid_selector = ".mermaid, pre > code.language-mermaid"
                    mermaid_count = page.locator(mermaid_selector).count()
                    if mermaid_count > 0:
                        has_mermaid_runtime = page.evaluate("() => Boolean(window.mermaid)")
                        if not has_mermaid_runtime:
                            errors.append(
                                f"{url}: .mermaid diagram failed to render <svg> (window.mermaid unavailable)"
                            )
                        else:
                            try:
                                page.wait_for_function(
                                    "() => {"
                                    "  if (document.querySelector('pre > code.language-mermaid')) return false;"
                                    "  const nodes = Array.from(document.querySelectorAll('.mermaid'));"
                                    "  return nodes.length > 0 && nodes.every(el => Boolean(el.querySelector('svg')));"
                                    "}",
                                    timeout=5000,
                                )
                                checks.append(f"mermaid-svg:{mermaid_count}:{url}")
                            except Exception:
                                errors.append(f"{url}: .mermaid diagram failed to render <svg>")

                    stylesheet_count = page.evaluate("() => document.styleSheets.length")
                    if stylesheet_count == 0:
                        errors.append(f"{url}: stylesheetCount == 0 (no stylesheets loaded)")
                    else:
                        checks.append(f"stylesheets:{stylesheet_count}:{url}")

                    vp_checks, vp_errors = _check_viewports_overflow(page, url)
                    checks.extend(vp_checks)
                    errors.extend(vp_errors)

                    has_sk_tokens = page.evaluate(
                        "() => Boolean(getComputedStyle(document.documentElement).getPropertyValue('--sk-paper').trim())"
                    )
                    if has_sk_tokens:
                        errors.extend(_check_sk_tokens_and_fonts(page, url))
                        errors.extend(_check_wcag_contrast_both_themes(page, url))
                        errors.extend(_check_keyboard_focus(page, url))
                        errors.extend(_check_print_modes(page, url))
                        checks.append(f"sk-tokens-f3-contrast-focus-print:{url}")
                finally:
                    page.remove_listener("request", on_request)
                    page.remove_listener("requestfailed", on_request_failed)
                    page.remove_listener("response", on_response)

                errors.extend(failed_assets)
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
            urls, http_checks, http_errors = _scan_http_targets(target_str)
            checks.extend(http_checks)
            errors.extend(http_errors)
            playwright_urls = urls
        else:
            path = Path(target_str).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Verification target does not exist: {path}")
            if path.is_file():
                html = path.read_text(encoding="utf-8")
                html_errors, script_srcs = _scan_html_and_collect_scripts(html, path.name)
                errors.extend(html_errors)
                js_paths = _resolve_local_script_paths(script_srcs, path.parent, path.parent)
                ext_js_errors, ext_js_count = _scan_local_js_files(js_paths, base_dir=path.parent)
                errors.extend(ext_js_errors)
                checks.append(f"static-html:{path.name}")
                checks.append(f"external-js:{ext_js_count}")
                if run_playwright:
                    server, base = _serve_directory(path.parent)
                    playwright_urls = [f"{base}/{path.name}"]
            else:
                if (path / ".obsidian").is_dir():
                    from folio.obsidian import build_obsidian_theme, verify_obsidian_vault

                    theme = build_obsidian_theme(DEFAULT_TOKENS_CSS_PATH.read_text(encoding="utf-8"))
                    obs_res = verify_obsidian_vault(theme, path)
                    checks.extend(obs_res.checks)
                    errors.extend(obs_res.errors)
                else:
                    html_files = sorted(path.rglob("*.html"))
                    if not html_files:
                        errors.append(f"No HTML files found in {path}")
                    js_candidates: list[Path] = sorted(path.rglob("*.js"))
                    for html_file in html_files:
                        rel = html_file.relative_to(path).as_posix()
                        html_errors, script_srcs = _scan_html_and_collect_scripts(
                            html_file.read_text(encoding="utf-8"),
                            rel,
                        )
                        errors.extend(html_errors)
                        js_candidates.extend(_resolve_local_script_paths(script_srcs, html_file.parent, path))
                    ext_js_errors, ext_js_count = _scan_local_js_files(js_candidates, base_dir=path)
                    errors.extend(ext_js_errors)
                    checks.append(f"static-html:{len(html_files)}")
                    checks.append(f"external-js:{ext_js_count}")
                    if (path / "obsidian").is_dir():
                        from folio.obsidian import build_obsidian_theme

                        expected_theme = build_obsidian_theme(DEFAULT_TOKENS_CSS_PATH.read_text(encoding="utf-8"))
                        dist_css = path / "obsidian" / "theme.css"
                        dist_manifest = path / "obsidian" / "manifest.json"
                        if not dist_css.is_file() or dist_css.read_text(encoding="utf-8") != expected_theme.theme_css:
                            errors.append(f"obsidian/theme.css drift detected in {path / 'obsidian'}")
                        elif (
                            not dist_manifest.is_file()
                            or dist_manifest.read_text(encoding="utf-8") != expected_theme.manifest_json
                        ):
                            errors.append(f"obsidian/manifest.json drift detected in {path / 'obsidian'}")
                        else:
                            checks.append("obsidian-dist:valid")
                    if run_playwright and html_files:
                        server, base = _serve_directory(path)
                        playwright_urls = [f"{base}/{f.relative_to(path).as_posix()}" for f in html_files]

        if run_playwright and playwright_urls:
            try:
                asyncio.get_running_loop()
                has_loop = True
            except RuntimeError:
                has_loop = False
            if has_loop:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    pw_checks, pw_errors = pool.submit(_run_playwright_checks, playwright_urls).result()
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
