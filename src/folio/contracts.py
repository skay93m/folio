"""Typed immutable page pattern contracts with construction-time validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

ThemeMode = Literal["light", "dark"]
PrintMode = Literal["colour", "greyscale", "black-white"]
SemanticRole = Literal["success", "warning", "error", "info", "neutral"]

VALID_THEMES: frozenset[str] = frozenset({"light", "dark"})
VALID_PRINT_MODES: frozenset[str] = frozenset({"colour", "greyscale", "black-white"})
VALID_SEMANTIC_ROLES: frozenset[str] = frozenset({"success", "warning", "error", "info", "neutral"})

_FAUX_SERIF_TAG_RE = re.compile(r"</?(?:em|strong|i|b)\b", re.IGNORECASE)


def require_non_empty(value: str, field_name: str) -> str:
    """Ensure a required string field is non-empty after stripping."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def require_sentence_case(heading: str, field_name: str) -> str:
    """Reject ALL-CAPS headings while permitting acronyms inside sentence-case strings."""
    require_non_empty(heading, field_name)
    letters = [ch for ch in heading if ch.isalpha()]
    if len(letters) >= 2 and heading == heading.upper():
        raise ValueError(f"{field_name} must use sentence-case rather than all-caps: {heading!r}")
    return heading


def forbid_faux_serif_tags(text: str, field_name: str) -> str:
    """Reject <em>, <strong>, <i>, and <b> tags in IBMPlexSerif-Regular reading prose."""
    if not isinstance(text, str):
        raise TypeError(f"{field_name} must be a str, got {type(text).__name__}")
    match = _FAUX_SERIF_TAG_RE.search(text)
    if match:
        raise ValueError(f"{field_name} must not contain faux-style Serif tag {match.group(0)!r}")
    return text


def validate_theme(theme: str) -> ThemeMode:
    """Validate that theme is 'light' or 'dark'."""
    if theme not in VALID_THEMES:
        raise ValueError(f"theme must be one of {sorted(VALID_THEMES)}, got {theme!r}")
    return theme  # type: ignore[return-value]


def validate_print_mode(print_mode: str) -> PrintMode:
    """Validate that print_mode is 'colour', 'greyscale', or 'black-white'."""
    if print_mode not in VALID_PRINT_MODES:
        raise ValueError(f"print_mode must be one of {sorted(VALID_PRINT_MODES)}, got {print_mode!r}")
    return print_mode  # type: ignore[return-value]


def validate_semantic_role(role: str, field_name: str = "status_role") -> SemanticRole:
    """Validate semantic state role against the five ADR 0020 roles."""
    if role not in VALID_SEMANTIC_ROLES:
        raise ValueError(f"{field_name} must be a valid semantic role {sorted(VALID_SEMANTIC_ROLES)}, got {role!r}")
    return role  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class SocialLink:
    """Icon-only header social or academic profile link."""

    label: str
    href: str
    icon: Literal["email", "github", "linkedin", "researchgate", "orcid"]
    aria_label: str
    external: bool = True

    def __post_init__(self) -> None:
        require_non_empty(self.label, "SocialLink.label")
        require_non_empty(self.href, "SocialLink.href")
        require_non_empty(self.aria_label, "SocialLink.aria_label")


@dataclass(frozen=True, slots=True)
class LaunchpadCard:
    """Concise activity destination card inside a Launchpad."""

    title: str
    description: str
    href: str
    eyebrow: str = ""
    status_role: SemanticRole = "neutral"
    status_label: str = ""

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "LaunchpadCard.title")
        require_non_empty(self.description, "LaunchpadCard.description")
        require_non_empty(self.href, "LaunchpadCard.href")
        validate_semantic_role(self.status_role, "LaunchpadCard.status_role")


def require_html_id(value: str) -> str:
    """Keep generated dialog IDs usable as HTML identifiers."""
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", value):
        raise ValueError("dialog ID must start with a letter and contain letters, digits, hyphens or underscores")
    return value


@dataclass(frozen=True, slots=True)
class HeaderAction:
    """Secondary button in the header that opens a named native dialog."""

    label: str
    dialog_id: str

    def __post_init__(self) -> None:
        require_non_empty(self.label, "HeaderAction.label")
        require_html_id(self.dialog_id)


