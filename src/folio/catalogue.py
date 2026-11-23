"""Single-source element catalogue and deterministic link validation (#156, #157)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from importlib import import_module
from typing import Any, Literal

from django.template import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string

from folio.contracts import PrintMode, ThemeMode, validate_print_mode, validate_theme
from folio.renderer import ensure_django_setup

ElementGroupKey = Literal[
    "foundations",
    "layout",
    "content",
    "forms",
    "navigation",
    "feedback",
]

PatternInventoryKey = Literal[
    "launchpad",
    "homepage",
    "reading",
    "dashboard",
    "search",
    "work-journal",
    "work-queues",
]

MaturityLevel = Literal["Reference", "Production source", "Shared adoption"]

ELEMENT_GROUPS: dict[ElementGroupKey, str] = {
    "foundations": "Foundations",
    "layout": "Layout and containment",
    "content": "Content and editorial",
    "forms": "Forms and controls",
    "navigation": "Navigation and structure",
    "feedback": "Feedback and accessibility",
}


class CatalogueValidationError(ValueError):
    """Raised when catalogue entries or pattern inventories fail validation."""


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    """Single-source UI element backed by one live Django template partial."""

    id: str
    title: str
    group: ElementGroupKey
    purpose: str
    constraints: tuple[str, ...]
    maturity: MaturityLevel
    production_owner: str
    release_dependency: str
    template_name: str
    python_usage: str
    used_in_patterns: tuple[PatternInventoryKey, ...]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PatternInventory:
    """Registered page pattern connected to its typed contract, template, and elements."""

    key: PatternInventoryKey
    name: str
    purpose: str
    maturity: MaturityLevel
    ownership_note: str
    dataclass_path: str
    template_name: str
    entry_ids: tuple[str, ...]
    gallery_href: str = ""


CATALOGUE_ENTRIES: tuple[CatalogueEntry, ...] = (
    CatalogueEntry(
        id="theme-roles",
        title="Theme roles",
        group="foundations",
        purpose="Map approved Light (#F7F6F2) and D1 Dark (#17191C) roles into Bootstrap 5 tokens.",
        constraints=(
            "Preserve WCAG 2.2 AA contrast for ink, muted text, links, and control borders.",
            "Keep brand coral #FF4F40 paired with dark ink #271B24.",
        ),
        maturity="Reference",
        production_owner="Folio foundations",
        release_dependency="folio==0.1.0 (sk-design-system.css)",
        template_name="folio/includes/elements/theme_roles.html",
        python_usage='Launchpad(..., theme="light", print_mode="colour")',
        used_in_patterns=(
            "launchpad",
            "homepage",
            "reading",
            "dashboard",
            "search",
            "work-journal",
            "work-queues",
        ),
    ),
    CatalogueEntry(
        id="typography-spacing",
        title="Typography and spacing",
        group="foundations",
        purpose="Use self-hosted F3 fonts (IBM Plex Sans, Serif, Mono) with faux-style guards and --sk-block-gap.",
        constraints=(
            "Never use <em>, <strong>, <i>, or <b> inside IBMPlexSerif-Regular prose.",
            "Use sentence-case left-aligned headings across all viewports.",
        ),
        maturity="Reference",
        production_owner="Folio foundations",
        release_dependency="folio==0.1.0 (fonts/ + sk-design-system.css)",
        template_name="folio/includes/elements/typography_spacing.html",
        python_usage='Reading(..., abstract="Clean Serif text without faux tags.")',
        used_in_patterns=("homepage", "reading", "dashboard"),
    ),
    CatalogueEntry(
        id="ten-colour-families",
        title="Ten approved colour families",
        group="foundations",
        purpose="Apply the ten approved families for categorical charts, pastel light surfaces, and semantic states.",
        constraints=(
            "Pair state colour with explicit words and redundant markers.",
            "Use neutral D1 surface in dark mode with named dark accent marks.",
        ),
        maturity="Reference",
        production_owner="Folio foundations",
        release_dependency="folio==0.1.0 (approved-palette.json)",
        template_name="folio/includes/elements/ten_colour_families.html",
        python_usage='MetricCard(label="Completed", value="28", comparison="+4", role="success")',
        used_in_patterns=("dashboard", "work-queues"),
    ),
    CatalogueEntry(
        id="contained-grid",
        title="Contained responsive grid",
        group="layout",
        purpose="Provide centred canvases and adaptive two-column splits that stack cleanly at 390px.",
        constraints=(
            "Add a side pane only when its content directly supports the active task.",
            "Ensure zero horizontal page overflow at desktop and 390px widths.",
        ),
        maturity="Reference",
        production_owner="Folio layout",
        release_dependency="folio==0.1.0 (bootstrap.min.css + sk-design-system.css)",
        template_name="folio/includes/elements/contained_grid.html",
        python_usage="Launchpad(title=..., intro=..., cards=(LaunchpadCard(...),))",
        used_in_patterns=("launchpad", "dashboard", "search", "work-journal", "work-queues"),
    ),
    CatalogueEntry(
        id="boxed-abstract",
        title="Boxed abstract and top provenance",
        group="content",
        purpose="Present Gwern-inspired boxed summary and collapsible AI/revision provenance above long-form prose.",
        constraints=(
            "Place .article-provenance directly after .abstract and before article sections.",
            "Omit .sk-reading-relations entirely when backlinks and similar_links are empty.",
        ),
        maturity="Reference",
        production_owner="Folio reading pattern",
        release_dependency="folio==0.1.0 (patterns/reading.html)",
        template_name="folio/includes/elements/boxed_abstract.html",
        python_usage="Reading(..., abstract=..., provenance=(ProvenanceEntry(...),))",
        used_in_patterns=("homepage", "reading"),
    ),
    CatalogueEntry(
        id="structured-table",
        title="Structured responsive table",
        group="content",
        purpose="Keep tabular records inside .table-responsive with an explicit caption and scoped headers.",
        constraints=(
            "Always provide <caption> and <th scope='col'>.",
            "Repeat <thead> when printing across pages.",
        ),
        maturity="Reference",
        production_owner="Folio content",
        release_dependency="folio==0.1.0 (sk-design-system.css)",
        template_name="folio/includes/elements/structured_table.html",
        python_usage='WorkQueue(..., table_caption="Work items in the selected queue")',
        used_in_patterns=("dashboard", "work-queues"),
    ),
    CatalogueEntry(
        id="primary-action",
        title="Primary action",
        group="forms",
        purpose="Express the primary commitment action on Monzo coral (#FF4F40) with accessible dark ink (#271B24).",
        constraints=(
            "Use a clear verb phrase explaining the action.",
            "Maintain a 3px high-contrast keyboard focus ring via :focus-visible.",
            "Limit to one primary action per decision surface.",
        ),
        maturity="Reference",
        production_owner="Folio forms",
        release_dependency="folio==0.1.0 (sk-design-system foundations)",
        template_name="folio/includes/elements/primary_action.html",
        context={"label": "Review work"},
        python_usage='{% include "folio/includes/elements/primary_action.html" with label="Review work" %}',
        used_in_patterns=("search", "work-journal", "work-queues"),
    ),
    CatalogueEntry(
        id="labelled-input",
        title="Labelled form input",
        group="forms",
        purpose="Pair every form control with an explicit <label> and aria-describedby helper text.",
        constraints=(
            "Never rely solely on placeholder text as a label.",
            "Use 1px solid --sk-control-border (#7B7B89 light / #6D747E dark) for non-text contrast.",
        ),
        maturity="Reference",
        production_owner="Folio forms",
        release_dependency="folio==0.1.0 (sk-design-system.css)",
        template_name="folio/includes/elements/labelled_input.html",
        python_usage='SearchIndex(..., search_aria_label="Search record text")',
        used_in_patterns=("search", "work-journal", "work-queues"),
    ),
    CatalogueEntry(
        id="status-badge",
        title="Semantic status badge",
        group="navigation",
        purpose="Communicate Ready, Waiting, Completed, Blocked, and Neutral states using words plus approved colours.",
        constraints=(
            "Validate status_role against ('success', 'warning', 'error', 'info', 'neutral').",
            "Always display status text so colour-blind and monochrome print readers retain meaning.",
        ),
        maturity="Reference",
        production_owner="Folio navigation & state",
        release_dependency="folio==0.1.0 (contracts.SemanticRole)",
        template_name="folio/includes/elements/status_badge.html",
        python_usage='QueueRow(..., status="Ready", status_role="info")',
        used_in_patterns=("launchpad", "dashboard", "search", "work-journal", "work-queues"),
    ),
    CatalogueEntry(
        id="disclosure-dialog",
        title="Contextual disclosure and dialog",
        group="navigation",
        purpose="Reveal supporting context or ticket details progressively without cluttering the primary canvas.",
        constraints=(
            "Keep critical actions outside collapsed disclosures.",
            "Provide an accessible close button with aria-label on every dialog.",
        ),
        maturity="Reference",
        production_owner="Folio navigation",
        release_dependency="folio==0.1.0 (bootstrap.bundle.min.js)",
        template_name="folio/includes/elements/disclosure_dialog.html",
        python_usage='ProvenanceEntry(summary="AI contribution", detail="...")',
        used_in_patterns=("reading", "dashboard", "work-journal", "work-queues"),
    ),
    CatalogueEntry(
        id="semantic-alert",
        title="Semantic feedback alert",
        group="feedback",
        purpose="Explain local save confirmation or failure clearly with role='status' or role='alert'.",
        constraints=(
            "Retain user input when a save fails.",
            "Explain state in plain language as well as border/surface role colour.",
        ),
        maturity="Production source",
        production_owner="Placemat (study_coach journal save feedback); Folio reference",
        release_dependency="folio==0.1.0 (sk-design-system.css)",
        template_name="folio/includes/elements/semantic_alert.html",
        python_usage='WorkJournal(..., preview_notice="Sample journal · Memory-only preview")',
        used_in_patterns=("work-journal",),
    ),
    CatalogueEntry(
        id="empty-state",
        title="Empty state",
        group="feedback",
        purpose="Explain why no records match or appear and suggest the next step calmly.",
        constraints=(
            "Keep copy concise and actionable.",
            "Distinguish zero matching filters from an empty source dataset.",
        ),
        maturity="Reference",
        production_owner="Folio feedback",
        release_dependency="folio==0.1.0 (sk-design-system.css)",
        template_name="folio/includes/elements/empty_state.html",
        python_usage="SearchIndex(...) / WorkQueue(...)",
        used_in_patterns=("search", "work-journal", "work-queues"),
    ),
)

PATTERN_INVENTORIES: dict[PatternInventoryKey, PatternInventory] = {
    "launchpad": PatternInventory(
        key="launchpad",
        name="Launchpad",
        purpose="Choose one activity and give it your full attention without sidebar clutter.",
        maturity="Reference",
        ownership_note="Cockpit initial validation scope uses a minimal 1-card Launchpad + Housekeeping queue.",
        dataclass_path="folio.contracts.Launchpad",
        template_name="folio/patterns/launchpad.html",
        entry_ids=("theme-roles", "contained-grid", "status-badge"),
        gallery_href="/?page=launchpad",
    ),
    "homepage": PatternInventory(
        key="homepage",
        name="Homepage · Stage 1",
        purpose="Cardless 760px editorial homepage with icon-only socials, Writer's Diet bio, Notes, Now, and static footer.",
        maturity="Reference",
        ownership_note="Reference template for syafiqkay.com Stage 1 (ADR 0021); syafiqkay.com owns its published content.",
        dataclass_path="folio.contracts.Homepage",
        template_name="folio/patterns/homepage.html",
        entry_ids=("theme-roles", "typography-spacing", "boxed-abstract"),
        gallery_href="/?page=homepage",
    ),
    "reading": PatternInventory(
        key="reading",
        name="Reading page",
        purpose="Sustained long-form reading with sticky TOC, boxed abstract, top provenance, marginalia, and conditional relations.",
        maturity="Reference",
        ownership_note="Shared Reading template used by both the gallery and Stage 1 note views.",
        dataclass_path="folio.contracts.Reading",
        template_name="folio/patterns/reading.html",
        entry_ids=("theme-roles", "typography-spacing", "boxed-abstract", "disclosure-dialog"),
        gallery_href="/?page=reading",
    ),
    "dashboard": PatternInventory(
        key="dashboard",
        name="Dashboard",
        purpose="Compare period metrics, redundant-encoded trend charts with data tables, and attention links.",
        maturity="Reference",
        ownership_note="Sample demonstration metrics only; consumers supply real domain series.",
        dataclass_path="folio.contracts.Dashboard",
        template_name="folio/patterns/dashboard.html",
        entry_ids=(
            "theme-roles",
            "typography-spacing",
            "ten-colour-families",
            "contained-grid",
            "structured-table",
            "status-badge",
            "disclosure-dialog",
        ),
        gallery_href="/?page=dashboard",
    ),
    "search": PatternInventory(
        key="search",
        name="Index / search",
        purpose="Combine metadata facets, category tabs, and structured field filters over a record index.",
        maturity="Reference",
        ownership_note="Client/server filter structure demonstrated with Git-tracked sample fixtures.",
        dataclass_path="folio.contracts.SearchIndex",
        template_name="folio/patterns/search.html",
        entry_ids=(
            "theme-roles",
            "contained-grid",
            "primary-action",
            "labelled-input",
            "status-badge",
            "empty-state",
        ),
        gallery_href="/?page=search",
    ),
    "work-journal": PatternInventory(
        key="work-journal",
        name="Work with journal",
        purpose="Execute a task checklist alongside contextual journal capture.",
        maturity="Production source",
        ownership_note="Memory-only preview in Folio; Placemat (skay93m/placemat study_coach) owns production journal persistence and recovery.",
        dataclass_path="folio.contracts.WorkJournal",
        template_name="folio/patterns/work_journal.html",
        entry_ids=(
            "theme-roles",
            "contained-grid",
            "primary-action",
            "labelled-input",
            "status-badge",
            "disclosure-dialog",
            "semantic-alert",
            "empty-state",
        ),
        gallery_href="/?page=work",
    ),
    "work-queues": PatternInventory(
        key="work-queues",
        name="Work queues",
        purpose="Group actionable items by need, track outstanding counts, and resolve items in a focused dialog.",
        maturity="Reference",
        ownership_note="Cockpit initial validation scope: concise Launchpad + Housekeeping queue.",
        dataclass_path="folio.contracts.WorkQueue",
        template_name="folio/patterns/work_queue.html",
        entry_ids=(
            "theme-roles",
            "ten-colour-families",
            "contained-grid",
            "structured-table",
            "primary-action",
            "labelled-input",
            "status-badge",
            "disclosure-dialog",
            "empty-state",
        ),
        gallery_href="/?page=queue",
    ),
}


@dataclass(frozen=True, slots=True)
class RenderedCatalogueEntry:
    """Single-source entry bundled with live HTML and identical escaped snippet."""

    entry: CatalogueEntry
    rendered_html: str
    snippet: str
    detail_href: str
    pattern_links: tuple[PatternInventory, ...]


@dataclass(frozen=True, slots=True)
class CatalogueGroupView:
    """Element group section inside the Folio catalogue page."""

    key: ElementGroupKey
    label: str
    entries: tuple[RenderedCatalogueEntry, ...]


@dataclass(frozen=True, slots=True)
class CataloguePage:
    """Typed page contract for the full SK Design System catalogue."""

    title: str
    eyebrow: str
    intro: str
    groups: tuple[CatalogueGroupView, ...]
    patterns: tuple[PatternInventory, ...]
    home_href: str = "/?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "elements"
    partial_template: str = "folio/patterns/catalogue.html"

    def __post_init__(self) -> None:
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)


@dataclass(frozen=True, slots=True)
class CatalogueDetailPage:
    """Typed page contract for inspecting one catalogue entry (e.g. primary-action)."""

    title: str
    eyebrow: str
    rendered_entry: RenderedCatalogueEntry
    back_href: str = "/catalogue/"
    home_href: str = "/?page=launchpad"
    home_aria_label: str = "SK launchpad"
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    show_theme_toggle: bool = True

    pattern_key: str = "elements"
    partial_template: str = "folio/patterns/catalogue_detail.html"

    def __post_init__(self) -> None:
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)


def get_catalogue_entries() -> tuple[CatalogueEntry, ...]:
    """Return all registered catalogue entries."""
    return CATALOGUE_ENTRIES


def get_catalogue_entry(entry_id: str) -> CatalogueEntry:
    """Fetch a registered catalogue entry by ID or raise KeyError."""
    for entry in CATALOGUE_ENTRIES:
        if entry.id == entry_id:
            return entry
    raise KeyError(f"Unknown catalogue entry: {entry_id!r}")


def render_entry_example(entry: CatalogueEntry) -> str:
    """Render an entry's single-source Django template partial into HTML."""
    ensure_django_setup()
    return render_to_string(entry.template_name, entry.context).strip()


