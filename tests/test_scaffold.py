"""Tests for declarative Folio prototype scaffolding and ?variant switcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page

from folio.scaffold import scaffold_html
from folio.verifier import _serve_directory, verify_target


def test_scaffold_html_wraps_semantic_fragment_and_passes_verifier(tmp_path: Path):
    fragment = (
        '<h1 class="mt-0">Weekly balance review</h1>'
        "<p>Compare spending against planned categories.</p>"
        '<div class="d-flex gap-2 align-items-center">'
        '<span class="status status-success">On track</span>'
        '<button type="button" class="btn btn-primary">Save check</button>'
        "</div>"
    )
    html = scaffold_html(
        "weekly-balance",
        fragment_html=fragment,
        static_prefix="assets/",
    )

    assert "assets/vendor/bootstrap.min.css" in html
    assert "assets/css/sk-design-system.css" in html
    assert "assets/css/extensions/kakeibo.css" in html
    assert "assets/vendor/bootstrap.bundle.min.js" in html
    assert "assets/js/folio.js" in html
    assert 'class="sk-logo"' in html
    assert 'id="theme-toggle"' in html
    assert 'id="print-mode"' in html
    assert "Weekly balance review" in html

    out_file = tmp_path / "prototype-weekly-balance.html"
    out_file.write_text(html, encoding="utf-8")

    result = verify_target(out_file, run_playwright=True, check_catalogue=False)
    assert result.passed, f"Expected scaffolded HTML to pass verify_target, got: {result.errors}"


def test_scaffold_variants_switcher_and_keyboard_navigation(tmp_path: Path, page: Page):
    fragment = (
        '<section data-variant="A" data-variant-label="A: Summary">'
        '<h1 class="mt-0">Variant A Summary</h1>'
        '<p>Overview surface with <span class="status status-info">Draft</span>.</p>'
        '<input id="note-filter" class="form-control" type="text" aria-label="Filter notes" />'
        "</section>"
        '<section data-variant="B" data-variant-label="B: Ledger">'
        '<h1 class="mt-0">Variant B Ledger</h1>'
        '<button type="button" class="btn btn-primary">Record entry</button>'
        "</section>"
        '<section data-variant="C" data-variant-label="C: Audit">'
        '<h1 class="mt-0">Variant C Audit</h1>'
        "<p>Final check panel.</p>"
        "</section>"
    )
    html = scaffold_html(
        "multi-surface",
        fragment_html=fragment,
        variants=("A", "B", "C"),
        static_prefix="assets/",
    )
    out_file = tmp_path / "prototype-multi-surface.html"
    out_file.write_text(html, encoding="utf-8")

    result = verify_target(out_file, run_playwright=True, check_catalogue=False)
    assert result.passed, f"Expected multi-variant scaffold to pass verify_target, got: {result.errors}"

    server, base_url = _serve_directory(tmp_path)
    try:
        page.goto(f"{base_url}/prototype-multi-surface.html", wait_until="load")
        assert page.locator("#folio-variant-label").inner_text().strip() == "A: Summary"
        assert page.locator('[data-variant="A"]').is_visible()
        assert not page.locator('[data-variant="B"]').is_visible()

        # ArrowRight ignored inside form input
        page.fill("#note-filter", "hello")
        page.keyboard.press("ArrowRight")
        assert page.locator('[data-variant="A"]').is_visible()

        # Click next button advances to B and updates URL query param
        page.click("#folio-variant-next")
        assert "variant=B" in page.url
        assert page.locator("#folio-variant-label").inner_text().strip() == "B: Ledger"
        assert page.locator('[data-variant="B"]').is_visible()
        assert not page.locator('[data-variant="A"]').is_visible()

        # ArrowRight outside input advances to C, then wraps to A
        page.locator("#folio-variant-next").focus()
        page.keyboard.press("ArrowRight")
        assert "variant=C" in page.url
        assert page.locator('[data-variant="C"]').is_visible()

        page.keyboard.press("ArrowRight")
        assert "variant=A" in page.url
        assert page.locator('[data-variant="A"]').is_visible()

        # ArrowLeft wraps backward to C
        page.keyboard.press("ArrowLeft")
        assert "variant=C" in page.url
        assert page.locator('[data-variant="C"]').is_visible()

        # Direct ?variant=B load
        page.goto(f"{base_url}/prototype-multi-surface.html?variant=B", wait_until="load")
        assert page.locator("#folio-variant-label").inner_text().strip() == "B: Ledger"
        assert page.locator('[data-variant="B"]').is_visible()
    finally:
        server.shutdown()
        server.server_close()


def test_scaffold_rejects_invalid_slug_and_duplicate_variants():
    with pytest.raises(ValueError, match="slug"):
        scaffold_html("../escape", fragment_html="<p>bad</p>")
    with pytest.raises(ValueError, match="variant"):
        scaffold_html("good-slug", variants=("A", "A"))


def test_scaffold_separates_data_json_into_page_data_script_tag(tmp_path: Path):
    import json
    import re

    payload = {"cycle": "2026-12", "items": [{"label": "Rent", "amount": 1650.0}], "note": "Keep `backtick` safe"}
    html = scaffold_html(
        "kakeibo-data-sep",
        fragment_html='<section class="surface p-4"><h1 class="mt-0">Ledger</h1><p>Template only.</p></section>',
        data_json=payload,
        static_prefix="assets/",
    )

    match = re.search(
        r'<script id="page-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    assert json.loads(match.group(1)) == payload

    out_file = tmp_path / "prototype-kakeibo-data-sep.html"
    out_file.write_text(html, encoding="utf-8")
    result = verify_target(out_file, run_playwright=True, check_catalogue=False)
    assert result.passed, f"Expected scaffolded page with #page-data JSON to pass verify_target, got: {result.errors}"


def test_scaffold_preserves_attributes_on_data_variant_tags():
    fragment = (
        '<section id="sec-alpha" class="surface p-4" aria-label="Alpha surface" '
        'data-variant="A" data-variant-label="A: Alpha">'
        '<h1 class="mt-0">Alpha</h1>'
        "</section>"
        '<article id="art-beta" class="surface p-3" data-custom="keep-me" '
        'data-variant="B" data-variant-label="B: Beta">'
        '<h1 class="mt-0">Beta</h1>'
        "</article>"
    )
    html = scaffold_html("attr-check", fragment_html=fragment, variants=("A", "B"))
    assert '<section id="sec-alpha" class="surface p-4" aria-label="Alpha surface">' in html
    assert '<article id="art-beta" class="surface p-3" data-custom="keep-me">' in html
    assert html.count('data-variant="A"') == 1
    assert html.count('data-variant="B"') == 1

    no_ext_html = scaffold_html(
        "attr-check",
        fragment_html=fragment,
        variants=("A", "B"),
        include_extensions=False,
    )
    assert "assets/css/sk-design-system.css" in no_ext_html
    assert "assets/css/extensions/kakeibo.css" not in no_ext_html