@dataclass(frozen=True, slots=True)
class Dialog:
    """Reusable native dialog with consumer-owned template content.

    Content templates receive the normal rendering context, including any
    CSRF token supplied by the Django adapter. Folio does not persist form data.
    """

    id: str
    title: str
    template_name: str

    def __post_init__(self) -> None:
        require_html_id(self.id)
        require_sentence_case(self.title, "Dialog.title")
        require_non_empty(self.template_name, "Dialog.template_name")


@dataclass(frozen=True, slots=True)
class Launchpad:
    """Concise entry-point pattern with a small set of destination cards."""

    title: str
    intro: str
    cards: tuple[LaunchpadCard, ...]
    eyebrow: str = "SK workspace"
    home_href: str = "?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True
    layout: Literal["default", "two-door"] = "default"
    header_actions: tuple[HeaderAction, ...] = ()
    dialogs: tuple[Dialog, ...] = ()

    pattern_key: str = "launchpad"
    partial_template: str = "folio/patterns/launchpad.html"

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "Launchpad.title")
        require_non_empty(self.intro, "Launchpad.intro")
        require_non_empty(self.home_aria_label, "Launchpad.home_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if not self.cards:
            raise ValueError("Launchpad.cards must contain at least one card")
        if self.layout not in {"default", "two-door"}:
            raise ValueError("Launchpad.layout must be default or two-door")
        if self.layout == "two-door" and len(self.cards) != 2:
            raise ValueError("Launchpad two-door layout requires exactly two cards")
        ids = [dialog.id for dialog in self.dialogs]
        if set(ids) & {"main", "theme-toggle", "page-picker", "print-mode"}:
            raise ValueError("Launchpad dialog IDs must not collide with shell control IDs")
        if len(ids) != len(set(ids)):
            raise ValueError("Launchpad dialog IDs must be unique")
        if set(ids) & {f"{identifier}-title" for identifier in ids}:
            raise ValueError("Launchpad dialog IDs must not collide with generated title IDs")
        if any(action.dialog_id not in ids for action in self.header_actions):
            raise ValueError("Launchpad header action references an unknown dialog")


@dataclass(frozen=True, slots=True)
class HomepageNoteItem:
    """Note link listed on a single-column editorial Homepage."""

    slug: str
    title: str
    date: str
    summary: str
    href: str

    def __post_init__(self) -> None:
        require_non_empty(self.slug, "HomepageNoteItem.slug")
        require_sentence_case(self.title, "HomepageNoteItem.title")
        require_non_empty(self.date, "HomepageNoteItem.date")
        forbid_faux_serif_tags(self.summary, "HomepageNoteItem.summary")
        require_non_empty(self.href, "HomepageNoteItem.href")


@dataclass(frozen=True, slots=True)
class Homepage:
    """Cardless 760px Stage 1 editorial homepage pattern."""

    author_name: str
    headline: str
    statement_paragraphs: tuple[str, ...]
    now_heading: str
    now_paragraphs: tuple[str, ...]
    notes_heading: str
    notes_intro: str
    notes: tuple[HomepageNoteItem, ...]
    long_form_heading: str
    long_form_paragraphs: tuple[str, ...]
    socials: tuple[SocialLink, ...]
    long_form_notes: tuple[HomepageNoteItem, ...] = ()
    footer_copyright: str = "© 2026 SK Design System"
    footer_note: str = "Built in public. Corrections welcome."
    footer_source_url: str = "https://github.com/skay93m/folio"
    footer_source_label: str = "open source"
    title: str = "Editorial Homepage"
    home_href: str = "?page=homepage"
    home_aria_label: str = "Editorial homepage"
    socials_aria_label: str = "Social and academic profiles"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = False

    lang: str = "en-GB"
    meta_description: str = ""
    canonical_url: str = ""
    author_meta: str = ""
    citation_date: str = ""
    include_scripts: bool = True

    pattern_key: str = "homepage"
    partial_template: str = "folio/patterns/homepage.html"
    body_classes: str = "sk-spatial-canvas sk-gwern-folio"
    is_stage1_shell: bool = True

    def __post_init__(self) -> None:
        require_non_empty(self.lang, "Homepage.lang")
        require_sentence_case(self.author_name, "Homepage.author_name")
        require_non_empty(self.headline, "Homepage.headline")
        require_sentence_case(self.now_heading, "Homepage.now_heading")
        require_sentence_case(self.notes_heading, "Homepage.notes_heading")
        require_sentence_case(self.long_form_heading, "Homepage.long_form_heading")
        require_non_empty(self.home_aria_label, "Homepage.home_aria_label")
        require_non_empty(self.socials_aria_label, "Homepage.socials_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        forbid_faux_serif_tags(self.notes_intro, "Homepage.notes_intro")
        for idx, para in enumerate(self.statement_paragraphs):
            forbid_faux_serif_tags(para, f"Homepage.statement_paragraphs[{idx}]")
        for idx, para in enumerate(self.now_paragraphs):
            forbid_faux_serif_tags(para, f"Homepage.now_paragraphs[{idx}]")
        for idx, para in enumerate(self.long_form_paragraphs):
            forbid_faux_serif_tags(para, f"Homepage.long_form_paragraphs[{idx}]")


@dataclass(frozen=True, slots=True)
class ProvenanceEntry:
    """Disclosure entry in top-placed .article-provenance."""

    summary: str
    detail: str
    open_by_default: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.summary, "ProvenanceEntry.summary")
        forbid_faux_serif_tags(self.detail, "ProvenanceEntry.detail")


@dataclass(frozen=True, slots=True)
class ReadingSection:
    """Anchored prose section inside a Reading page."""

    id: str
    heading: str
    paragraphs: tuple[str, ...]
    blockquote: str = ""
    blockquote_variant: Literal["default", "thought"] = "default"
    blockquote_eyebrow: str = ""
    code_block: str = ""
    comparison: tuple[tuple[str, str], ...] = ()
    figure_caption: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.id, "ReadingSection.id")
        require_sentence_case(self.heading, "ReadingSection.heading")
        for idx, para in enumerate(self.paragraphs):
            forbid_faux_serif_tags(para, f"ReadingSection.paragraphs[{idx}]")
        if self.blockquote:
            forbid_faux_serif_tags(self.blockquote, "ReadingSection.blockquote")