def _resolve_dotted_symbol(dotted_path: str) -> Any:
    module_path, _, symbol_name = dotted_path.rpartition(".")
    if not module_path or not symbol_name:
        raise ValueError(f"Invalid dotted symbol path: {dotted_path!r}")
    module = import_module(module_path)
    return getattr(module, symbol_name)


def validate_catalogue(
    *,
    entries: tuple[CatalogueEntry, ...] | None = None,
    patterns: tuple[PatternInventory, ...] | None = None,
) -> None:
    """Validate unique IDs, template rendering, dataclass resolution, and bidirectional links."""
    ensure_django_setup()
    entry_list = CATALOGUE_ENTRIES if entries is None else entries
    pattern_list = tuple(PATTERN_INVENTORIES.values()) if patterns is None else patterns
    errors: list[str] = []

    seen_entry_ids: set[str] = set()
    entry_map: dict[str, CatalogueEntry] = {}
    for entry in entry_list:
        if entry.id in seen_entry_ids:
            errors.append(f"Duplicate catalogue entry ID: {entry.id!r}")
            continue
        seen_entry_ids.add(entry.id)
        entry_map[entry.id] = entry

        if entry.group not in ELEMENT_GROUPS:
            errors.append(f"Entry {entry.id!r} references unknown group {entry.group!r}")

        try:
            rendered = render_entry_example(entry)
            if not rendered:
                errors.append(f"Entry {entry.id!r} template {entry.template_name!r} rendered empty HTML")
        except TemplateDoesNotExist:
            errors.append(f"Template not found for entry {entry.id!r}: {entry.template_name!r}")
        except Exception as exc:
            errors.append(f"Error rendering entry {entry.id!r} ({entry.template_name!r}): {exc}")

    covered_groups = {entry.group for entry in entry_list if entry.group in ELEMENT_GROUPS}
    missing_groups = set(ELEMENT_GROUPS.keys()) - covered_groups
    if missing_groups:
        errors.append(f"Element groups with zero entries: {sorted(missing_groups)}")

    seen_pattern_keys: set[str] = set()
    pattern_map: dict[str, PatternInventory] = {}
    for pattern in pattern_list:
        if pattern.key in seen_pattern_keys:
            errors.append(f"Duplicate pattern key: {pattern.key!r}")
            continue
        seen_pattern_keys.add(pattern.key)
        pattern_map[pattern.key] = pattern

        if not pattern.entry_ids:
            errors.append(f"Pattern {pattern.key!r} has an empty entry_ids inventory")

        try:
            get_template(pattern.template_name)
        except TemplateDoesNotExist:
            errors.append(f"Template not found for pattern {pattern.key!r}: {pattern.template_name!r}")

        try:
            _resolve_dotted_symbol(pattern.dataclass_path)
        except Exception as exc:
            errors.append(f"Unresolved dataclass for pattern {pattern.key!r} ({pattern.dataclass_path!r}): {exc}")

        for entry_id in pattern.entry_ids:
            if entry_id not in entry_map:
                errors.append(f"Pattern {pattern.key!r} references unknown entry ID {entry_id!r}")
            elif pattern.key not in entry_map[entry_id].used_in_patterns:
                errors.append(
                    f"Bidirectional link mismatch: pattern {pattern.key!r} lists {entry_id!r}, "
                    f"but entry.used_in_patterns does not include {pattern.key!r}"
                )

    for entry in entry_list:
        for p_key in entry.used_in_patterns:
            if p_key not in pattern_map:
                errors.append(f"Entry {entry.id!r} references unknown pattern {p_key!r}")
            elif entry.id not in pattern_map[p_key].entry_ids:
                errors.append(
                    f"Bidirectional link mismatch: entry {entry.id!r} lists pattern {p_key!r}, "
                    f"but pattern.entry_ids does not include {entry.id!r}"
                )

    if errors:
        raise CatalogueValidationError("; ".join(errors))


