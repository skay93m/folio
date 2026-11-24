"""Obsidian Adapter for Folio: builds, syncs, and verifies the 'folio' Obsidian theme."""

from __future__ import annotations

import base64
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from folio.catalogue import iter_css_blocks
from folio.verifier import VerificationResult

_ROLE_FAMILIES: tuple[str, ...] = (
    "coral",
    "blue",
    "gold",
    "teal",
    "violet",
    "rose",
    "cyan",
    "orange",
    "leaf",
    "slate",
)

_REQUIRED_CORE_TOKENS: tuple[str, ...] = (
    "--sk-paper",
    "--sk-surface",
    "--sk-border",
    "--sk-ink",
    "--sk-muted",
    "--sk-coral",
    "--sk-on-coral",
    "--sk-link",
    "--sk-fill",
)

_REQUIRED_TOKENS: tuple[str, ...] = _REQUIRED_CORE_TOKENS + tuple(
    f"--sk-family-{family}-{kind}" for family in _ROLE_FAMILIES for kind in ("surface", "mark")
)

_FONT_SPECS: tuple[tuple[str, str, str], ...] = (
    ("IBM Plex Sans", "IBMPlexSans.ttf", "100 700"),
    ("IBM Plex Serif", "IBMPlexSerif-Regular.ttf", "400"),
    ("IBM Plex Serif", "IBMPlexSerif-SemiBold.ttf", "600"),
    ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400"),
    ("IBM Plex Mono", "IBMPlexMono-SemiBold.ttf", "600"),
)

_CSS_VAR_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", re.IGNORECASE)
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


@dataclass(frozen=True, slots=True)
class ObsidianTheme:
    """Immutable Obsidian theme representation."""

    theme_css: str
    manifest_json: str


@dataclass(frozen=True, slots=True)
class ObsidianSyncResult:
    """Structured outcome of syncing the folio theme to one Obsidian vault."""

    vault: str
    synced: bool
    status: str
    errors: tuple[str, ...] = ()


def _font_to_base64(font_path: Path) -> str:
    if not font_path.is_file():
        return ""
    encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
    return f"data:font/ttf;base64,{encoded}"


def _is_light_root_selector(selector: str) -> bool:
    stripped = selector.lstrip()
    if not stripped or stripped.startswith("@"):
        return False
    parts = [part.strip() for part in stripped.split(",")]
    has_root = any(part == ":root" for part in parts)
    has_dark = any("dark" in part.lower() for part in parts)
    return has_root and not has_dark


def _parse_tokens(tokens_css: str) -> dict[str, str]:
    """Parse CSS custom properties solely from top-level light :root rule blocks."""
    vars_map: dict[str, str] = {}
    for selector, body in iter_css_blocks(tokens_css):
        if not _is_light_root_selector(selector):
            continue
        for key, value in _CSS_VAR_RE.findall(body):
            vars_map[key.strip()] = value.strip()
    return vars_map


