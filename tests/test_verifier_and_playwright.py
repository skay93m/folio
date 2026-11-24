"""Slice 5 tests: Static + Playwright verifier, negative fixtures, and all 7 patterns."""

from pathlib import Path

from playwright.sync_api import Page

from folio.bundle import build_release
from folio.verifier import verify_target


def test_playwright_scriptless_markdown_consumer(page: Page):
    from dataclasses import replace

    from folio import HomepageNoteItem, Reading, render_static
    from folio.fixtures import build_homepage

    reading = Reading(
        eyebrow="Note", title="A clean article title", meta=(),
        body_html='<p>Markdown prose with <a href="/source/">a source</a>.</p>',
        include_scripts=False, author_meta="Sample Author", citation_date="2026-11-23",
        meta_description="A short note", canonical_url="https://example.com/note/",
    )
    page.set_content(render_static(reading, extra_context={"page_title": "Note · Site"}))
    assert page.locator(".sk-reading-body a").inner_text() == "a source"
    assert page.locator(".abstract").count() == 0
    assert page.locator(".reading-toc .eyebrow").count() == 0
    assert page.locator("script").count() == 0
    assert page.locator("html").get_attribute("lang") == "en-GB"
    assert page.locator('meta[name="citation_title"]').get_attribute("content") == "A clean article title"
    assert page.locator('meta[name="description"]').get_attribute("content") == "A short note"
    assert page.locator('link[rel="canonical"]').get_attribute("href") == "https://example.com/note/"

    homepage = replace(build_homepage(), include_scripts=False, long_form_notes=(
        HomepageNoteItem("essay", "A longer essay", "23 November 2026", "Summary.", "/essay/"),
    ))
    page.set_content(render_static(homepage))
    assert page.locator('.sk-section-list a[href="/essay/"]').inner_text() == "A longer essay"
    assert page.locator("script").count() == 0


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

    # 5. External directory .js file containing template-literal backtick
    ext_dir = tmp_path / "ext-site"
    ext_dir.mkdir()
    (ext_dir / "app.js").write_text("const greeting = `hello ${name}`;\n", encoding="utf-8")
    (ext_dir / "index.html").write_text(
        '<!doctype html><html lang="en"><body><script src="app.js"></script></body></html>',
        encoding="utf-8",
    )
    res_ext_js = verify_target(ext_dir, run_playwright=False, check_catalogue=False)
    assert not res_ext_js.passed
    assert any("backtick" in err.lower() for err in res_ext_js.errors)

    # 6. Low-contrast status badge caught by WCAG 2.2 AA check
    bad_contrast = tmp_path / "bad-contrast.html"
    bad_contrast.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><head>'
        "<style>"
        ":root { --sk-paper: #f7f6f2; }"
        "body { background: #f7f6f2; color: #34344a; font-family: 'IBM Plex Sans', sans-serif; }"
        ".status-success { background: #d8f3ec; color: #90d8c8; padding: 4px 8px; display: inline-block; }"
        "</style></head><body>"
        '<a href="#main">Skip</a><button type="button">Action</button>'
        '<span class="status-success">Low contrast</span>'
        "</body></html>",
        encoding="utf-8",
    )
    res_contrast = verify_target(bad_contrast, run_playwright=True, check_catalogue=False)
    assert not res_contrast.passed
    assert any("wcag aa contrast" in err.lower() for err in res_contrast.errors)

    # 7. SK page without focusable visible interactive control caught by keyboard check
    bad_focus = tmp_path / "bad-focus.html"
    bad_focus.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><head>'
        "<style>"
        ":root { --sk-paper: #f7f6f2; }"
        "body { background: #f7f6f2; color: #34344a; font-family: 'IBM Plex Sans', sans-serif; }"
        "</style></head><body><main><p>No controls here</p></main></body></html>",
        encoding="utf-8",
    )
    res_focus = verify_target(bad_focus, run_playwright=True, check_catalogue=False)
    assert not res_focus.passed
    assert any("body/document" in err.lower() or "interactive control" in err.lower() for err in res_focus.errors)

    # 8. file:// asset link caught statically
    bad_file_url = tmp_path / "bad-file-url.html"
    bad_file_url.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><head>'
        '<link rel="stylesheet" href="file:///tmp/sk-design-system.css" />'
        '<script src="file:///tmp/folio.js"></script>'
        "</head><body><main><p>File links</p></main></body></html>",
        encoding="utf-8",
    )
    res_file_url = verify_target(bad_file_url, run_playwright=False, check_catalogue=False)
    assert not res_file_url.passed
    assert any("file://" in err.lower() for err in res_file_url.errors)

    # 9. Zero loaded stylesheets (stylesheetCount == 0) caught by Playwright
    no_styles = tmp_path / "no-styles.html"
    no_styles.write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><body>'
        "<main><p>Unstyled page</p></main></body></html>",
        encoding="utf-8",
    )
    res_no_styles = verify_target(no_styles, run_playwright=True, check_catalogue=False)
    assert not res_no_styles.passed
    assert any("stylesheetcount == 0" in err.lower() for err in res_no_styles.errors)

    # 10. Failed asset request (404 CSS/JS) caught by Playwright even when another stylesheet exists
    broken_asset_dir = tmp_path / "broken-assets"
    broken_asset_dir.mkdir()
    (broken_asset_dir / "index.html").write_text(
        '<!doctype html><html lang="en" data-bs-theme="light"><head>'
        "<style>body { margin: 0; }</style>"
        '<link rel="stylesheet" href="missing.css" />'
        '<script src="missing.js"></script>'
        "</head><body><main><p>Broken assets</p></main></body></html>",
        encoding="utf-8",
    )
    res_broken_asset = verify_target(broken_asset_dir, run_playwright=True, check_catalogue=False)
    assert not res_broken_asset.passed
    assert any("missing.css" in err for err in res_broken_asset.errors)
    assert any("missing.js" in err for err in res_broken_asset.errors)


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

    # 7. Work queues arrival, completion, and consistent #ticket-code
    page.goto(f"{live_server.url}/?page=queue")
    initial_count = int(page.locator('.queue-tab[data-queue="housekeeping"] .count-pill').inner_text())
    page.locator(".ticket-link").first.click()
    assert "Daily housekeeping" in page.locator("#ticket-code").inner_text()
    page.click("#ticket-close")
    page.click("#simulate-arrival")
    assert int(page.locator('.queue-tab[data-queue="housekeeping"] .count-pill').inner_text()) == initial_count + 1
    page.locator(".ticket-link").last.click()
    assert "Daily housekeeping" in page.locator("#ticket-code").inner_text()
    page.click("#ticket-close")
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


