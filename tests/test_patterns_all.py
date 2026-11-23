"""Slice 2 tests: All 7 pattern contracts, validations, fixtures, and templates."""

import re

import pytest
from django.test import Client

import folio
from folio.contracts import (
    AttentionItem,
    Dashboard,
    Homepage,
    HomepageNoteItem,
    JournalPreviewEntry,
    MarginNote,
    MetricCard,
    ProvenanceEntry,
    QueueCategory,
    QueueRow,
    Reading,
    ReadingRelation,
    ReadingSection,
    SearchFacet,
    SearchFacetValue,
    SearchFilter,
    SearchIndex,
    SearchRecord,
    SocialLink,
    TrendSeries,
    WorkJournal,
    WorkQueue,
    WorkStep,
)
from folio.fixtures import PATTERN_KEYS, get_pattern_page
from folio.navigation import resolve_pattern_key


def test_faux_serif_tags_rejected_in_reading_and_homepage_prose():
    with pytest.raises(ValueError, match="faux-style Serif"):
        Reading(
            eyebrow="Working note · Design",
            title="Clean prose check",
            meta=("22 November 2026",),
            abstract="Contains <em>forbidden</em> emphasis.",
            sections=(
                ReadingSection(
                    id="sec-1",
                    heading="First section",
                    paragraphs=("Clean paragraph.",),
                ),
            ),
        )

    with pytest.raises(ValueError, match="faux-style Serif"):
        ReadingSection(
            id="sec-1",
            heading="First section",
            paragraphs=("Contains <strong>bold</strong> tag.",),
        )

    with pytest.raises(ValueError, match="faux-style Serif"):
        Homepage(
            author_name="Sample Author",
            headline="Role · Focus",
            statement_paragraphs=("Clean paragraph.",),
            now_heading="Now",
            now_paragraphs=("Working.",),
            notes_heading="Notes",
            notes_intro="Includes <strong>bold</strong> tag.",
            notes=(),
            long_form_heading="Long-form notes",
            long_form_paragraphs=("Drafting.",),
            socials=(),
        )

    with pytest.raises(ValueError, match="faux-style Serif"):
        Homepage(
            author_name="Sample Author",
            headline="Role · Focus",
            statement_paragraphs=("Includes <em>italic</em> tag.",),
            now_heading="Now",
            now_paragraphs=("Working.",),
            notes_heading="Notes",
            notes_intro="Short notes.",
            notes=(),
            long_form_heading="Long-form notes",
            long_form_paragraphs=("Drafting.",),
            socials=(),
        )


def test_required_aria_labels_and_semantic_roles_validated_across_patterns():
    with pytest.raises(ValueError, match="aria_label"):
        SocialLink(label="GitHub", href="https://github.com/example", icon="github", aria_label="")

    with pytest.raises(ValueError, match="semantic role"):
        MetricCard(label="Done", value="10", comparison="Up 2", role="critical")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="semantic role"):
        SearchRecord(
            title="Item",
            record_type="note",
            topic="Design",
            status="Active",
            status_role="unknown",  # type: ignore[arg-type]
            excerpt="Summary.",
            href="?page=reading",
        )

    with pytest.raises(ValueError, match="semantic role"):
        QueueRow(
            id="HK-1",
            queue="housekeeping",
            title="Check queue",
            status="Ready",
            status_role="bad",  # type: ignore[arg-type]
            priority="Normal",
            owner="Owner",
            age="1 day",
            context="Context.",
        )

    with pytest.raises(ValueError, match="chart_aria_label"):
        Dashboard(
            eyebrow="Dashboard",
            title="Overview",
            intro="Check direction.",
            periods=(
                TrendSeries(
                    period_key="week",
                    period_label="This week",
                    labels=("Mon", "Tue"),
                    completed=(1, 2),
                    arrived=(1, 1),
                    metrics=(MetricCard("Done", "3", "On track", "success"),),
                ),
            ),
            selected_period="week",
            chart_title="Work flow",
            chart_subtitle="Sample",
            chart_aria_label=" ",
            attention_heading="Attention",
            attention_items=(
                AttentionItem("Check", "Desc", "Open", "?page=queue", "warning"),
            ),
            direction_eyebrow="Direction",
            direction_text="Stay focused.",
        )

    with pytest.raises(ValueError, match="table_caption"):
        WorkQueue(
            eyebrow="Queues",
            title="Work queues",
            intro="Review items.",
            categories=(QueueCategory("housekeeping", "Daily housekeeping", "Routine."),),
            selected_category="housekeeping",
            rows=(),
            table_caption="",
        )


def test_reading_conditionally_omits_empty_relations():
    base_reading = Reading(
        eyebrow="Working note · Design",
        title="Quiet interface",
        meta=("22 November 2026", "Draft"),
        abstract="Short abstract.",
        provenance=(ProvenanceEntry("AI contribution", "Sample provenance."),),
        sections=(
            ReadingSection(
                id="claim",
                heading="The claim",
                paragraphs=("First paragraph.",),
            ),
        ),
        margin_notes=(MarginNote("1 · Note", "Margin detail."),),
        back_href="?page=homepage",
    )
    html_without_relations = folio.render_static(base_reading)
    assert "sk-reading-relations" not in html_without_relations
    assert "Back to homepage" in html_without_relations
    assert 'class="abstract"' in html_without_relations
    assert 'class="article-provenance"' in html_without_relations

    populated_reading = Reading(
        eyebrow=base_reading.eyebrow,
        title=base_reading.title,
        meta=base_reading.meta,
        abstract=base_reading.abstract,
        provenance=base_reading.provenance,
        sections=base_reading.sections,
        margin_notes=base_reading.margin_notes,
        backlinks=(ReadingRelation("Homepage", "?page=homepage"),),
        similar_links=(ReadingRelation("Reference", "https://example.com", external=True),),
    )
    html_with_relations = folio.render_static(populated_reading)
    assert "sk-reading-relations" in html_with_relations
    assert "Backlinks" in html_with_relations
    assert "Similar links" in html_with_relations