def _rel_lum(r: int, g: int, b: int) -> float:
    def chan(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1 = _rel_lum(*fg)
    l2 = _rel_lum(*bg)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    cleaned = hex_str.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(c * 2 for c in cleaned)
    if len(cleaned) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", cleaned):
        raise ValueError(f"invalid hex colour token: {hex_str!r}")
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def _check_wcag_contrast(tokens: dict[str, str]) -> None:
    paper = tokens["--sk-paper"]
    surface = tokens["--sk-surface"]
    ink = tokens["--sk-ink"]
    muted = tokens["--sk-muted"]
    link = tokens["--sk-link"]
    coral = tokens["--sk-coral"]
    on_coral = tokens["--sk-on-coral"]

    pairs = (
        ("ink", ink, "paper", paper),
        ("ink", ink, "surface", surface),
        ("muted", muted, "paper", paper),
        ("muted", muted, "surface", surface),
        ("link", link, "paper", paper),
        ("link", link, "surface", surface),
        ("on_coral", on_coral, "coral", coral),
    )
    for fg_name, fg_hex, bg_name, bg_hex in pairs:
        ratio = _contrast_ratio(_hex_to_rgb(fg_hex), _hex_to_rgb(bg_hex))
        if ratio < 4.5:
            raise ValueError(
                f"WCAG 2.2 AA contrast failure for {fg_name} ({fg_hex}) on {bg_name} ({bg_hex}): {ratio:.2f}:1 < 4.5:1"
            )


def _build_font_faces(fonts_dir: Path) -> str:
    blocks: list[str] = []
    for family, filename, weight in _FONT_SPECS:
        b64 = _font_to_base64(fonts_dir / filename)
        if not b64:
            continue
        blocks.append(
            f"@font-face {{\n"
            f'  font-family: "{family}";\n'
            f'  src: url("{b64}") format("truetype");\n'
            f"  font-weight: {weight};\n"
            f"  font-style: normal;\n"
            f"}}"
        )
    return "\n\n".join(blocks)


def build_obsidian_theme(tokens_css: str, fonts_dir: Path | None = None) -> ObsidianTheme:
    """Build the light-only 'folio' Obsidian theme from the Token module CSS."""
    tokens = _parse_tokens(tokens_css)
    for required in _REQUIRED_TOKENS:
        if required not in tokens:
            raise ValueError(f"missing required semantic token: {required}")

    _check_wcag_contrast(tokens)

    paper = tokens["--sk-paper"]
    surface = tokens["--sk-surface"]
    border = tokens["--sk-border"]
    ink = tokens["--sk-ink"]
    muted = tokens["--sk-muted"]
    coral = tokens["--sk-coral"]
    on_coral = tokens["--sk-on-coral"]
    link = tokens["--sk-link"]
    fill = tokens["--sk-fill"]

    resolved_fonts_dir = fonts_dir or (Path(__file__).resolve().parent / "static" / "folio" / "fonts")
    font_faces_css = _build_font_faces(resolved_fonts_dir)

    family_lines = "\n".join(
        f"  --sk-family-{family}-{kind}: {tokens[f'--sk-family-{family}-{kind}']};"
        for family in _ROLE_FAMILIES
        for kind in ("surface", "mark")
    )

    theme_css = f"""/*
 * Folio Theme for Obsidian (SK Design System ADR 0020)
 * Light mode baseline with F3 typography and Monzo coral interactive fills.
 */

{font_faces_css}

body,
.theme-light,
.theme-dark {{
  --background-primary: {paper};
  --background-secondary: {surface};
  --background-modifier-border: {border};
  --code-background: {fill};

  --text-normal: {ink};
  --text-muted: {muted};
  --text-accent: {link};
  --text-accent-hover: {link};
  --text-on-accent: {on_coral};

  --interactive-accent: {coral};
  --interactive-accent-hover: {coral};

  --link-color: {link};
  --link-color-hover: {link};

  --font-text: "IBM Plex Serif", serif;
  --font-interface: "IBM Plex Sans", sans-serif;
  --font-monospace: "IBM Plex Mono", monospace;

  --font-heading-weight: 600;
  --h1-font-size: 1.75rem;
  --h2-font-size: 1.25rem;
  --h3-font-size: 1.05rem;

  font-family: "IBM Plex Sans", sans-serif;
  font-synthesis: none;

{family_lines}
}}

.markdown-rendered,
.markdown-preview-view,
.markdown-source-view .cm-content {{
  font-family: "IBM Plex Serif", serif;
  font-size: 1rem;
  line-height: 1.75;
  font-synthesis: none;
}}

.markdown-rendered p,
.markdown-preview-view p {{
  margin-block-end: 1.5em;
}}

code,
pre,
.cm-inline-code,
.HyperMD-codeblock,
.metadata-container,
.tree-item-self {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.85rem;
}}

code {{
  color: var(--text-normal);
  background-color: {fill};
}}

pre {{
  background-color: {fill};
  border: 1px solid {border};
}}

pre code {{
  background-color: transparent;
}}

h1,
h2,
h3,
h4 {{
  font-family: "IBM Plex Sans", sans-serif;
  font-weight: 600;
  text-align: left;
}}

h1 {{
  font-size: 1.75rem;
  line-height: 1.25;
}}

h2 {{
  font-size: 1.25rem;
  line-height: 1.35;
}}

h3 {{
  font-size: 1.05rem;
  line-height: 1.35;
}}

h4 {{
  font-size: 0.95rem;
  line-height: 1.4;
}}
"""

    from folio import __version__

    manifest_dict = {
        "name": "folio",
        "version": __version__,
        "minAppVersion": "1.0.0",
        "author": "folio",
        "description": "SK Design System theme for Obsidian",
        "desktopOnly": False,
    }
    manifest_json = json.dumps(manifest_dict, indent=2)
    return ObsidianTheme(theme_css=theme_css, manifest_json=manifest_json)


def sync_obsidian_theme(
    theme: ObsidianTheme,
    vaults: Iterable[Path | str],
) -> tuple[ObsidianSyncResult, ...]:
    """Sync the 'folio' Obsidian theme one-way to explicit allowlisted vaults."""
    results: list[ObsidianSyncResult] = []
    for vault_path_raw in vaults:
        vault_path = Path(vault_path_raw).expanduser().resolve()
        if not vault_path.is_dir():
            results.append(
                ObsidianSyncResult(
                    vault=str(vault_path),
                    synced=False,
                    status="missing-vault",
                    errors=(f"missing vault: {vault_path}",),
                )
            )
            continue

        obsidian_dir = vault_path / ".obsidian"
        if not obsidian_dir.is_dir():
            results.append(
                ObsidianSyncResult(
                    vault=str(vault_path),
                    synced=False,
                    status="not-an-obsidian-vault",
                    errors=(f"not an obsidian vault: {vault_path}",),
                )
            )
            continue

        try:
            themes_root = obsidian_dir / "themes"
            if themes_root.is_dir():
                for item in themes_root.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    elif item.is_file() and item.suffix == ".css":
                        item.unlink()

            folio_theme_dir = themes_root / "folio"
            folio_theme_dir.mkdir(parents=True, exist_ok=True)
            (folio_theme_dir / "theme.css").write_text(theme.theme_css, encoding="utf-8")
            (folio_theme_dir / "manifest.json").write_text(theme.manifest_json, encoding="utf-8")

            appearance_path = obsidian_dir / "appearance.json"
            appearance_data: dict[str, Any] = {}
            if appearance_path.is_file():
                try:
                    loaded = json.loads(appearance_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        appearance_data = loaded
                except json.JSONDecodeError:
                    appearance_data = {}

            appearance_data["cssTheme"] = "folio"
            snippets = appearance_data.get("enabledCssSnippets")
            if isinstance(snippets, list) and "dissertation-spacing" in snippets:
                appearance_data["enabledCssSnippets"] = [s for s in snippets if s != "dissertation-spacing"]
            appearance_path.write_text(json.dumps(appearance_data, indent=2), encoding="utf-8")

            snippet_path = obsidian_dir / "snippets" / "dissertation-spacing.css"
            if snippet_path.is_file():
                snippet_path.unlink()

            results.append(
                ObsidianSyncResult(
                    vault=str(vault_path),
                    synced=True,
                    status="synced",
                )
            )
        except Exception as exc:
            results.append(
                ObsidianSyncResult(
                    vault=str(vault_path),
                    synced=False,
                    status="error",
                    errors=(str(exc),),
                )
            )

    return tuple(results)


def verify_obsidian_vault(theme: ObsidianTheme, vault: Path | str) -> VerificationResult:
    """Check one Obsidian vault for theme, manifest, appearance, or retired-snippet drift."""
    vault_path = Path(vault).expanduser().resolve()
    checks: list[str] = []
    errors: list[str] = []

    if not vault_path.is_dir():
        return VerificationResult(
            passed=False,
            target=str(vault_path),
            checks=(),
            errors=(f"missing vault: {vault_path}",),
        )

    obsidian_dir = vault_path / ".obsidian"
    if not obsidian_dir.is_dir():
        return VerificationResult(
            passed=False,
            target=str(vault_path),
            checks=(),
            errors=(f"not an obsidian vault: {vault_path}",),
        )
    checks.append("obsidian-dir:present")

    themes_root = obsidian_dir / "themes"
    folio_theme_dir = themes_root / "folio"
    theme_css_path = folio_theme_dir / "theme.css"
    manifest_path = folio_theme_dir / "manifest.json"

    if not theme_css_path.is_file():
        errors.append(f"missing theme.css in {folio_theme_dir}")
    elif theme_css_path.read_text(encoding="utf-8") != theme.theme_css:
        errors.append(f"theme.css drift detected in {theme_css_path}")
    else:
        checks.append("obsidian-theme-css:match")

    if not manifest_path.is_file():
        errors.append(f"missing manifest.json in {folio_theme_dir}")
    elif manifest_path.read_text(encoding="utf-8") != theme.manifest_json:
        errors.append(f"manifest.json drift detected in {manifest_path}")
    else:
        checks.append("obsidian-manifest-json:match")

    if themes_root.is_dir():
        strays = sorted(
            item.name
            for item in themes_root.iterdir()
            if item.name != "folio" and (item.is_dir() or item.suffix == ".css")
        )
        for stray in strays:
            errors.append(f"unexpected third-party theme in {themes_root}: {stray}")
        if not strays:
            checks.append("obsidian-themes:clean")

    appearance_path = obsidian_dir / "appearance.json"
    if not appearance_path.is_file():
        errors.append(f"missing appearance.json in {obsidian_dir}")
    else:
        try:
            appearance_data = json.loads(appearance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid appearance.json in {obsidian_dir}: {exc}")
        else:
            if not isinstance(appearance_data, dict):
                errors.append(f"appearance.json must be a JSON object in {obsidian_dir}")
            else:
                if appearance_data.get("cssTheme") != "folio":
                    errors.append(
                        f"appearance.json cssTheme drift in {obsidian_dir}: "
                        f"expected 'folio', got {appearance_data.get('cssTheme')!r}"
                    )
                else:
                    checks.append("obsidian-appearance:folio")
                snippets = appearance_data.get("enabledCssSnippets")
                if isinstance(snippets, list) and "dissertation-spacing" in snippets:
                    errors.append(
                        f"appearance.json still enables retired snippet 'dissertation-spacing' in {obsidian_dir}"
                    )

    retired_snippet = obsidian_dir / "snippets" / "dissertation-spacing.css"
    if retired_snippet.exists():
        errors.append(f"retired dissertation-spacing.css snippet still present: {retired_snippet}")
    else:
        checks.append("obsidian-retired-snippet:absent")

    return VerificationResult(
        passed=not errors,
        target=str(vault_path),
        checks=tuple(checks),
        errors=tuple(errors),
    )
