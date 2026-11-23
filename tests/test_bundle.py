"""Slice 4 tests: Deterministic release bundler and atomic staging."""

import json
from pathlib import Path

import pytest

from folio.bundle import BuildManifest, build_release


def test_build_release_writes_deterministic_manifest_and_assets(tmp_path: Path):
    out1 = tmp_path / "dist-a"
    out2 = tmp_path / "dist-b"

    m1 = build_release(out1, version="v0.1.0", git_sha="abc1234")
    m2 = build_release(out2, version="v0.1.0", git_sha="abc1234")

    assert isinstance(m1, BuildManifest)
    manifest1 = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
    manifest2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))

    assert manifest1 == manifest2
    assert manifest1["version"] == "v0.1.0"
    assert manifest1["git_sha"] == "abc1234"
    assert manifest1["bootstrap_version"] == "5.3.9"
    assert manifest1["load_order"] == [
        "assets/vendor/bootstrap.min.css",
        "assets/css/sk-design-system.css",
        "assets/vendor/bootstrap.bundle.min.js",
        "assets/js/folio.js",
    ]
    assert "assets/vendor/BOOTSTRAP-LICENSE" in manifest1["licences"]
    assert "assets/fonts/IBMPlexSans.ttf" in manifest1["fonts"]

    for rel_path in (
        "index.html",
        "homepage.html",
        "reading.html",
        "dashboard.html",
        "search.html",
        "work.html",
        "queue.html",
        "elements.html",
        "catalogue.html",
        "catalogue/primary-action.html",
        "assets/css/sk-design-system.css",
        "assets/js/folio.js",
        "assets/approved-palette.json",
    ):
        assert (out1 / rel_path).is_file(), f"Missing {rel_path}"
        assert rel_path in manifest1["assets"]
        assert (out1 / rel_path).read_bytes() == (out2 / rel_path).read_bytes()

    homepage_html = (out1 / "homepage.html").read_text(encoding="utf-8")
    assert 'href="assets/css/sk-design-system.css"' in homepage_html
    assert 'href="/static/' not in homepage_html

    for cat_file in ("catalogue.html", "elements.html"):
        cat_html = (out1 / cat_file).read_text(encoding="utf-8")
        assert 'class="sk-logo" href="index.html"' in cat_html
        assert "/?page=launchpad" not in cat_html

    detail_html = (out1 / "catalogue/primary-action.html").read_text(encoding="utf-8")
    assert 'class="sk-logo" href="../index.html"' in detail_html
    assert 'href="../search.html"' in detail_html
    assert 'href="../work.html"' in detail_html
    assert 'href="../queue.html"' in detail_html
    assert "/?page=" not in detail_html

    reading_html = (out1 / "reading.html").read_text(encoding="utf-8")
    assert 'id="" class="article-footnote"' not in reading_html
    assert 'id="footnote-1" class="article-footnote"' in reading_html


def test_build_release_preserves_prior_output_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    out = tmp_path / "dist"
    build_release(out, version="v0.1.0", git_sha="goodsha")
    sentinel = out / "manifest.json"
    original_bytes = sentinel.read_bytes()

    import folio.bundle as bundle_mod

    def boom(*args, **kwargs):
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr(bundle_mod, "render_static", boom)
    with pytest.raises(RuntimeError, match="simulated render failure"):
        build_release(out, version="v0.2.0", git_sha="badsha")

    assert sentinel.read_bytes() == original_bytes
    assert json.loads(sentinel.read_text(encoding="utf-8"))["version"] == "v0.1.0"
