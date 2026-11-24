"""Tests for the Obsidian Adapter, sync, and vault drift verification."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import folio
from folio.bundle import build_release
from folio.obsidian import (
    ObsidianSyncResult,
    ObsidianTheme,
    build_obsidian_theme,
    sync_obsidian_theme,
    verify_obsidian_vault,
)
from folio.verifier import VerificationResult, verify_target

REAL_CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "folio"
    / "static"
    / "folio"
    / "css"
    / "sk-design-system.css"
)


def _real_tokens_css() -> str:
    return REAL_CSS_PATH.read_text(encoding="utf-8")


def _tokens_css_with_overrides(**overrides: str) -> str:
    css = _real_tokens_css()
    for token, value in overrides.items():
        css = re.sub(
            rf"({re.escape(token)}\s*:\s*)([^;]+)(;)",
            rf"\g<1>{value}\g<3>",
            css,
            count=1,
        )
    return css


def test_obsidian_symbols_exported_in_folio_all() -> None:
    expected = {
        "ObsidianSyncResult",
        "ObsidianTheme",
        "build_obsidian_theme",
        "sync_obsidian_theme",
        "verify_obsidian_vault",
    }
    assert expected.issubset(set(folio.__all__))
    assert folio.__all__ == sorted(folio.__all__)
    for sym in expected:
        assert hasattr(folio, sym)


def test_build_obsidian_theme_from_real_sk_design_system_css() -> None:
    theme = build_obsidian_theme(_real_tokens_css())

    assert isinstance(theme, ObsidianTheme)
    css = theme.theme_css

    # Light :root tokens used; dark (#17191c, #ffa093) and @media print (#000000) ignored
    assert "--background-primary: #f7f6f2;" in css
    assert "--background-secondary: #ffffff;" in css
    assert "--background-modifier-border: #d9d8e2;" in css
    assert "--text-normal: #34344a;" in css
    assert "--text-muted: #626276;" in css
    assert "#17191c" not in css
    assert "#ffa093" not in css

    # --text-accent and links = --sk-link (#9c3028); coral only on --interactive-accent fills
    assert "--text-accent: #9c3028;" in css
    assert "--text-accent-hover: #9c3028;" in css
    assert "--link-color: #9c3028;" in css
    assert "--link-color-hover: #9c3028;" in css
    assert "--interactive-accent: #ff4f40;" in css
    assert "--text-on-accent: #271b24;" in css

    # Ten role families mapped using their real --sk-family-<name>-{surface,mark} names
    expected_families = (
        ("coral", "#ffe2dc", "#ff4f40"),
        ("blue", "#dbeafe", "#2864b4"),
        ("gold", "#fff0c2", "#9a6700"),
        ("teal", "#d8f3ec", "#087f75"),
        ("violet", "#ede3fa", "#7751b0"),
        ("rose", "#fbe0ed", "#b04478"),
        ("cyan", "#d9f2fa", "#14758f"),
        ("orange", "#fce7d5", "#b45114"),
        ("leaf", "#e6eecf", "#55732b"),
        ("slate", "#e3e8ef", "#52677f"),
    )
    for name, surface_hex, mark_hex in expected_families:
        assert f"--sk-family-{name}-surface: {surface_hex};" in css
        assert f"--sk-family-{name}-mark: {mark_hex};" in css

    # F3 typography, font-synthesis on body/prose (not in @font-face), Mono 0.85rem, Serif .cm-content
    font_face_blocks = re.findall(r"@font-face\s*\{[^}]*\}", css, flags=re.DOTALL)
    assert len(font_face_blocks) >= 3
    for block in font_face_blocks:
        assert "font-synthesis" not in block
        assert "data:font/ttf;base64," in block

    assert "font-synthesis: none;" in css
    assert ".markdown-source-view .cm-scroller" not in css

    cm_content_match = re.search(
        r"\.markdown-source-view\s+\.cm-content\s*\{[^}]*\}",
        css,
        flags=re.DOTALL,
    )
    assert cm_content_match is not None
    assert '"IBM Plex Serif"' in cm_content_match.group(0)
    assert "font-size: 1rem;" in cm_content_match.group(0)
    assert "line-height: 1.75;" in cm_content_match.group(0)
    assert "font-synthesis: none;" in cm_content_match.group(0)

    mono_rule_match = re.search(
        r"code,\s*pre,[^\{]*\.metadata-container,\s*\.tree-item-self\s*\{[^}]*\}",
        css,
        flags=re.DOTALL,
    )
    assert mono_rule_match is not None
    assert '"IBM Plex Mono"' in mono_rule_match.group(0)
    assert "font-size: 0.85rem;" in mono_rule_match.group(0)

    manifest = json.loads(theme.manifest_json)
    assert manifest["name"] == "folio"
    assert manifest["version"] == folio.__version__
    assert manifest["author"] == "folio"
    assert manifest["minAppVersion"] == "1.0.0"


def test_obsidian_unmapped_token_guard() -> None:
    with pytest.raises(ValueError, match="missing required semantic token"):
        build_obsidian_theme(":root {}")


@pytest.mark.parametrize(
    ("token", "bad_value"),
    [
        ("--sk-ink", "#e0dfd8"),       # fails vs paper and surface
        ("--sk-muted", "#9999a8"),     # fails vs paper and surface
        ("--sk-link", "#ff4f40"),      # coral fails vs paper and surface
        ("--sk-on-coral", "#ffffff"),  # white fails on coral #ff4f40
    ],
)
def test_obsidian_wcag_contrast_guard_rejects_any_failing_pair(
    token: str,
    bad_value: str,
) -> None:
    bad_css = _tokens_css_with_overrides(**{token: bad_value})
    with pytest.raises(ValueError, match="WCAG 2.2 AA contrast"):
        build_obsidian_theme(bad_css)


def test_obsidian_wcag_contrast_guard_rejects_single_surface_failure() -> None:
    # Paper is light (#f7f6f2), surface is dark (#34344a): ink (#34344a) passes on paper
    # but fails (1:1) on surface. Guard MUST fail if ANY pair fails.
    bad_css = _tokens_css_with_overrides(**{"--sk-surface": "#34344a"})
    with pytest.raises(ValueError, match="WCAG 2.2 AA contrast"):
        build_obsidian_theme(bad_css)


def test_sync_and_verify_obsidian_vault_round_trip(tmp_path: Path) -> None:
    vault1 = tmp_path / "vault1"
    vault2 = tmp_path / "vault2"
    not_a_vault = tmp_path / "plain-dir"
    missing_vault = tmp_path / "does-not-exist"
    for v in (vault1, vault2):
        (v / ".obsidian").mkdir(parents=True)
    not_a_vault.mkdir()

    # Pre-create old snippet, old theme dir, and loose old theme file to test cleanup
    (vault1 / ".obsidian" / "snippets").mkdir(parents=True)
    (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").write_text("old snippet", encoding="utf-8")
    (vault1 / ".obsidian" / "themes" / "old-theme").mkdir(parents=True)
    (vault1 / ".obsidian" / "themes" / "old-theme" / "theme.css").write_text("old theme", encoding="utf-8")
    (vault1 / ".obsidian" / "themes" / "loose-theme.css").write_text("loose theme", encoding="utf-8")

    appearance_json = vault1 / ".obsidian" / "appearance.json"
    appearance_json.write_text(
        json.dumps({"cssTheme": "old-theme", "enabledCssSnippets": ["dissertation-spacing", "other"], "baseFontSize": 16}),
        encoding="utf-8",
    )

    theme = build_obsidian_theme(_real_tokens_css())
    results = sync_obsidian_theme(theme, vaults=[vault1, vault2, not_a_vault, missing_vault])

    assert len(results) == 4
    assert all(isinstance(r, ObsidianSyncResult) for r in results)
    by_vault = {r.vault: r for r in results}

    assert by_vault[str(vault1.resolve())].synced is True
    assert by_vault[str(vault2.resolve())].synced is True
    assert by_vault[str(not_a_vault.resolve())].synced is False
    assert by_vault[str(missing_vault.resolve())].synced is False
    assert not (not_a_vault / ".obsidian").exists()

    # Verify vault1 cleanup and appearance.json preservation
    assert not (vault1 / ".obsidian" / "themes" / "old-theme").exists()
    assert not (vault1 / ".obsidian" / "themes" / "loose-theme.css").exists()
    assert not (vault1 / ".obsidian" / "snippets" / "dissertation-spacing.css").exists()
    app_data = json.loads(appearance_json.read_text(encoding="utf-8"))
    assert app_data["cssTheme"] == "folio"
    assert app_data["enabledCssSnippets"] == ["other"]
    assert app_data["baseFontSize"] == 16

    # verify_obsidian_vault passes cleanly on both synced vaults
    v1_res = verify_obsidian_vault(theme, vault1)
    v2_res = verify_obsidian_vault(theme, vault2)
    assert isinstance(v1_res, VerificationResult)
    assert v1_res.passed is True
    assert v1_res.drifted is False
    assert v1_res.errors == ()
    assert v2_res.passed is True

    # Hooked into folio.verifier.verify_target
    target_res = verify_target(vault1, run_playwright=False, check_catalogue=False)
    assert target_res.passed is True


def test_verify_obsidian_vault_detects_drift(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    theme = build_obsidian_theme(_real_tokens_css())
    sync_obsidian_theme(theme, [vault])

    # 1. theme.css drift
    theme_css = vault / ".obsidian" / "themes" / "folio" / "theme.css"
    original_css = theme_css.read_text(encoding="utf-8")
    theme_css.write_text(original_css + "\n/* manual edit */\n", encoding="utf-8")
    drift_res = verify_obsidian_vault(theme, vault)
    assert drift_res.passed is False
    assert drift_res.drifted is True
    assert any("theme.css" in err for err in drift_res.errors)

    target_res = verify_target(vault, run_playwright=False, check_catalogue=False)
    assert target_res.passed is False
    assert any("theme.css" in err for err in target_res.errors)

    # Restore theme.css and test manifest, third-party theme, appearance, and retired snippet drift
    theme_css.write_text(original_css, encoding="utf-8")
    (vault / ".obsidian" / "themes" / "stray.css").write_text("/* stray */", encoding="utf-8")
    (vault / ".obsidian" / "snippets").mkdir(parents=True, exist_ok=True)
    (vault / ".obsidian" / "snippets" / "dissertation-spacing.css").write_text("/* old */", encoding="utf-8")
    app_path = vault / ".obsidian" / "appearance.json"
    app_path.write_text(json.dumps({"cssTheme": "Primary", "enabledCssSnippets": ["dissertation-spacing"]}), encoding="utf-8")

    multi_drift = verify_obsidian_vault(theme, vault)
    assert multi_drift.passed is False
    assert any("stray.css" in err for err in multi_drift.errors)
    assert any("dissertation-spacing" in err for err in multi_drift.errors)
    assert any("appearance.json" in err for err in multi_drift.errors)


def test_bundle_emits_dist_obsidian_theme_and_manifest(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    manifest = build_release(dist_dir, version="v0.2.0", git_sha="obsidiansha")

    obsidian_css = dist_dir / "obsidian" / "theme.css"
    obsidian_manifest = dist_dir / "obsidian" / "manifest.json"
    assert obsidian_css.is_file()
    assert obsidian_manifest.is_file()
    assert "obsidian/theme.css" in manifest.assets
    assert "obsidian/manifest.json" in manifest.assets

    expected = build_obsidian_theme(_real_tokens_css())
    assert obsidian_css.read_text(encoding="utf-8") == expected.theme_css
    assert obsidian_manifest.read_text(encoding="utf-8") == expected.manifest_json
