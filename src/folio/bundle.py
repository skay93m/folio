"""Deterministic static release bundler with atomic staging (#153, #155)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from folio.catalogue import (
    build_catalogue_detail_page,
    build_catalogue_page,
    get_catalogue_entries,
    validate_catalogue,
)
from folio.fixtures import PATTERN_KEYS, PATTERN_LABELS, get_pattern_page
from folio.renderer import render_static

STATIC_SOURCE_DIR = Path(__file__).resolve().parent / "static" / "folio"

DIST_PAGE_FILES: dict[str, str] = {
    "launchpad": "index.html",
    "homepage": "homepage.html",
    "reading": "reading.html",
    "dashboard": "dashboard.html",
    "search": "search.html",
    "work": "work.html",
    "queue": "queue.html",
}


@dataclass(frozen=True, slots=True)
class BuildManifest:
    """Typed representation of dist/manifest.json."""

    version: str
    git_sha: str
    bootstrap_version: str
    load_order: tuple[str, ...]
    fonts: tuple[str, ...]
    licences: tuple[str, ...]
    assets: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "git_sha": self.git_sha,
            "bootstrap_version": self.bootstrap_version,
            "load_order": list(self.load_order),
            "fonts": list(self.fonts),
            "licences": list(self.licences),
            "assets": self.assets,
        }


def resolve_git_sha(repo_dir: Path | None = None) -> str:
    """Resolve current Git HEAD SHA or fall back to 'unknown'."""
    target = repo_dir or Path(__file__).resolve().parent.parent.parent
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dist_gallery_nav(active_key: str, *, prefix: str = "") -> dict[str, object]:
    links = [
        {
            "key": key,
            "label": label,
            "href": f"{prefix}{DIST_PAGE_FILES[key]}",
            "active": key == active_key,
        }
        for key, label in PATTERN_LABELS
    ]
    links.append(
        {
            "key": "elements",
            "label": "Design-system elements",
            "href": f"{prefix}elements.html",
            "active": active_key == "elements",
        }
    )
    return {
        "catalogue_href": f"{prefix}catalogue.html",
        "pattern_links": links,
    }


def _atomic_swap(staging_dir: Path, output_dir: Path) -> None:
    if not output_dir.exists():
        staging_dir.rename(output_dir)
        return
    backup_dir = output_dir.parent / f".{output_dir.name}.backup-{uuid.uuid4().hex[:8]}"
    output_dir.rename(backup_dir)
    try:
        staging_dir.rename(output_dir)
    except Exception:
        if not output_dir.exists() and backup_dir.exists():
            backup_dir.rename(output_dir)
        raise
    else:
        shutil.rmtree(backup_dir, ignore_errors=True)


def build_release(
    output_dir: Path | str,
    version: str,
    *,
    git_sha: str | None = None,
) -> BuildManifest:
    """Build a deterministic static release bundle atomically into output_dir."""
    if not version or not version.strip():
        raise ValueError("version must not be empty")

    validate_catalogue()

    dest = Path(output_dir).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = dest.parent / f".{dest.name}.staging-{uuid.uuid4().hex[:8]}"
    resolved_sha = git_sha if git_sha is not None else resolve_git_sha()

    try:
        staging.mkdir(parents=True, exist_ok=False)
        assets_dir = staging / "assets"
        shutil.copytree(STATIC_SOURCE_DIR, assets_dir)

        root_hrefs: dict[str, str] = {
            **DIST_PAGE_FILES,
            "work-journal": "work.html",
            "work-queues": "queue.html",
            "elements": "elements.html",
        }

        for key in PATTERN_KEYS:
            page = get_pattern_page(key, page_hrefs=root_hrefs)
            extra: dict[str, Any] = {}
            if not getattr(page, "is_stage1_shell", False):
                extra = {
                    "gallery_nav": _dist_gallery_nav(key),
                    "show_print_selector": True,
                }
            html = render_static(
                page,
                static_prefix="assets/",
                extra_context=extra,
            )
            (staging / DIST_PAGE_FILES[key]).write_text(html, encoding="utf-8")

        catalogue_page = build_catalogue_page(
            detail_prefix="catalogue",
            pattern_hrefs=root_hrefs,
        )
        cat_extra = {
            "gallery_nav": _dist_gallery_nav("elements"),
            "show_print_selector": True,
        }
        cat_html = render_static(
            catalogue_page,
            static_prefix="assets/",
            extra_context=cat_extra,
        )
        (staging / "elements.html").write_text(cat_html, encoding="utf-8")
        (staging / "catalogue.html").write_text(cat_html, encoding="utf-8")

        catalogue_dir = staging / "catalogue"
        catalogue_dir.mkdir(parents=True, exist_ok=True)
        for entry in get_catalogue_entries():
            detail_page = build_catalogue_detail_page(
                entry.id,
                back_href="../catalogue.html",
                home_href="../index.html",
            )
            # Rewrite pattern_links gallery_hrefs relative to catalogue/<slug>.html
            rewritten_links = tuple(
                type(pat)(
                    key=pat.key,
                    name=pat.name,
                    purpose=pat.purpose,
                    maturity=pat.maturity,
                    ownership_note=pat.ownership_note,
                    dataclass_path=pat.dataclass_path,
                    template_name=pat.template_name,
                    entry_ids=pat.entry_ids,
                    gallery_href=f"../{root_hrefs[pat.key]}",
                )
                for pat in detail_page.rendered_entry.pattern_links
            )
            detail_page = type(detail_page)(
                title=detail_page.title,
                eyebrow=detail_page.eyebrow,
                rendered_entry=type(detail_page.rendered_entry)(
                    entry=detail_page.rendered_entry.entry,
                    rendered_html=detail_page.rendered_entry.rendered_html,
                    snippet=detail_page.rendered_entry.snippet,
                    detail_href=f"{entry.id}.html",
                    pattern_links=rewritten_links,
                ),
                back_href="../catalogue.html",
                home_href="../index.html",
                home_aria_label=detail_page.home_aria_label,
                theme=detail_page.theme,
                print_mode=detail_page.print_mode,
                show_theme_toggle=detail_page.show_theme_toggle,
            )
            detail_html = render_static(
                detail_page,
                static_prefix="../assets/",
                extra_context={
                    "gallery_nav": _dist_gallery_nav("elements", prefix="../"),
                    "show_print_selector": True,
                },
            )
            (catalogue_dir / f"{entry.id}.html").write_text(detail_html, encoding="utf-8")

        asset_entries: dict[str, dict[str, Any]] = {}
        fonts: list[str] = []
        licences: list[str] = []
        for file_path in sorted(staging.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(staging).as_posix()
            if rel == "manifest.json":
                continue
            asset_entries[rel] = {
                "sha256": _sha256_file(file_path),
                "size": file_path.stat().st_size,
            }
            if rel.startswith("assets/fonts/") and rel.endswith(".ttf"):
                fonts.append(rel)
            if rel.endswith("LICENSE") or rel.endswith("OFL.txt"):
                licences.append(rel)

        manifest = BuildManifest(
            version=version,
            git_sha=resolved_sha,
            bootstrap_version="5.3.9",
            load_order=(
                "assets/vendor/bootstrap.min.css",
                "assets/css/sk-design-system.css",
                "assets/vendor/bootstrap.bundle.min.js",
                "assets/js/folio.js",
            ),
            fonts=tuple(sorted(fonts)),
            licences=tuple(sorted(licences)),
            assets=asset_entries,
        )
        (staging / "manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _atomic_swap(staging, dest)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
