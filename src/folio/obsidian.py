"""Obsidian Adapter for Folio: builds and syncs the 'folio' Obsidian theme from the Token module."""

from __future__ import annotations

import base64
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ObsidianTheme:
    """Immutable Obsidian theme representation."""
    theme_css: str
    manifest_json: str


def _font_to_base64(font_path: Path) -> str:
    if not font_path.exists():
        return ""
    data = font_path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:font/ttf;base64,{encoded}"


def _parse_tokens(tokens_css: str) -> dict[str, str]:
    # Extract CSS variables from :root or [data-bs-theme="light"]
    vars_map: dict[str, str] = {}
    matches = re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", tokens_css, re.IGNORECASE)
    for k, v in matches:
        vars_map[k.strip()] = v.strip()
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
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))


def build_obsidian_theme(tokens_css: str, fonts_dir: Path | None = None) -> ObsidianTheme:
    """Pure function mapping Token module CSS to Obsidian theme CSS and manifest.json."""
    tokens = _parse_tokens(tokens_css)
    
    required_tokens = [
        "--sk-paper", "--sk-surface", "--sk-border", "--sk-ink",
        "--sk-muted", "--sk-coral", "--sk-coral-dark", "--sk-on-coral",
        "--sk-link", "--sk-link-hover"
    ]
    for rt in required_tokens:
        if rt not in tokens:
            raise ValueError(f"missing required semantic token: {rt}")

    paper = tokens["--sk-paper"]
    surface = tokens["--sk-surface"]
    border = tokens["--sk-border"]
    ink = tokens["--sk-ink"]
    muted = tokens["--sk-muted"]
    coral = tokens["--sk-coral"]
    coral_dark = tokens["--sk-coral-dark"]
    on_coral = tokens["--sk-on-coral"]
    link = tokens["--sk-link"]
    link_hover = tokens["--sk-link-hover"]

    # WCAG contrast check vs paper (#f7f6f2) and surface (#ffffff) for text/links, but accent fill (#ff4f40) is interactive/background fill with --text-on-accent (#271b24)
    bg_paper_rgb = _hex_to_rgb(paper)
    bg_surface_rgb = _hex_to_rgb(surface)
    
    # Check text/link/dark colors against background
    for name, val in [("coral_dark", coral_dark), ("link", link), ("link_hover", link_hover), ("on_coral", on_coral)]:
        fg_rgb = _hex_to_rgb(val)
        c_paper = _contrast_ratio(fg_rgb, bg_paper_rgb)
        c_surface = _contrast_ratio(fg_rgb, bg_surface_rgb)
        if c_paper < 4.5 and c_surface < 4.5:
            raise ValueError(f"WCAG 2.2 AA contrast failure for {name} ({val}): contrast {c_paper:.2f}:1 on paper, {c_surface:.2f}:1 on surface")

    font_faces_css = ""
    # Look for fonts in fonts_dir if provided, otherwise default to static/folio/fonts relative to __file__
    if not fonts_dir:
        fonts_dir = Path(__file__).resolve().parent / "static" / "folio" / "fonts"

    font_configs = [
        ("IBM Plex Sans", "IBMPlexSans.ttf", "100 700", True),
        ("IBM Plex Serif", "IBMPlexSerif-Regular.ttf", "400", False),
        ("IBM Plex Serif", "IBMPlexSerif-SemiBold.ttf", "600", True),
        ("IBM Plex Mono", "IBMPlexMono-Regular.ttf", "400", False),
        ("IBM Plex Mono", "IBMPlexMono-SemiBold.ttf", "600", True),
    ]

    for family, filename, weight, has_600 in font_configs:
        fpath = fonts_dir / filename
        b64 = _font_to_base64(fpath)
        if b64:
            synthesis_rule = "\n  font-synthesis: none;" if has_600 else ""
            font_faces_css += f"""
@font-face {{
  font-family: "{family}";
  src: url("{b64}") format("truetype");
  font-weight: {weight};
  font-style: normal;{synthesis_rule}
}}
"""

    theme_css = f"""/*
 * Folio Theme for Obsidian (SK Design System ADR 0020)
 * Light mode baseline with F3 typography and Monzo coral accent.
 */

{font_faces_css}

body, .theme-light, .theme-dark {{
  --background-primary: {paper};
  --background-secondary: {surface};
  --background-modifier-border: {border};
  
  --text-normal: {ink};
  --text-muted: {muted};
  --text-accent: {coral};
  --text-accent-hover: {coral_dark};
  --text-on-accent: {on_coral};
  
  --interactive-accent: {coral};
  --interactive-accent-hover: {coral_dark};
  
  --link-color: {link};
  --link-color-hover: {link_hover};
  
  --font-text: "IBM Plex Serif", serif;
  --font-interface: "IBM Plex Sans", sans-serif;
  --font-monospace: "IBM Plex Mono", monospace;
  
  --font-heading-weight: 600;
  --h1-font-size: 1.75rem;
  --h2-font-size: 1.25rem;
  --h3-font-size: 1.05rem;
  
  --sk-coral-surface: {tokens.get("--sk-coral-surface", "#ffe2dc")};
  --sk-coral-mark: {coral};
  --sk-blue-surface: {tokens.get("--sk-blue-surface", "#dbeafe")};
  --sk-blue-mark: {tokens.get("--sk-blue-mark", "#2864b4")};
  --sk-gold-surface: {tokens.get("--sk-gold-surface", "#fff0c2")};
  --sk-gold-mark: {tokens.get("--sk-gold-mark", "#9a6700")};
  --sk-teal-surface: {tokens.get("--sk-teal-surface", "#d8f3ec")};
  --sk-teal-mark: {tokens.get("--sk-teal-mark", "#087f75")};
  --sk-violet-surface: {tokens.get("--sk-violet-surface", "#ede3fa")};
  --sk-violet-mark: {tokens.get("--sk-violet-mark", "#7751b0")};
  --sk-rose-surface: {tokens.get("--sk-rose-surface", "#fbe0ed")};
  --sk-rose-mark: {tokens.get("--sk-rose-mark", "#b04478")};
  --sk-cyan-surface: {tokens.get("--sk-cyan-surface", "#d9f2fa")};
  --sk-cyan-mark: {tokens.get("--sk-cyan-mark", "#14758f")};
  --sk-orange-surface: {tokens.get("--sk-orange-surface", "#fce7d5")};
  --sk-orange-mark: {tokens.get("--sk-orange-mark", "#b45114")};
  --sk-leaf-surface: {tokens.get("--sk-leaf-surface", "#e6eecf")};
  --sk-leaf-mark: {tokens.get("--sk-leaf-mark", "#55732b")};
  --sk-slate-surface: {tokens.get("--sk-slate-surface", "#e3e8ef")};
  --sk-slate-mark: {tokens.get("--sk-slate-mark", "#52677f")};
}}

.markdown-rendered,
.markdown-preview-view,
.markdown-source-view .cm-content {{
  font-family: "IBM Plex Serif", serif;
  font-size: 1rem;
  line-height: 1.75;
}}

.markdown-rendered p,
.markdown-preview-view p {{
  margin-block-end: 1.5em;
}}

.markdown-source-view .cm-scroller,
.metadata-container,
.tree-item-self {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.85rem;
}}

h1, h2, h3, h4 {{
  font-family: "IBM Plex Sans", sans-serif;
  font-weight: 600;
  text-align: left;
}}

h1 {{ font-size: 1.75rem; line-height: 1.2; }}
h2 {{ font-size: 1.25rem; line-height: 1.3; }}
h3 {{ font-size: 1.05rem; line-height: 1.35; }}
h4 {{ font-size: 0.95rem; line-height: 1.4; }}
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
) -> dict[str, str]:
    """Syncs the folio Obsidian theme to allowlisted vaults (I/O)."""
    results: dict[str, str] = {}
    for vault_path_raw in vaults:
        vault_path = Path(vault_path_raw).expanduser()
        if not vault_path.exists():
            results[str(vault_path)] = "error: missing vault"
            continue
        
        try:
            obsidian_dir = vault_path / ".obsidian"
            if not obsidian_dir.exists():
                results[str(vault_path)] = "error: not an obsidian vault"
                continue
            
            # 1. Clean up old themes (directories and loose .css files in themes/)
            themes_root = obsidian_dir / "themes"
            if themes_root.exists():
                for item in themes_root.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    elif item.is_file() and item.suffix == ".css":
                        item.unlink()
            
            # Also delete loose .obsidian/themes/*.css if any
            for loose_css in obsidian_dir.glob("themes/*.css"):
                if loose_css.is_file():
                    loose_css.unlink()

            # 2. Write theme files to .obsidian/themes/folio/
            themes_dir = themes_root / "folio"
            themes_dir.mkdir(parents=True, exist_ok=True)
            
            (themes_dir / "theme.css").write_text(theme.theme_css, encoding="utf-8")
            (themes_dir / "manifest.json").write_text(theme.manifest_json, encoding="utf-8")
            
            # 3. Update appearance.json: cssTheme = "folio", preserving other keys
            appearance_path = obsidian_dir / "appearance.json"
            appearance_data: dict[str, Any] = {}
            if appearance_path.exists():
                try:
                    appearance_data = json.loads(appearance_path.read_text(encoding="utf-8"))
                except Exception:
                    appearance_data = {}
            appearance_data["cssTheme"] = "folio"
            
            snippets = appearance_data.get("enabledCssSnippets", [])
            if "dissertation-spacing" in snippets:
                snippets = [s for s in snippets if s != "dissertation-spacing"]
                appearance_data["enabledCssSnippets"] = snippets
            
            appearance_path.write_text(json.dumps(appearance_data, indent=2), encoding="utf-8")
            
            # 4. Remove dissertation-spacing snippet file if present
            snippet_path = obsidian_dir / "snippets" / "dissertation-spacing.css"
            if snippet_path.exists():
                snippet_path.unlink()
                
            results[str(vault_path)] = "synced"
        except Exception as e:
            results[str(vault_path)] = f"error: {e}"
            
    return results
