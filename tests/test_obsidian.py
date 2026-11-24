"""Tests for the Obsidian Adapter and sync functionality."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from folio.obsidian import build_obsidian_theme, sync_obsidian_theme, ObsidianTheme


def test_build_obsidian_theme():
    tokens_css = """
:root, [data-bs-theme="light"] {
  --sk-paper: #f7f6f2;
  --sk-surface: #ffffff;
  --sk-border: #d9d8e2;
  --sk-ink: #34344a;
  --sk-muted: #626276;
  --sk-coral: #ff4f40;
  --sk-coral-dark: #9c3028;
  --sk-on-coral: #271b24;
  --sk-link: #9c3028;
  --sk-link-hover: #9c3028;
}
"""
    theme = build_obsidian_theme(tokens_css)
    
    assert isinstance(theme, ObsidianTheme)
    assert "--background-primary: #f7f6f2" in theme.theme_css
    assert "--interactive-accent: #ff4f40" in theme.theme_css
    
    manifest = json.loads(theme.manifest_json)
    assert manifest["name"] == "folio"
    assert manifest["author"] == "folio"
    assert manifest["minAppVersion"] == "1.0.0"


def test_obsidian_unmapped_token_guard():
    # Test that missing required tokens raises ValueError / BuildError
    bad_css = ":root {}"
    with pytest.raises(ValueError, match="missing required semantic token"):
      build_obsidian_theme(bad_css)


def test_obsidian_wcag_contrast_guard():
    # Test that insufficient contrast raises ValueError
    bad_tokens = """
:root {
  --sk-paper: #f7f6f2;
  --sk-surface: #ffffff;
  --sk-border: #d9d8e2;
  --sk-ink: #34344a;
  --sk-muted: #626276;
  --sk-coral: #ff4f40;
  --sk-coral-dark: #ff4f40; /* Bad contrast */
  --sk-on-coral: #ffffff;   /* Bad contrast */
  --sk-link: #ff4f40;       /* Bad contrast */
  --sk-link-hover: #ff4f40;
}
"""
    with pytest.raises(ValueError, match="WCAG 2.2 AA contrast"):
      build_obsidian_theme(bad_tokens)


def test_sync_obsidian_theme_temp_vault(tmp_path: Path):
    vault1 = tmp_path / "vault1"
    vault2 = tmp_path / "vault2"
    vault1.mkdir()
    vault2.mkdir()
    (vault1 / ".obsidian").mkdir()
    (vault2 / ".obsidian").mkdir()
    
    # Pre-create old snippet, old theme dir, and loose old theme file to test cleanup
    (vault1 / ".obsidian" / "snippets").mkdir(parents=True)
    (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").write_text("old snippet")
    
    (vault1 / ".obsidian" / "themes" / "old-theme").mkdir(parents=True)
    (vault1 / ".obsidian" / "themes" / "old-theme" / "theme.css").write_text("old theme")
    (vault1 / ".obsidian" / "themes" / "loose-theme.css").write_text("loose theme")
    
    appearance_json = vault1 / ".obsidian" / "appearance.json"
    appearance_json.write_text(json.dumps({"cssTheme": "old-theme", "enabledCssSnippets": ["dissertation-spacing"]}))
    
    tokens_css = """
:root {
  --sk-paper: #f7f6f2;
  --sk-surface: #ffffff;
  --sk-border: #d9d8e2;
  --sk-ink: #34344a;
  --sk-muted: #626276;
  --sk-coral: #ff4f40;
  --sk-coral-dark: #9c3028;
  --sk-on-coral: #271b24;
  --sk-link: #9c3028;
  --sk-link-hover: #9c3028;
}
"""
    theme = build_obsidian_theme(tokens_css)
    results = sync_obsidian_theme(theme, vaults=[vault1, vault2])
    
    assert results[str(vault1)] == "synced"
    assert results[str(vault2)] == "synced"
    
    # Verify vault1 state
    assert (vault1 / ".obsidian" / "themes" / "folio" / "theme.css").exists()
    assert (vault1 / ".obsidian" / "themes" / "folio" / "manifest.json").exists()
    assert not (vault1 / ".obsidian" / "themes" / "old-theme").exists()
    assert not (vault1 / ".obsidian" / "themes" / "loose-theme.css").exists()
    assert not (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").exists()
    
    app_data = json.loads(appearance_json.read_text())
    assert app_data["cssTheme"] == "folio"
    assert "dissertation-spacing" not in app_data.get("enabledCssSnippets", [])