def test_playwright_homepage_d1_dark_theme_and_search_initial_filter(page: Page, live_server, tmp_path: Path):
    # 1. Homepage rendered in D1 Dark (?page=homepage&theme=dark)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{live_server.url}/?page=homepage&theme=dark")
    page.wait_for_function("() => document.fonts.ready")
    assert page.evaluate("() => document.documentElement.dataset.bsTheme") == "dark"
    assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(23, 25, 28)"
    assert page.evaluate("() => getComputedStyle(document.body).color") == "rgb(238, 240, 242)"

    contrasts = page.evaluate(
        """() => {
            function parseColor(str) {
                const m = str && str.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
            }
            function lum(rgb) {
                const c = rgb.map(v => {
                    const s = v / 255;
                    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
                });
                return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
            }
            function ratio(fgStr, bgStr) {
                const l1 = lum(parseColor(fgStr));
                const l2 = lum(parseColor(bgStr));
                return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
            }
            const bg = getComputedStyle(document.body).backgroundColor;
            return {
                body: ratio(getComputedStyle(document.body).color, bg),
                heading: ratio(getComputedStyle(document.querySelector('h2')).color, bg),
                muted: ratio(getComputedStyle(document.querySelector('.sk-meta-line')).color, bg),
                link: ratio(getComputedStyle(document.querySelector('.sk-section-list a')).color, bg),
            };
        }"""
    )
    for role, val in contrasts.items():
        assert val >= 4.5, f"D1 Dark Homepage {role} contrast {val:.2f} < 4.5"

    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")

    # 2. SearchIndex with initial query & active_filters invokes runSearchFilter() on load
    import shutil

    from folio import render_static
    from folio.bundle import STATIC_SOURCE_DIR
    from folio.contracts import SearchFilter, SearchIndex
    from folio.fixtures import build_search

    base_search = build_search()
    prefilled = SearchIndex(
        eyebrow=base_search.eyebrow,
        title=base_search.title,
        intro=base_search.intro,
        facets=base_search.facets,
        modes=base_search.modes,
        selected_mode="Notes",
        records=base_search.records,
        active_filters=(SearchFilter("topic", "equals", "Housekeeping"),),
        query="queue",
    )
    search_dir = tmp_path / "search-init"
    search_dir.mkdir()
    shutil.copytree(STATIC_SOURCE_DIR, search_dir / "assets")
    (search_dir / "index.html").write_text(
        render_static(prefilled, static_prefix="assets/"),
        encoding="utf-8",
    )
    obs_mode = SearchIndex(
        eyebrow=base_search.eyebrow,
        title=base_search.title,
        intro=base_search.intro,
        facets=base_search.facets,
        modes=base_search.modes,
        selected_mode="Observations",
        records=base_search.records,
    )
    (search_dir / "obs.html").write_text(
        render_static(obs_mode, static_prefix="assets/"),
        encoding="utf-8",
    )
    from folio.verifier import _serve_directory

    server, base_url = _serve_directory(search_dir)
    try:
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(f"{base_url}/index.html")
        assert "1 notes in this sample" in page.locator("#result-count").inner_text()
        page.goto(f"{base_url}/obs.html")
        assert "0 observations in this sample" in page.locator("#result-count").inner_text()
        assert page.locator("#search-empty").is_visible()
    finally:
        server.shutdown()
        server.server_close()
