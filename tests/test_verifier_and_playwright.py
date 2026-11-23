"""Slice 5 tests: Static + Playwright verifier, negative fixtures, and all 7 patterns."""

from pathlib import Path

import pytest
from playwright.sync_api import Page

from folio.bundle import build_release
from folio.verifier import verify_target


def test_verifier_rejects_negative_static_and_overflow_fixtures(tmp_path: Path):
    # 1. JS template-literal backtick
    bad_js = tmp_path / "bad-js.html"
    bad_js.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><body>'
        "<main><p>Hello</p></main>"
        "<script>const x = `template ${1}`;</script>"
        "</body></html>",
        encoding="utf-8",
    )
    res_js = verify_target(bad_js, run_playwright=False, check_catalogue=False)
    assert not res_js.passed
    assert any("backtick" in err.lower() for err in res_js.errors)

    # 2. Faux <em> in Serif reading prose
    bad_serif = tmp_path / "bad-serif.html"
    bad_serif.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><body>'
        '<article class="article"><p>This has <em>faux italic</em> text.</p></article>'
        "</body></html>",
        encoding="utf-8",
    )
    res_serif = verify_target(bad_serif, run_playwright=False, check_catalogue=False)
    assert not res_serif.passed
    assert any("faux" in err.lower() for err in res_serif.errors)

    # 3. Unapproved inline <style> token override
    bad_style = tmp_path / "bad-style.html"
    bad_style.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><head>'
        "<style>:root { --sk-paper: #ff00ff; }</style>"
        "</head><body><main><p>Bad style</p></main></body></html>",
        encoding="utf-8",
    )
    res_style = verify_target(bad_style, run_playwright=False, check_catalogue=False)
    assert not res_style.passed
    assert any("inline <style>" in err.lower() for err in res_style.errors)

    # 4. Horizontal overflow caught by Playwright
    bad_overflow = tmp_path / "bad-overflow.html"
    bad_overflow.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><body style="margin:0">'
        '<div style="width:2200px;height:20px;">wide</div>'
        "</body></html>",
        encoding="utf-8",
    )
    res_overflow = verify_target(bad_overflow, run_playwright=True, check_catalogue=False)
    assert not res_overflow.passed
    assert any("overflow" in err.lower() for err in res_overflow.errors)


def test_verifier_passes_on_built_dist_and_live_server(tmp_path: Path, live_server):
    dist_dir = tmp_path / "dist"
    build_release(dist_dir, version="v0.1.0", git_sha="testsha")

    dist_result = verify_target(dist_dir, run_playwright=True)
    assert dist_result.passed, f"dist verification failed: {dist_result.errors}"

    live_result = verify_target(live_server.url, run_playwright=True)
    assert live_result.passed, f"live_server verification failed: {live_result.errors}"


def test_playwright_all_seven_patterns_interactions_and_print(page: Page, live_server):
    # 1. Launchpad Light & D1 Dark + 390px + keyboard focus
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server.url}/?page=launchpad")
    page.wait_for_function("() => document.fonts.ready")
    assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(247, 246, 242)"
    page.click("#theme-toggle")
    assert page.evaluate("() => document.documentElement.dataset.bsTheme") == "dark"
    assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(23, 25, 28)"

    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

    # 2. Homepage Stage 1 static footer + F3 Serif
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server.url}/?page=homepage")
    assert page.locator(".prototype-controls").count() == 0
    assert page.evaluate("() => getComputedStyle(document.querySelector('.sk-site-footer')).position") == "static"
    assert "IBM Plex Serif" in page.evaluate(
        "() => getComputedStyle(document.querySelector('.sk-section-block p')).fontFamily"
    )

    # 3. Reading pattern + print modes
    page.goto(f"{live_server.url}/?page=reading")
    assert "IBM Plex Serif" in page.evaluate(
        "() => getComputedStyle(document.querySelector('.article p')).fontFamily"
    )
    for mode in ("colour", "greyscale", "black-white"):
        page.evaluate(f"() => {{ document.documentElement.dataset.printMode = '{mode}'; }}")
        page.emulate_media(media="print")
        assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(255, 255, 255)"
        assert page.evaluate("() => getComputedStyle(document.querySelector('.site-header')).display") == "none"
    page.emulate_media(media="screen")

    # 4. Dashboard period switch
    page.goto(f"{live_server.url}/?page=dashboard")
    assert "28" in page.locator("#metrics").inner_text()
    page.select_option("#period", "month")
    assert "92" in page.locator("#metrics").inner_text()

    # 5. SearchIndex filter and empty state
    page.goto(f"{live_server.url}/?page=search")
    page.fill("#search-text", "housekeeping")
    page.click("#run-search")
    assert "1 notes" in page.locator("#result-count").inner_text()
    page.click('[data-search-mode="Observations"]')
    assert page.locator("#search-empty").is_visible()

    # 6. Work with journal preview
    page.goto(f"{live_server.url}/?page=work")
    page.click("#switch-scope")
    assert "[general]" in page.locator("#scope-label").inner_text()
    page.fill("#journal-text", "Captured insight in memory-only preview.")
    page.click("#journal-add")
    assert page.locator("#all-count").inner_text() == "2"

    # 7. Work queues arrival & completion
    page.goto(f"{live_server.url}/?page=queue")
    initial_count = int(page.locator('.queue-tab[data-queue="housekeeping"] .count-pill').inner_text())
    page.click("#simulate-arrival")
    assert int(page.locator('.queue-tab[data-queue="housekeeping"] .count-pill').inner_text()) == initial_count + 1
    page.locator(".ticket-link").first.click()
    page.click("#ticket-complete")
    assert int(page.locator('.queue-tab[data-queue="housekeeping"] .count-pill').inner_text()) == initial_count

    # 8. Catalogue + primary-action focus ring, coral contrast, Light/Dark, 390px
    page.goto(f"{live_server.url}/catalogue/primary-action/")
    btn = page.locator(".catalogue-preview .btn-primary")
    assert btn.evaluate("el => getComputedStyle(el).backgroundColor") == "rgb(255, 79, 64)"
    assert btn.evaluate("el => getComputedStyle(el).color") == "rgb(39, 27, 36)"
    page.locator(".breadcrumb a").last.focus()
    page.keyboard.press("Tab")
    assert btn.evaluate("el => document.activeElement === el")
    assert btn.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