@dataclass(frozen=True, slots=True)
class MarginNote:
    """Marginalia and mobile footnote entry on a Reading page."""

    label: str
    text: str
    footnote_id: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.label, "MarginNote.label")
        forbid_faux_serif_tags(self.text, "MarginNote.text")


@dataclass(frozen=True, slots=True)
class ReadingRelation:
    """Backlink or similar link entry rendered only when populated."""

    title: str
    href: str
    external: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.title, "ReadingRelation.title")
        require_non_empty(self.href, "ReadingRelation.href")


@dataclass(frozen=True, slots=True)
class Reading:
    """Long-form Reading pattern with sticky TOC, boxed abstract, provenance, and marginalia."""

    eyebrow: str
    title: str
    meta: tuple[str, ...]
    abstract: str = ""
    sections: tuple[ReadingSection, ...] = ()
    body_html: str = ""
    provenance: tuple[ProvenanceEntry, ...] = ()
    margin_notes: tuple[MarginNote, ...] = ()
    backlinks: tuple[ReadingRelation, ...] = ()
    similar_links: tuple[ReadingRelation, ...] = ()
    back_href: str = ""
    back_label: str = "Back to homepage"
    toc_aria_label: str = "On this page"
    margin_aria_label: str = "Margin notes"
    show_print_action: bool = True
    show_progress: bool = True
    standalone_header: bool = False
    socials: tuple[SocialLink, ...] = ()
    socials_aria_label: str = "Social and academic profiles"
    footer_copyright: str = ""
    footer_note: str = ""
    footer_source_url: str = ""
    footer_source_label: str = "open source"
    home_href: str = "?page=homepage"
    home_aria_label: str = "Reading home"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    lang: str = "en-GB"
    meta_description: str = ""
    canonical_url: str = ""
    author_meta: str = ""
    citation_date: str = ""
    include_scripts: bool = True

    pattern_key: str = "reading"
    partial_template: str = "folio/patterns/reading.html"
    study_markdown: str = ""

    @property
    def body_classes(self) -> str:
        if self.standalone_header:
            return "sk-spatial-canvas sk-gwern-folio sk-view-reading"
        return ""

    @property
    def is_stage1_shell(self) -> bool:
        return self.standalone_header

    def __post_init__(self) -> None:
        require_non_empty(self.lang, "Reading.lang")
        if self.study_markdown:
            from folio.study import parse_study_markup

            parse_study_markup(self.study_markdown)
        require_non_empty(self.eyebrow, "Reading.eyebrow")
        require_sentence_case(self.title, "Reading.title")
        if self.abstract:
            forbid_faux_serif_tags(self.abstract, "Reading.abstract")
        if self.body_html:
            forbid_faux_serif_tags(self.body_html, "Reading.body_html")
        require_non_empty(self.toc_aria_label, "Reading.toc_aria_label")
        require_non_empty(self.margin_aria_label, "Reading.margin_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if not self.sections and not self.body_html.strip() and not self.study_markdown.strip():
            raise ValueError("Reading requires sections, body_html or study_markdown")


@dataclass(frozen=True, slots=True)
class MetricCard:
    """Single labelled metric with comparison and semantic role."""

    label: str
    value: str
    comparison: str
    role: SemanticRole = "neutral"

    def __post_init__(self) -> None:
        require_non_empty(self.label, "MetricCard.label")
        require_non_empty(self.value, "MetricCard.value")
        require_non_empty(self.comparison, "MetricCard.comparison")
        validate_semantic_role(self.role, "MetricCard.role")


@dataclass(frozen=True, slots=True)
class TrendSeries:
    """Time-period metric and trend series for Dashboard."""

    period_key: str
    period_label: str
    labels: tuple[str, ...]
    completed: tuple[int, ...]
    arrived: tuple[int, ...]
    metrics: tuple[MetricCard, ...]

    @property
    def table_rows(self) -> tuple[tuple[str, int, int], ...]:
        return tuple(zip(self.labels, self.completed, self.arrived, strict=True))

    def __post_init__(self) -> None:
        require_non_empty(self.period_key, "TrendSeries.period_key")
        require_non_empty(self.period_label, "TrendSeries.period_label")
        if len(self.labels) != len(self.completed) or len(self.labels) != len(self.arrived):
            raise ValueError("TrendSeries labels, completed, and arrived must have equal lengths")


@dataclass(frozen=True, slots=True)
class AttentionItem:
    """Actionable attention item inside Dashboard."""

    title: str
    description: str
    action_label: str
    action_href: str
    role: SemanticRole = "warning"

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "AttentionItem.title")
        require_non_empty(self.description, "AttentionItem.description")
        require_non_empty(self.action_label, "AttentionItem.action_label")
        require_non_empty(self.action_href, "AttentionItem.action_href")
        validate_semantic_role(self.role, "AttentionItem.role")


