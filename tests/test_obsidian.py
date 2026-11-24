"""Tests for the Obsidian Adapter and sync functionality."""

from __future__ import annotations

import json
from pathlib import Path
from folio.obsidian import build_obsidian_theme, sync_obsidian_theme, ObsidianTheme


def test_build_obsidian_theme():
    css_stub = ":root { --sk-paper: #f7f6f2; --sk-coral: #ff4f40; }"
    theme = build_obsidian_theme(css_stub)
    
    assert isinstance(theme, ObsidianTheme)
    assert "--background-primary: #f7f6f2" in theme.theme_css
    assert "--interactive-accent: #ff4f40" in theme.theme_css
    
    manifest = json.loads(theme.manifest_json)
    assert manifest["name"] == "folio"
    assert manifest["minAppVersion"] == "1.0.0"


def test_sync_obsidian_theme_temp_vault(tmp_path: Path):
    vault1 = tmp_path / "vault1"
    vault2 = tmp_path / "vault2"
    vault1.mkdir()
    vault2.mkdir()
    
    # Pre-create old snippet and theme to test cleanup
    (vault1 / ".obsidian" / "snippets").mkdir(parents=True)
    (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").write_text("old snippet")
    
    (vault1 / ".obsidian" / "themes" / "old-theme").mkdir(parents=True)
    (vault1 / ".obsidian" / "themes" / "old-theme" / "theme.css").write_text("old theme")
    
    appearance_json = vault1 / ".obsidian" / "appearance.json"
    appearance_json.write_text(json.dumps({"cssTheme": "old-theme", "enabledCssSnippets": ["dissertation-spacing"]}))
    
    theme = build_obsidian_theme(":root {}")
    results = sync_obsidian_theme(theme, vaults=[vault1, vault2, tmp_path / "nonexistent"])
    
    assert results[str(vault1)] == "synced"
    assert results[str(vault2)] == "synced"
    assert "error: missing vault" in results[str(tmp_path / "nonexistent")]
    
    # Verify vault1 state
    assert (vault1 / ".obsidian" / "themes" / "folio" / "theme.css").exists()
    assert (vault1 / ".obsidian" / "themes" / "folio" / "manifest.json").exists()
    assert not (vault1 / ".obsidian" / "themes" / "old-theme").exists()
    assert not (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").exists()
    
    app_data = json.loads(appearance_json.read_text())
    assert app_data["cssTheme"] == "folio"
    assert "dissertation-spacing" not in app_data.get("enabledCssSnippets", [])
