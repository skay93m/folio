"""Slice 3 tests: Single-source catalogue (#156, #157) and deterministic validation."""

import pytest
from django.template.loader import render_to_string
from django.test import Client

from folio.catalogue import (
    ELEMENT_GROUPS,
    PATTERN_INVENTORIES,
    CatalogueEntry,
    CatalogueValidationError,
    PatternInventory,
    get_catalogue_entries,
    get_catalogue_entry,
    render_entry_example,
    validate_catalogue,
)


def test_primary_action_single_source_example_and_snippet():
    entry = get_catalogue_entry("primary-action")
    assert entry.group == "forms"
    assert entry.maturity == "Reference"
    assert "folio==0.1.0" in entry.release_dependency
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
    assert "Placemat" in PATTERN_INVENTORIES["work-journal"].ownership_note
    assert "Cockpit" in PATTERN_INVENTORIES["work-queues"].ownership_note


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
        release_dependency="folio==0.1.0",
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
        ownership_note="Cockpit uses launchpad.",
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
        ownership_note="Cockpit uses launchpad.",
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
