"""Tests for Folio's loopback prototype HTTP server helper (#243)."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Page

from folio import start_prototype_server
from folio.verifier import _serve_directory, verify_target


def test_prototype_server_serves_prototype_and_design_system_assets(tmp_path: Path):
    proto_dir = tmp_path / "proto"
    proto_dir.mkdir()
    (proto_dir / "demo.html").write_text(
        "<!doctype html><html><body><h1>Demo</h1></body></html>",
        encoding="utf-8",
    )

    server, base_url = start_prototype_server(proto_dir)
    try:
        assert base_url.startswith("http://127.0.0.1:")

        with urllib.request.urlopen(f"{base_url}/demo.html", timeout=5) as resp:
            assert resp.status == 200
            assert "<h1>Demo</h1>" in resp.read().decode("utf-8")

        for asset_path, expected_substr in (
            ("assets/vendor/bootstrap.min.css", "Bootstrap"),
            ("assets/css/sk-design-system.css", "--sk-paper"),
            ("assets/vendor/bootstrap.bundle.min.js", "Bootstrap"),
            ("assets/js/folio.js", "theme"),
        ):
            with urllib.request.urlopen(f"{base_url}/{asset_path}", timeout=5) as resp:
                assert resp.status == 200
                body = resp.read().decode("utf-8", errors="replace")
                assert expected_substr in body, f"{asset_path} missing {expected_substr!r}"

        with urllib.request.urlopen(f"{base_url}/assets/fonts/IBMPlexSans.ttf", timeout=5) as resp:
            assert resp.status == 200
            assert len(resp.read()) > 1000

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{base_url}/assets/../../pyproject.toml", timeout=5)
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_serve_directory_adapter_exposes_assets_for_standalone_prototype(tmp_path: Path, page: Page):
    proto_dir = tmp_path / "standalone"
    proto_dir.mkdir()
    proto_html = proto_dir / "index.html"
    proto_html.write_text(
        '<!doctype html><html lang="en-GB" data-bs-theme="light"><head>'
        '<meta charset="utf-8" />'
        "<title>Standalone prototype</title>"
        '<link rel="stylesheet" href="assets/vendor/bootstrap.min.css" />'
        '<link rel="stylesheet" href="assets/css/sk-design-system.css" />'
        "</head><body>"
        '<main id="main" class="page-shell">'
        '<h1 class="mt-0">Prototype heading</h1>'
        '<button type="button" class="btn btn-primary">Continue</button>'
        "</main>"
        '<script src="assets/vendor/bootstrap.bundle.min.js"></script>'
        '<script src="assets/js/folio.js"></script>'
        "</body></html>",
        encoding="utf-8",
    )

    server, base_url = _serve_directory(proto_dir)
    failed_requests: list[str] = []
    bad_responses: list[tuple[str, int]] = []
    page.on("requestfailed", lambda req: failed_requests.append(req.url))
    page.on(
        "response",
        lambda resp: bad_responses.append((resp.url, resp.status)) if resp.status >= 400 else None,
    )
    try:
        page.goto(f"{base_url}/index.html", wait_until="load")
        page.wait_for_function("() => document.fonts.ready")

        assert not failed_requests
        assert not [item for item in bad_responses if not item[0].endswith("/favicon.ico")]
        assert page.evaluate("() => document.styleSheets.length") >= 2
        assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(247, 246, 242)"
        assert "IBM Plex Sans" in page.evaluate("() => getComputedStyle(document.body).fontFamily")

        verify_res = verify_target(f"{base_url}/index.html", run_playwright=True, check_catalogue=False)
        assert verify_res.passed, f"Expected prototype HTTP verification to pass, got {verify_res.errors}"
        file_verify_res = verify_target(proto_html, run_playwright=True, check_catalogue=False)
        assert file_verify_res.passed, f"Expected standalone HTML verification to pass, got {file_verify_res.errors}"
    finally:
        server.shutdown()
        server.server_close()


def test_prototype_server_supports_explicit_assets_dir_override(tmp_path: Path):
    proto_dir = tmp_path / "proto"
    proto_dir.mkdir()
    (proto_dir / "page.html").write_text("<p>Hi</p>", encoding="utf-8")

    custom_assets = tmp_path / "custom-assets"
    (custom_assets / "css").mkdir(parents=True)
    (custom_assets / "css" / "sk-design-system.css").write_text("/* custom override */\n", encoding="utf-8")

    server, base_url = start_prototype_server(proto_dir, assets_dir=custom_assets)
    try:
        with urllib.request.urlopen(f"{base_url}/assets/css/sk-design-system.css", timeout=5) as resp:
            assert resp.status == 200
            assert "custom override" in resp.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