@pytest.mark.django_db
def test_all_seven_fixtures_render_through_gallery_view():
    assert set(PATTERN_KEYS) == {
        "launchpad",
        "homepage",
        "reading",
        "dashboard",
        "search",
        "work",
        "queue",
    }
    client = Client()
    for key in PATTERN_KEYS:
        page = get_pattern_page(key)
        static_html = folio.render_static(page)
        assert "prototype-controls" not in static_html
        response = client.get(f"/?page={key}")
        assert response.status_code == 200
        body = response.content.decode("utf-8")
        assert page.title in body or getattr(page, "author_name", "") in body

    homepage_html = folio.render_static(get_pattern_page("homepage"))
    assert "sk-spatial-shell" in homepage_html
    assert "sk-gwern-folio" in homepage_html
    assert "sk-site-footer" in homepage_html
    assert "sk-header-socials" in homepage_html


def test_reading_footnotes_always_render_unique_non_empty_ids():
    reading = Reading(
        eyebrow="Working note · Design",
        title="Footnote ID check",
        meta=("22 November 2026",),
        abstract="Short abstract.",
        sections=(
            ReadingSection(
                id="sec-1",
                heading="Section one",
                paragraphs=("Paragraph one.",),
            ),
        ),
        margin_notes=(
            MarginNote("1 · Implicit first", "First margin note."),
            MarginNote("2 · Explicit", "Second margin note.", footnote_id="custom-fn-2"),
            MarginNote("3 · Implicit third", "Third margin note."),
        ),
    )
    html = folio.render_static(reading)
    ids = re.findall(r'<p id="([^"]*)" class="article-footnote">', html)
    assert ids == ["footnote-1", "custom-fn-2", "footnote-3"]
    assert all(ids)
    assert len(set(ids)) == len(ids)


def test_search_index_work_journal_and_work_queue_ssr_state():
    # 1. SearchIndex: facet-driven <select> options and SSR active_filters
    search_page = SearchIndex(
        eyebrow="Search",
        title="Search records",
        intro="Filter records.",
        facets=(
            SearchFacet("topic", (SearchFacetValue("Design", 1),)),
            SearchFacet("status", (SearchFacetValue("Active", 1),)),
        ),
        modes=("Notes", "Observations"),
        selected_mode="Notes",
        records=(
            SearchRecord(
                title="Design note",
                record_type="note",
                topic="Design",
                status="Active",
                status_role="success",
                excerpt="Summary.",
                href="?page=reading",
            ),
        ),
        active_filters=(SearchFilter("topic", "contains", "Des"),),
    )
    search_html = folio.render_static(search_page)
    assert '<option value="topic">topic</option>' in search_html
    assert '<option value="status">status</option>' in search_html
    assert '<option value="type">type</option>' not in search_html
    assert '<option value="topic" selected>topic</option>' in search_html
    assert '<option value="contains" selected>contains</option>' in search_html
    assert 'value="Des"' in search_html

    # 2. WorkJournal: #work-count reflects scope == "work", not total entries
    journal_page = WorkJournal(
        eyebrow="Work",
        title="Work journal",
        intro="Track steps.",
        task_heading="Task",
        task_description="Do the work.",
        status_badges=(("In progress", "info"),),
        steps=(WorkStep("s1", "Step 1", "First step."),),
        journal_date_label="Journal",
        journal_path="journals/today.md",
        work_scope_label="[work/test]",
        general_scope_label="[general]",
        entries=(
            JournalPreviewEntry(scope="work", text="Work entry."),
            JournalPreviewEntry(scope="general", text="General entry 1."),
            JournalPreviewEntry(scope="general", text="General entry 2."),
        ),
    )
    journal_html = folio.render_static(journal_page)
    assert '<span id="all-count">3</span>' in journal_html
    assert '<span id="work-count">1</span>' in journal_html

    # 3. WorkQueue: accurate SSR category_counts and consistent data-queue-name
    queue_page = get_pattern_page("queue")
    queue_html = folio.render_static(queue_page)
    assert 'aria-label="3 outstanding items">3</span>' in queue_html
    assert 'aria-label="2 outstanding items">2</span>' in queue_html
    assert 'data-queue="housekeeping" data-queue-name="Daily housekeeping"' in queue_html
    assert 'data-queue="analysis" data-queue-name="Analysis needed"' in queue_html
    assert '<span id="queue-count" role="status">3 items in this view</span>' in queue_html

    # 4. Shared pattern key alias resolution
    assert resolve_pattern_key("writing") == "work"
    assert resolve_pattern_key("index") == "search"
    assert resolve_pattern_key("unknown", default="launchpad") == "launchpad"