@dataclass(frozen=True, slots=True)
class Dashboard:
    """Metrics, accessible trend chart + table, and attention direction pattern."""

    eyebrow: str
    title: str
    intro: str
    periods: tuple[TrendSeries, ...]
    selected_period: str
    chart_title: str
    chart_subtitle: str
    chart_aria_label: str
    attention_heading: str
    attention_items: tuple[AttentionItem, ...]
    direction_eyebrow: str
    direction_text: str
    disclaimer: str = "Sample metrics and guidance. No live activity is inferred."
    period_label: str = "Period"
    period_aria_label: str = "Select time period"
    home_href: str = "?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "dashboard"
    partial_template: str = "folio/patterns/dashboard.html"

    @property
    def active_period(self) -> TrendSeries:
        for period in self.periods:
            if period.period_key == self.selected_period:
                return period
        return self.periods[0]

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "Dashboard.title")
        require_non_empty(self.intro, "Dashboard.intro")
        require_sentence_case(self.chart_title, "Dashboard.chart_title")
        require_non_empty(self.chart_aria_label, "Dashboard.chart_aria_label")
        require_sentence_case(self.attention_heading, "Dashboard.attention_heading")
        require_non_empty(self.period_aria_label, "Dashboard.period_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if not self.periods:
            raise ValueError("Dashboard.periods must contain at least one TrendSeries")


@dataclass(frozen=True, slots=True)
class SearchFacetValue:
    """Facet value and count inside SearchIndex sidebar."""

    value: str
    count: int

    def __post_init__(self) -> None:
        require_non_empty(self.value, "SearchFacetValue.value")
        if self.count < 0:
            raise ValueError("SearchFacetValue.count must be non-negative")


@dataclass(frozen=True, slots=True)
class SearchFacet:
    """Metadata facet group inside SearchIndex."""

    field: str
    values: tuple[SearchFacetValue, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.field, "SearchFacet.field")


@dataclass(frozen=True, slots=True)
class SearchFilter:
    """Structured field filter row."""

    field: str
    operator: Literal["equals", "contains", "not"]
    value: str

    def __post_init__(self) -> None:
        require_non_empty(self.field, "SearchFilter.field")


@dataclass(frozen=True, slots=True)
class SearchRecord:
    """Single searchable record result."""

    title: str
    record_type: str
    topic: str
    status: str
    status_role: SemanticRole
    excerpt: str
    href: str

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "SearchRecord.title")
        require_non_empty(self.record_type, "SearchRecord.record_type")
        require_non_empty(self.topic, "SearchRecord.topic")
        require_non_empty(self.status, "SearchRecord.status")
        validate_semantic_role(self.status_role, "SearchRecord.status_role")
        require_non_empty(self.excerpt, "SearchRecord.excerpt")
        require_non_empty(self.href, "SearchRecord.href")


