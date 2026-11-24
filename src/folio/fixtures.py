"""Git-tracked sample fixtures for all seven SK Design System page patterns."""

from __future__ import annotations

from typing import Any

from folio.contracts import (
    AttentionItem,
    Dashboard,
    Homepage,
    HomepageNoteItem,
    JournalPreviewEntry,
    Launchpad,
    LaunchpadCard,
    MarginNote,
    MetricCard,
    PrintMode,
    ProvenanceEntry,
    QueueCategory,
    QueueRow,
    Reading,
    ReadingRelation,
    ReadingSection,
    SearchFacet,
    SearchFacetValue,
    SearchIndex,
    SearchRecord,
    SocialLink,
    ThemeMode,
    TrendSeries,
    WorkJournal,
    WorkQueue,
    WorkStep,
)
from folio.navigation import PATTERN_KEYS, resolve_pattern_key


def build_launchpad(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> Launchpad:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return Launchpad(
        title="Launchpad",
        intro="Choose one activity and give it your full attention.",
        cards=(
            LaunchpadCard(
                title="Overview",
                description="See progress, changes and the work that needs your attention.",
                href=hrefs.get("dashboard", "?page=dashboard"),
            ),
            LaunchpadCard(
                title="Work session",
                description="Focus on a task and capture useful thoughts as you go.",
                href=hrefs.get("work", "?page=work"),
            ),
            LaunchpadCard(
                title="Work queues",
                description="Review incoming work and move the next useful item forward.",
                href=hrefs.get("queue", "?page=queue"),
            ),
        ),
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


def build_homepage(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> Homepage:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return Homepage(
        title="SK Editorial · Reference Homepage",
        author_name="SK Editorial",
        headline="Design Systems · Plain-Text Notebooks · Reproducible Software",
        statement_paragraphs=(
            "A calm, cardless homepage built on the SK Design System foundations: open paper canvas, left-aligned IBM Plex Sans headings, and clean IBM Plex Serif prose.",
        ),
        now_heading="Now",
        now_paragraphs=(
            "Publishing shared UI foundations, typed pattern contracts, and deterministic static release bundles for connected applications.",
        ),
        notes_heading="Notes",
        notes_intro="Working notes demonstrating the Stage 1 editorial listing and Reading pattern handoff.",
        notes=(
            HomepageNoteItem(
                slug="quiet-interface",
                title="A quiet interface leaves room for thought",
                date="22 November 2026",
                summary="How a clear starting point, restrained controls, and contextual references support sustained reading.",
                href=hrefs.get("reading", "?page=reading"),
            ),
            HomepageNoteItem(
                slug="single-source-catalogue",
                title="Single-source pattern examples",
                date="21 November 2026",
                summary="Keeping live previews, reusable markup, and verification fixtures bound to one template.",
                href=hrefs.get("reading", "?page=reading"),
            ),
        ),
        long_form_heading="Long-form notes",
        long_form_paragraphs=(
            "Longer essays mature progressively from rough seedlings to revised editions, recording provenance and open questions alongside the main text.",
        ),
        socials=(
            SocialLink("Email", "mailto:hello@example.com", "email", "Email"),
            SocialLink("GitHub", "https://github.com/skay93m/folio", "github", "GitHub"),
            SocialLink("LinkedIn", "https://www.linkedin.com/", "linkedin", "LinkedIn"),
            SocialLink("ResearchGate", "https://www.researchgate.net/", "researchgate", "ResearchGate"),
            SocialLink("ORCID", "https://orcid.org/", "orcid", "ORCID"),
        ),
        home_href=hrefs.get("homepage", "?page=homepage"),
        theme=theme,
        print_mode=print_mode,
    )


def build_reading(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> Reading:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return Reading(
        eyebrow="Working note · Design",
        title="A quiet interface leaves room for thought.",
        meta=("Created 21 November 2026", "Updated 22 November 2026", "Developing"),
        abstract="A short exploration of how a clear starting point, useful context and restrained controls can support a longer train of thought.",
        provenance=(
            ProvenanceEntry(
                summary="AI contribution",
                detail="Sample editorial prose and reference layout assembled for the SK Design System gallery.",
            ),
            ProvenanceEntry(
                summary="Revision history",
                detail="22 November 2026 · Expanded the reading example with marginalia, boxed abstract, top provenance disclosures, and conditional relations.",
            ),
        ),
        sections=(
            ReadingSection(
                id="claim",
                heading="Start with the thought.",
                paragraphs=(
                    "When I open a workspace, I want a clear place to begin. A small set of meaningful choices gives me room to decide where my attention should go.",
                    "A reading page needs more context than a launchpad. I may want to check a reference, return to an earlier section, or follow a connection without forgetting the original claim.",
                ),
                blockquote="Give the writing room. Bring the next useful step within reach.",
                blockquote_variant="thought",
                blockquote_eyebrow="Working principle",
            ),
            ReadingSection(
                id="revision",
                heading="A useful revision.",
                paragraphs=(
                    "The first draft of a page often gives every useful idea a visible control. Revising it means asking when each of those controls actually helps.",
                    "This formulation leaves room for different page purposes. A queue can reveal status and ownership. A reading page can reveal sources and connections.",
                ),
                blockquote="Show a useful path forward. Keep the supporting detail close enough to find.",
                comparison=(
                    ("Launchpad", "Choose a destination. Keep the choices concise."),
                    ("Reading", "Follow a line of thought. Make its context available."),
                ),
                figure_caption="Figure 1. The same visual foundations support different levels of detail.",
            ),
            ReadingSection(
                id="evidence",
                heading="Keep the evidence available.",
                paragraphs=(
                    "A source should help me examine why I accepted a claim. A stable note address, a dated revision and a reference retained in context make that return easier.",
                    "The writing can remain unfinished while its status is clear. A future revision can strengthen the example or record a reason to change direction.",
                ),
                code_block="note -> claim -> source -> revision",
            ),
        ),
        margin_notes=(
            MarginNote(
                label="1 · Beside the claim",
                text="Minimalism should follow the task demands. A useful reference earns its space.",
                footnote_id="footnote-1",
            ),
            MarginNote(
                label="2 · Beside the evidence",
                text="Stable addresses and revisions support future reading.",
                footnote_id="footnote-2",
            ),
        ),
        backlinks=(
            ReadingRelation("Editorial Homepage pattern", hrefs.get("homepage", "?page=homepage")),
            ReadingRelation("Launchpad pattern", hrefs.get("launchpad", "?page=launchpad")),
        ),
        similar_links=(
            ReadingRelation("Gwern · Design of this website", "https://gwern.net/design", external=True),
            ReadingRelation("Gwern · About long-form notes", "https://gwern.net/about", external=True),
        ),
        back_href=hrefs.get("homepage", "?page=homepage"),
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


def build_dashboard(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> Dashboard:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return Dashboard(
        eyebrow="Dashboard",
        title="Choose the next direction.",
        intro="Compare incoming work, completed work and the items that need intervention.",
        periods=(
            TrendSeries(
                period_key="week",
                period_label="This week",
                labels=("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
                completed=(2, 4, 3, 5, 4, 6, 4),
                arrived=(3, 3, 5, 4, 6, 4, 5),
                metrics=(
                    MetricCard("Completed work", "28", "4 more than last week", "success"),
                    MetricCard("Outstanding work", "9", "Ready or waiting for action", "info"),
                    MetricCard("Blocked items", "2", "Require a decision or context", "warning"),
                    MetricCard("Median age", "1.4 days", "Outstanding items", "neutral"),
                ),
            ),
            TrendSeries(
                period_key="month",
                period_label="This month",
                labels=("Week 1", "Week 2", "Week 3", "Week 4"),
                completed=(18, 22, 24, 28),
                arrived=(23, 25, 26, 30),
                metrics=(
                    MetricCard("Completed work", "92", "12 more than last month", "success"),
                    MetricCard("Outstanding work", "15", "Ready or waiting for action", "info"),
                    MetricCard("Blocked items", "3", "Require a decision or context", "warning"),
                    MetricCard("Median age", "2.1 days", "Outstanding items", "neutral"),
                ),
            ),
        ),
        selected_period="week",
        chart_title="Work moving through the system",
        chart_subtitle="Sample activity",
        chart_aria_label="Completed and incoming work over the selected period. Data is available in the table below.",
        attention_heading="Where attention helps",
        attention_items=(
            AttentionItem(
                title="Incoming work is outpacing completions.",
                description="Choose whether to reduce intake or make time for the oldest items.",
                action_label="Review the work queues",
                action_href=hrefs.get("queue", "?page=queue"),
                role="warning",
            ),
            AttentionItem(
                title="Two items need an unblock.",
                description="A decision or missing context is holding the next step.",
                action_label="Inspect blockers",
                action_href=hrefs.get("queue", "?page=queue"),
                role="error",
            ),
            AttentionItem(
                title="Three records need analysis.",
                description="Group related questions before starting another investigation.",
                action_label="Find related records",
                action_href=hrefs.get("search", "?page=search"),
                role="info",
            ),
        ),
        direction_eyebrow="Direction to consider",
        direction_text="Clear the oldest blocker before taking on another task.",
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


def build_search(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> SearchIndex:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    reading_href = hrefs.get("reading", "?page=reading")
    records = (
        SearchRecord(
            title="A quiet interface leaves room for thought",
            record_type="note",
            topic="Design",
            status="Developing",
            status_role="info",
            excerpt="A working claim about attention, navigation and making useful controls easy to find.",
            href=reading_href,
        ),
        SearchRecord(
            title="SK Design System principles",
            record_type="decision",
            topic="Design",
            status="Needs review",
            status_role="warning",
            excerpt="Foundations and patterns developed from real tasks, with coral as the brand anchor.",
            href=reading_href,
        ),
        SearchRecord(
            title="Daily housekeeping review",
            record_type="log",
            topic="Housekeeping",
            status="Active",
            status_role="success",
            excerpt="Items requiring attention after the latest housekeeping pass.",
            href=reading_href,
        ),
        SearchRecord(
            title="A useful choice explains its consequence",
            record_type="note",
            topic="Design",
            status="Developing",
            status_role="info",
            excerpt="Navigation benefits from enough context to make a meaningful choice.",
            href=reading_href,
        ),
        SearchRecord(
            title="Work queue handoff",
            record_type="decision",
            topic="Housekeeping",
            status="Needs review",
            status_role="warning",
            excerpt="A draft contract for incoming work, queue membership and resolution.",
            href=reading_href,
        ),
        SearchRecord(
            title="Learning through a short reflection",
            record_type="note",
            topic="Study",
            status="Active",
            status_role="success",
            excerpt="A note connecting deliberate practice with a useful account of what changed.",
            href=reading_href,
        ),
    )
    facets = []
    for field, attr in (("type", "record_type"), ("topic", "topic"), ("status", "status")):
        counts: dict[str, int] = {}
        for rec in records:
            val = getattr(rec, attr)
            counts[val] = counts.get(val, 0) + 1
        facets.append(
            SearchFacet(
                field=field,
                values=tuple(SearchFacetValue(v, c) for v, c in counts.items()),
            )
        )
    return SearchIndex(
        eyebrow="Index / search",
        title="Find the thread.",
        intro="Search record text and combine metadata filters to narrow a collection.",
        facets=tuple(facets),
        modes=("Notes", "Observations", "Relations"),
        selected_mode="Notes",
        records=records,
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


def build_work_journal(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> WorkJournal:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return WorkJournal(
        eyebrow="Work with journal",
        title="Review the next piece of work.",
        intro="Track what you are doing and keep your journal within reach.",
        task_heading="Prepare a useful handoff",
        task_description="Review the evidence, capture open questions and describe the next step clearly enough for someone to continue.",
        status_badges=(
            ("In progress", "info"),
            ("Memory-only preview", "neutral"),
        ),
        steps=(
            WorkStep(
                id="step-1",
                label="Read the current account",
                description="Understand the context and the decision already recorded.",
                completed=True,
            ),
            WorkStep(
                id="step-2",
                label="Check the supporting evidence",
                description="Follow the relevant sources and capture anything that changes your view.",
                completed=False,
            ),
            WorkStep(
                id="step-3",
                label="Record the next useful step",
                description="State the action, any dependency and the expected result.",
                completed=False,
            ),
        ),
        journal_date_label="Journal · 22 November",
        journal_path="journals/2026/11/2026-11-22.md",
        work_scope_label="[work/review]",
        general_scope_label="[general]",
        entries=(
            JournalPreviewEntry(
                scope="work",
                cue="Evidence check",
                text="Sample reflection scoped to this work item. Production persistence belongs to the consuming application.",
            ),
        ),
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


def build_work_queue(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> WorkQueue:
    hrefs = page_hrefs or {key: f"?page={key}" for key in PATTERN_KEYS}
    return WorkQueue(
        eyebrow="Work queues",
        title="Work queues",
        intro="Choose a queue, inspect the work and move the next useful item forward.",
        categories=(
            QueueCategory(
                key="housekeeping",
                name="Daily housekeeping",
                description="Review routine maintenance and the exceptions that need attention.",
            ),
            QueueCategory(
                key="analysis",
                name="Analysis needed",
                description="Investigations that need evidence, interpretation or a recommendation.",
            ),
            QueueCategory(
                key="github",
                name="GitHub unblocking",
                description="Issues waiting for a decision, clarification or missing prerequisite.",
            ),
        ),
        selected_category="housekeeping",
        rows=(
            QueueRow(
                id="HK-021",
                queue="housekeeping",
                title="Review the oldest pending housekeeping result",
                status="Ready",
                status_role="info",
                priority="Normal",
                owner="Owner",
                age="2 days",
                context="The daily pass recorded an exception that needs human review.",
            ),
            QueueRow(
                id="HK-022",
                queue="housekeeping",
                title="Check the source archive exceptions",
                status="Ready",
                status_role="info",
                priority="High",
                owner="Unassigned",
                age="1 day",
                context="Two references could not be verified in the sample maintenance report.",
            ),
            QueueRow(
                id="HK-023",
                queue="housekeeping",
                title="Confirm the next housekeeping window",
                status="Waiting",
                status_role="warning",
                priority="Normal",
                owner="Owner",
                age="4 hours",
                context="The next pass is waiting for an agreed time window.",
            ),
            QueueRow(
                id="AN-014",
                queue="analysis",
                title="Compare two accounts of the same design decision",
                status="Ready",
                status_role="info",
                priority="Normal",
                owner="Unassigned",
                age="1 day",
                context="The sources express different constraints. Review the evidence before proposing a direction.",
            ),
            QueueRow(
                id="AN-015",
                queue="analysis",
                title="Summarise the evidence for a proposed pattern",
                status="Ready",
                status_role="info",
                priority="Normal",
                owner="Owner",
                age="3 hours",
                context="A new pattern needs a concise account of the user need it serves.",
            ),
            QueueRow(
                id="GH-008",
                queue="github",
                title="Clarify the missing acceptance condition",
                status="Ready",
                status_role="info",
                priority="High",
                owner="Owner",
                age="3 days",
                context="The linked work needs a clear completion condition before it can proceed.",
            ),
            QueueRow(
                id="GH-009",
                queue="github",
                title="Confirm the dependency handoff",
                status="Waiting",
                status_role="warning",
                priority="Normal",
                owner="Unassigned",
                age="1 day",
                context="The downstream work is waiting for an agreed input from another ticket.",
            ),
        ),
        home_href=hrefs.get("launchpad", "?page=launchpad"),
        theme=theme,
        print_mode=print_mode,
    )


_BUILDERS = {
    "launchpad": build_launchpad,
    "homepage": build_homepage,
    "reading": build_reading,
    "dashboard": build_dashboard,
    "search": build_search,
    "work": build_work_journal,
    "queue": build_work_queue,
}


def get_pattern_page(
    key: str,
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    page_hrefs: dict[str, str] | None = None,
) -> Any:
    """Return the Git-tracked sample page dataclass for one of the 7 patterns."""
    alias = resolve_pattern_key(key)
    builder = _BUILDERS[alias]
    return builder(theme=theme, print_mode=print_mode, page_hrefs=page_hrefs)
