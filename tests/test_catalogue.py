"""Slice 3 tests: Single-source catalogue (#156, #157) and deterministic validation."""

from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.test import Client

from folio.catalogue import (
    ELEMENT_GROUPS,
    PATTERN_INVENTORIES,
    CatalogueEntry,
    CatalogueValidationError,
    PatternInventory,
    build_catalogue_detail_page,
    build_catalogue_page,
    build_class_index,
    get_catalogue_entries,
    get_catalogue_entry,
    render_entry_example,
    validate_catalogue,
)


def test_primary_action_single_source_example_and_snippet():
    entry = get_catalogue_entry("primary-action")
    assert entry.group == "forms"
    assert entry.maturity == "Reference"
    assert "folio==0.2.0" in entry.release_dependency
    assert entry.constraints
    assert "work-queues" in entry.used_in_patterns

    rendered = render_entry_example(entry)
    direct = render_to_string(entry.template_name, entry.context).strip()
    assert rendered == direct
    assert 'class="btn btn-primary"' in rendered
    assert "Review work" in rendered


def test_all_six_groups_and_seven_pattern_inventories_valid():
    validate_catalogue()
    entries = get_catalogue_entries()
    groups_covered = {entry.group for entry in entries}
    assert groups_covered == set(ELEMENT_GROUPS.keys())
    assert set(ELEMENT_GROUPS.keys()) == {
        "foundations",
        "layout",
        "content",
        "forms",
        "navigation",
        "feedback",
    }
    assert set(PATTERN_INVENTORIES.keys()) == {
        "launchpad",
        "homepage",
        "reading",
        "dashboard",
        "search",
        "work-journal",
        "work-queues",
    }
    assert "the consuming application" in PATTERN_INVENTORIES["work-journal"].ownership_note
    assert "Consuming application" in PATTERN_INVENTORIES["work-queues"].ownership_note


def test_validate_catalogue_rejects_negative_fixtures():
    valid_entries = get_catalogue_entries()
    valid_patterns = tuple(PATTERN_INVENTORIES.values())

    # 1. Duplicate entry ID
    dup_entries = valid_entries + (valid_entries[0],)
    with pytest.raises(CatalogueValidationError, match="Duplicate"):
        validate_catalogue(entries=dup_entries, patterns=valid_patterns)

    # 2. Missing template
    missing_tpl_entry = CatalogueEntry(
        id="broken-tpl",
        title="Broken template",
        group="forms",
        purpose="Test missing template.",
        constraints=("None",),
        maturity="Reference",
        production_owner="Folio",
        release_dependency="folio==0.2.0",
        template_name="folio/includes/elements/does_not_exist.html",
        python_usage="Launchpad(...)",
        used_in_patterns=("launchpad",),
    )
    with pytest.raises(CatalogueValidationError, match="Template not found"):
        validate_catalogue(
            entries=valid_entries + (missing_tpl_entry,),
            patterns=valid_patterns,
        )

    # 3. Broken bidirectional pattern-inventory link
    orphan_pattern = PatternInventory(
        key="launchpad",
        name="Launchpad",
        purpose="Choose one activity.",
        maturity="Reference",
        ownership_note="Consuming application uses launchpad.",
        dataclass_path="folio.contracts.Launchpad",
        template_name="folio/patterns/launchpad.html",
        entry_ids=("non-existent-entry",),
    )
    with pytest.raises(CatalogueValidationError, match="non-existent-entry"):
        validate_catalogue(
            entries=valid_entries,
            patterns=(orphan_pattern,) + valid_patterns[1:],
        )

    # 4. Empty pattern inventory
    empty_pattern = PatternInventory(
        key="launchpad",
        name="Launchpad",
        purpose="Choose one activity.",
        maturity="Reference",
        ownership_note="Consuming application uses launchpad.",
        dataclass_path="folio.contracts.Launchpad",
        template_name="folio/patterns/launchpad.html",
        entry_ids=(),
    )
    with pytest.raises(CatalogueValidationError, match="empty"):
        validate_catalogue(
            entries=valid_entries,
            patterns=(empty_pattern,) + valid_patterns[1:],
        )


@pytest.mark.django_db
def test_catalogue_views_render_single_source_markup_and_snippet():
    client = Client()
    index_resp = client.get("/catalogue/")
    assert index_resp.status_code == 200
    index_body = index_resp.content.decode("utf-8")
    for group_title in ELEMENT_GROUPS.values():
        assert group_title in index_body
    for pattern in PATTERN_INVENTORIES.values():
        assert pattern.name in index_body

    detail_resp = client.get("/catalogue/primary-action/")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.content.decode("utf-8")
    assert "Primary action" in detail_body
    assert "&lt;button type=&quot;button&quot; class=&quot;btn btn-primary&quot;&gt;Review work&lt;/button&gt;" in detail_body
    assert '<button type="button" class="btn btn-primary">Review work</button>' in detail_body