@dataclass(frozen=True, slots=True)
class SearchIndex:
    """Index and structured search pattern."""

    eyebrow: str
    title: str
    intro: str
    facets: tuple[SearchFacet, ...]
    modes: tuple[str, ...]
    selected_mode: str
    records: tuple[SearchRecord, ...]
    active_filters: tuple[SearchFilter, ...] = ()
    query: str = ""
    search_aria_label: str = "Search record text"
    search_placeholder: str = "Search titles and content"
    modes_aria_label: str = "Record category"
    facets_heading: str = "Metadata fields"
    home_href: str = "?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "search"
    partial_template: str = "folio/patterns/search.html"

    @property
    def facet_fields(self) -> tuple[str, ...]:
        return tuple(facet.field for facet in self.facets)

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "SearchIndex.title")
        require_non_empty(self.intro, "SearchIndex.intro")
        require_non_empty(self.search_aria_label, "SearchIndex.search_aria_label")
        require_non_empty(self.modes_aria_label, "SearchIndex.modes_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if self.selected_mode not in self.modes:
            raise ValueError("SearchIndex.selected_mode must be present in modes")


@dataclass(frozen=True, slots=True)
class WorkStep:
    """Checklist step inside WorkJournal."""

    id: str
    label: str
    description: str
    completed: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.id, "WorkStep.id")
        require_non_empty(self.label, "WorkStep.label")
        require_non_empty(self.description, "WorkStep.description")


@dataclass(frozen=True, slots=True)
class JournalPreviewEntry:
    """Memory-only journal entry for WorkJournal preview."""

    scope: Literal["work", "general"]
    text: str
    cue: str = ""

    def __post_init__(self) -> None:
        if self.scope not in {"work", "general"}:
            raise ValueError(f"JournalPreviewEntry.scope must be 'work' or 'general', got {self.scope!r}")
        require_non_empty(self.text, "JournalPreviewEntry.text")


@dataclass(frozen=True, slots=True)
class WorkJournal:
    """Work session with contextual journal capture preview (the consuming application owns production persistence)."""

    eyebrow: str
    title: str
    intro: str
    task_heading: str
    task_description: str
    status_badges: tuple[tuple[str, SemanticRole], ...]
    steps: tuple[WorkStep, ...]
    journal_date_label: str
    journal_path: str
    work_scope_label: str
    general_scope_label: str
    entries: tuple[JournalPreviewEntry, ...] = ()
    pane_aria_label: str = "Contextual journal"
    preview_notice: str = (
        "Sample journal · Memory-only preview (the consuming application owns production journal persistence)"
    )
    supporting_context: str = (
        "The journal stays associated with this work. Production save and recovery belong to the consuming application."
    )
    home_href: str = "?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "work"
    partial_template: str = "folio/patterns/work_journal.html"

    @property
    def work_entries_count(self) -> int:
        return sum(1 for entry in self.entries if entry.scope == "work")

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "WorkJournal.title")
        require_non_empty(self.intro, "WorkJournal.intro")
        require_sentence_case(self.task_heading, "WorkJournal.task_heading")
        require_non_empty(self.pane_aria_label, "WorkJournal.pane_aria_label")
        require_non_empty(self.preview_notice, "WorkJournal.preview_notice")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        for label, role in self.status_badges:
            require_non_empty(label, "WorkJournal.status_badges label")
            validate_semantic_role(role, "WorkJournal.status_badges role")