def _resolve_pattern_inventories(
    pattern_keys: Iterable[PatternInventoryKey],
    pattern_hrefs: Mapping[str, str] | None = None,
) -> tuple[PatternInventory, ...]:
    resolved: list[PatternInventory] = []
    for key in pattern_keys:
        pat = PATTERN_INVENTORIES[key]
        if pattern_hrefs and key in pattern_hrefs:
            resolved.append(replace(pat, gallery_href=pattern_hrefs[key]))
        else:
            resolved.append(pat)
    return tuple(resolved)


def _render_entry_record(
    entry: CatalogueEntry,
    *,
    detail_prefix: str = "/catalogue/",
    pattern_hrefs: Mapping[str, str] | None = None,
) -> RenderedCatalogueEntry:
    html = render_entry_example(entry)
    if not detail_prefix:
        detail_href = f"{entry.id}.html"
    elif detail_prefix.endswith("/"):
        detail_href = f"{detail_prefix}{entry.id}/"
    else:
        detail_href = f"{detail_prefix}/{entry.id}.html"
    return RenderedCatalogueEntry(
        entry=entry,
        rendered_html=html,
        snippet=html,
        detail_href=detail_href,
        pattern_links=_resolve_pattern_inventories(entry.used_in_patterns, pattern_hrefs),
    )