@pytest.mark.django_db
def test_ten_colour_families_all_present_in_preview_and_snippet():
    expected_families = (
        "Coral",
        "Teal",
        "Gold",
        "Blue",
        "Slate",
        "Violet",
        "Rose",
        "Cyan",
        "Orange",
        "Leaf",
    )
    entry = get_catalogue_entry("ten-colour-families")
    rendered = render_entry_example(entry)
    for family in expected_families:
        assert f"palette-sample-{family.lower()}" in rendered
        assert family in rendered

    client = Client()
    detail_resp = client.get("/catalogue/ten-colour-families/")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.content.decode("utf-8")
    for family in expected_families:
        assert f"palette-sample-{family.lower()}" in detail_body
        assert f"&lt;div class=&quot;palette-sample palette-sample-{family.lower()}&quot;&gt;{family}" in detail_body


def test_catalogue_builders_accept_home_href_and_pattern_hrefs():
    hrefs = {"search": "search.html", "work-journal": "work.html", "work-queues": "queue.html"}
    cat_page = build_catalogue_page(detail_prefix="catalogue", home_href="index.html", pattern_hrefs=hrefs)
    assert cat_page.home_href == "index.html"
    detail_page = build_catalogue_detail_page(
        "primary-action",
        detail_prefix="",
        back_href="../catalogue.html",
        home_href="../index.html",
        pattern_hrefs={k: f"../{v}" for k, v in hrefs.items()},
    )
    assert detail_page.home_href == "../index.html"
    assert detail_page.rendered_entry.detail_href == "primary-action.html"
    assert {p.gallery_href for p in detail_page.rendered_entry.pattern_links} == {
        "../search.html",
        "../work.html",
        "../queue.html",
    }


def test_pattern_templates_include_shared_element_partials():
    templates_dir = Path(__file__).resolve().parent.parent / "src" / "folio" / "templates" / "folio" / "patterns"
    expected_includes = {
        "launchpad.html": ("folio/includes/elements/status_badge.html",),
        "dashboard.html": ("folio/includes/elements/status_badge.html",),
        "search.html": (
            "folio/includes/elements/labelled_input.html",
            "folio/includes/elements/primary_action.html",
            "folio/includes/elements/status_badge.html",
            "folio/includes/elements/empty_state.html",
        ),
        "work_journal.html": (
            "folio/includes/elements/labelled_input.html",
            "folio/includes/elements/primary_action.html",
            "folio/includes/elements/status_badge.html",
        ),
        "work_queue.html": (
            "folio/includes/elements/labelled_input.html",
            "folio/includes/elements/primary_action.html",
            "folio/includes/elements/status_badge.html",
            "folio/includes/elements/empty_state.html",
        ),
    }
    for filename, partials in expected_includes.items():
        source = (templates_dir / filename).read_text(encoding="utf-8")
        for partial in partials:
            assert partial in source, f"{filename} must include {partial}"


def test_build_class_index_exposes_classes_layout_primitives_and_tokens():
    index = build_class_index()

    assert index["version"]
    classes = index["classes"]
    assert isinstance(classes, list)
    assert classes == sorted(set(classes))
    for required_cls in (
        "sk-logo",
        "sk-spatial-shell",
        "sk-section-block",
        "page-shell",
        "launchpad",
        "status",
        "status-success",
        "btn-primary",
        "surface",
        "eyebrow",
    ):
        assert required_cls in classes
    # Must not leak filename extensions from url(...) or decimal values
    assert "ttf" not in classes
    assert "css" not in classes

    primitives = index["layout_primitives"]
    for key in (
        "page-shell",
        "launchpad",
        "sk-spatial-shell",
        "reading-layout",
        "dashboard-grid",
        "metrics-grid",
        "search-layout",
        "work-layout",
        "queue-layout",
        "catalogue-grid",
        "surface",
    ):
        assert key in primitives
        assert primitives[key]["role"]

    tokens = index["tokens"]
    assert tokens["sk"]["--sk-paper"] == {"light": "#f7f6f2", "dark": "#17191c"}
    assert tokens["sk"]["--sk-coral"]["light"] == "#ff4f40"
    assert "--sk-block-gap" in tokens["sk"]
    assert "--bs-body-bg" in tokens["bootstrap"]
    assert tokens["palette"]["brand"] == "#FF4F40"
    assert len(tokens["palette"]["families"]) == 10

    assert "primary-action" in index["elements"]
    assert "btn-primary" in index["elements"]["primary-action"]["classes"]
    assert set(index["patterns"].keys()) == set(PATTERN_INVENTORIES.keys())