@dataclass(frozen=True, slots=True)
class QueueCategory:
    """Left-rail queue category."""

    key: str
    name: str
    description: str

    def __post_init__(self) -> None:
        require_non_empty(self.key, "QueueCategory.key")
        require_sentence_case(self.name, "QueueCategory.name")
        require_non_empty(self.description, "QueueCategory.description")


@dataclass(frozen=True, slots=True)
class QueueRow:
    """Actionable item row in a WorkQueue."""

    id: str
    queue: str
    title: str
    status: Literal["Ready", "Waiting", "Completed"]
    status_role: SemanticRole
    priority: Literal["Normal", "High"]
    owner: str
    age: str
    context: str
    note: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.id, "QueueRow.id")
        require_non_empty(self.queue, "QueueRow.queue")
        require_sentence_case(self.title, "QueueRow.title")
        if self.status not in {"Ready", "Waiting", "Completed"}:
            raise ValueError(f"QueueRow.status invalid: {self.status!r}")
        validate_semantic_role(self.status_role, "QueueRow.status_role")
        if self.priority not in {"Normal", "High"}:
            raise ValueError(f"QueueRow.priority invalid: {self.priority!r}")
        require_non_empty(self.owner, "QueueRow.owner")
        require_non_empty(self.age, "QueueRow.age")
        require_non_empty(self.context, "QueueRow.context")


@dataclass(frozen=True, slots=True)
class WorkQueue:
    """Grouped work queues with outstanding-count pills and resolution dialog."""

    eyebrow: str
    title: str
    intro: str
    categories: tuple[QueueCategory, ...]
    selected_category: str
    rows: tuple[QueueRow, ...]
    nav_aria_label: str = "Work queues"
    search_aria_label: str = "Search this queue"
    status_aria_label: str = "Work status"
    table_caption: str = "Work items in the selected queue"
    scope_note: str = "Consuming application initial validation scope: concise Launchpad + Housekeeping queue."
    home_href: str = "?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "queue"
    partial_template: str = "folio/patterns/work_queue.html"

    @property
    def active_category(self) -> QueueCategory:
        for cat in self.categories:
            if cat.key == self.selected_category:
                return cat
        return self.categories[0]

    @property
    def category_counts(self) -> dict[str, int]:
        counts = {cat.key: 0 for cat in self.categories}
        for row in self.rows:
            if row.queue in counts and row.status != "Completed":
                counts[row.queue] += 1
        return counts

    @property
    def category_tabs(self) -> tuple[tuple[QueueCategory, int], ...]:
        counts = self.category_counts
        return tuple((cat, counts.get(cat.key, 0)) for cat in self.categories)

    @property
    def row_entries(self) -> tuple[tuple[QueueRow, str], ...]:
        names = {cat.key: cat.name for cat in self.categories}
        return tuple((row, names.get(row.queue, row.queue)) for row in self.rows)

    @property
    def selected_outstanding_count(self) -> int:
        return self.category_counts.get(self.selected_category, 0)

    def __post_init__(self) -> None:
        require_sentence_case(self.title, "WorkQueue.title")
        require_non_empty(self.intro, "WorkQueue.intro")
        require_non_empty(self.nav_aria_label, "WorkQueue.nav_aria_label")
        require_non_empty(self.search_aria_label, "WorkQueue.search_aria_label")
        require_non_empty(self.status_aria_label, "WorkQueue.status_aria_label")
        require_non_empty(self.table_caption, "WorkQueue.table_caption")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if not self.categories:
            raise ValueError("WorkQueue.categories must contain at least one category")
