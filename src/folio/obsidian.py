"""Obsidian Adapter for Folio: builds and syncs the 'folio' Obsidian theme from the Token module."""

from __future__ import annotations

import base64
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_ALLOWLISTED_VAULTS = (
    Path("~/Home/docs").expanduser(),
    Path("~/Repos/coaches/life-coach").expanduser(),
    Path("~/Repos/coaches/career-coach").expanduser(),
    Path("~/Repos/coaches/study-coach").expanduser(),
    Path("~/Repos/projects/mhel-dissertation").expanduser(),
)


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


def build_obsidian_theme(tokens_css: str, fonts_dir: Path | None = None) -> ObsidianTheme:
    """Pure function mapping Token module CSS to Obsidian theme CSS and manifest.json."""
    # Extract semantic tokens or fall back to standard F3/D1 mappings
    # For Obsidian, we emit .theme-light and .theme-dark sharing light tokens (light only per ADR).
    
    font_faces_css = ""
    if fonts_dir and fonts_dir.exists():
        sans_path = fonts_dir / "IBMPlexSans.ttf"
        serif_path = fonts_dir / "IBMPlexSerif-Regular.ttf"
        mono_path = fonts_dir / "IBMPlexMono-Regular.ttf"
        
        sans_b64 = _font_to_base64(sans_path)
        serif_b64 = _font_to_base64(serif_path)
        mono_b64 = _font_to_base64(mono_path)
        
        if sans_b64:
            font_faces_css += f"""
@font-face {{
  font-family: "IBM Plex Sans";
  src: url("{sans_b64}") format("truetype");
  font-weight: 100 700;
  font-style: normal;
}}
"""
        if serif_b64:
            font_faces_css += f"""
@font-face {{
  font-family: "IBM Plex Serif";
  src: url("{serif_b64}") format("truetype");
  font-weight: 400;
  font-style: normal;
}}
"""
        if mono_b64:
            font_faces_css += f"""
@font-face {{
  font-family: "IBM Plex Mono";
  src: url("{mono_b64}") format("truetype");
  font-weight: 400;
  font-style: normal;
}}
"""

    theme_css = f"""/*
 * Folio Theme for Obsidian (SK Design System ADR 0020)
 * Light mode baseline with F3 typography and Monzo coral accent.
 */

{font_faces_css}

body, .theme-light, .theme-dark {{
  --background-primary: #f7f6f2;
  --background-secondary: #ffffff;
  --background-modifier-border: #d9d8e2;
  
  --text-normal: #34344a;
  --text-muted: #626276;
  --text-accent: #ff4f40;
  --text-accent-hover: #9c3028;
  
  --interactive-accent: #ff4f40;
  --interactive-accent-hover: #9c3028;
  
  --link-color: #9c3028;
  --link-color-hover: #ff4f40;
  
  --font-text: "IBM Plex Serif", serif;
  --font-interface: "IBM Plex Sans", sans-serif;
  --font-monospace: "IBM Plex Mono", monospace;
  
  /* Heading typography (F3 sentence case, left-aligned, 600 weight) */
  --font-heading-weight: 600;
  --h1-font-size: 1.75rem;
  --h2-font-size: 1.25rem;
  --h3-font-size: 1.05rem;
  
  /* Role colours / Callouts */
  --sk-coral-surface: #ffe2dc;
  --sk-coral-mark: #ff4f40;
  --sk-blue-surface: #dbeafe;
  --sk-blue-mark: #2864b4;
  --sk-gold-surface: #fff0c2;
  --sk-gold-mark: #9a6700;
  --sk-teal-surface: #d8f3ec;
  --sk-teal-mark: #087f75;
  --sk-violet-surface: #ede3fa;
  --sk-violet-mark: #7751b0;
  --sk-rose-surface: #fbe0ed;
  --sk-rose-mark: #b04478;
  --sk-cyan-surface: #d9f2fa;
  --sk-cyan-mark: #14758f;
  --sk-orange-surface: #fce7d5;
  --sk-orange-mark: #b45114;
  --sk-leaf-surface: #e6eecf;
  --sk-leaf-mark: #55732b;
  --sk-slate-surface: #e3e8ef;
  --sk-slate-mark: #52677f;
}}

/* Absorbed dissertation-spacing.css rules consistent with F3 */
.markdown-rendered,
.markdown-preview-view,
.markdown-source-view .cm-content {{
  line-height: 1.75;
}}

.markdown-rendered p,
.markdown-preview-view p {{
  margin-block-end: 1.5em;
}}

h1, h2, h3, h4, h5, h6 {{
  font-family: "IBM Plex Sans", sans-serif;
  font-weight: 600;
  text-align: left;
}}
"""

    manifest_dict = {
        "name": "folio",
        "version": "0.2.0",
        "minAppVersion": "1.0.0",
        "author": "Syafiq Kay",
        "description": "SK Design System theme for Obsidian",
        "desktopOnly": False,
    }
    manifest_json = json.dumps(manifest_dict, indent=2)

    return ObsidianTheme(theme_css=theme_css, manifest_json=manifest_json)


def sync_obsidian_theme(
    theme: ObsidianTheme,
    vaults: Iterable[Path | str] = DEFAULT_ALLOWLISTED_VAULTS,
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
            obsidian_dir.mkdir(parents=True, exist_ok=True)
            
            # 1. Write theme files to .obsidian/themes/folio/
            themes_dir = obsidian_dir / "themes" / "folio"
            themes_dir.mkdir(parents=True, exist_ok=True)
            
            (themes_dir / "theme.css").write_text(theme.theme_css, encoding="utf-8")
            (themes_dir / "manifest.json").write_text(theme.manifest_json, encoding="utf-8")
            
            # 2. Update appearance.json: cssTheme = "folio", preserving other keys
            appearance_path = obsidian_dir / "appearance.json"
            appearance_data: dict[str, Any] = {}
            if appearance_path.exists():
                try:
                    appearance_data = json.loads(appearance_path.read_text(encoding="utf-8"))
                except Exception:
                    appearance_data = {}
            appearance_data["cssTheme"] = "folio"
            
            # Remove dissertation-spacing from enabledCssSnippets if present
            snippets = appearance_data.get("enabledCssSnippets", [])
            if isinstance(snippets, list):
                appearance_data["enabledCssSnippets"] = [
                    s for s in snippets if s != "dissertation-spacing"
                ]
            
            appearance_path.write_text(json.dumps(appearance_data, indent=2), encoding="utf-8")
            
            # 3. Delete dissertation-spacing snippet file if present
            snippet_file = obsidian_dir / "snippets" / "dissertation-spacing.css"
            if snippet_file.exists():
                snippet_file.unlink()
                
            # 4. Delete other folders in .obsidian/themes/
            parent_themes_dir = obsidian_dir / "themes"
            if parent_themes_dir.exists():
                for sub_item in parent_themes_dir.iterdir():
                    if sub_item.is_dir() and sub_item.name != "folio":
                        shutil.rmtree(sub_item, ignore_errors=True)
            
            results[str(vault_path)] = "synced"
        except Exception as exc:
            results[str(vault_path)] = f"error: {exc}"
            
    return results