def build_catalogue_page(
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    detail_prefix: str = "/catalogue/",
    home_href: str = "/?page=launchpad",
    pattern_hrefs: Mapping[str, str] | None = None,
) -> CataloguePage:
    """Build the full CataloguePage from single-source entries and pattern inventories."""
    validate_catalogue()
    groups: list[CatalogueGroupView] = []
    for group_key, group_label in ELEMENT_GROUPS.items():
        group_entries = tuple(
            _render_entry_record(
                entry,
                detail_prefix=detail_prefix,
                pattern_hrefs=pattern_hrefs,
            )
            for entry in CATALOGUE_ENTRIES
            if entry.group == group_key
        )
        groups.append(
            CatalogueGroupView(
                key=group_key,
                label=group_label,
                entries=group_entries,
            )
        )

    return CataloguePage(
        title="SK Design System Catalogue",
        eyebrow="Source-linked reuse catalogue",
        intro="Bootstrap 5 provides the structural vocabulary. Each entry below renders its live preview and markup snippet from one shared Django template partial.",
        groups=tuple(groups),
        patterns=_resolve_pattern_inventories(PATTERN_INVENTORIES.keys(), pattern_hrefs),
        home_href=home_href,
        theme=theme,
        print_mode=print_mode,
    )


def build_catalogue_detail_page(
    slug: str,
    *,
    theme: ThemeMode = "light",
    print_mode: PrintMode = "colour",
    back_href: str = "/catalogue/",
    home_href: str = "/?page=launchpad",
    detail_prefix: str = "/catalogue/",
    pattern_hrefs: Mapping[str, str] | None = None,
) -> CatalogueDetailPage:
    """Build a focused detail page for a single catalogue entry."""
    validate_catalogue()
    entry = get_catalogue_entry(slug)
    rendered = _render_entry_record(
        entry,
        detail_prefix=detail_prefix,
        pattern_hrefs=pattern_hrefs,
    )
    return CatalogueDetailPage(
        title=entry.title,
        eyebrow=f"Catalogue · {ELEMENT_GROUPS[entry.group]}",
        rendered_entry=rendered,
        back_href=back_href,
        home_href=home_href,
        theme=theme,
        print_mode=print_mode,
    )
