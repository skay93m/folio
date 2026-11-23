"""Shared pattern navigation and key-alias helpers for Django views and static builds."""

from __future__ import annotations

from collections.abc import Mapping

PATTERN_KEYS: tuple[str, ...] = (
    "launchpad",
    "homepage",
    "reading",
    "dashboard",
    "search",
    "work",
    "queue",
)

PATTERN_LABELS: tuple[tuple[str, str], ...] = (
    ("launchpad", "Launchpad"),
    ("homepage", "Homepage · Stage 1"),
    ("reading", "Reading page"),
    ("dashboard", "Dashboard"),
    ("search", "Index / search"),
    ("work", "Work with journal"),
    ("queue", "Work queues"),
)

PATTERN_KEY_ALIASES: dict[str, str] = {
    "writing": "work",
    "index": "search",
}


def resolve_pattern_key(raw_key: str, *, default: str | None = None) -> str:
    """Resolve a pattern key or legacy alias to a canonical pattern key."""
    canonical = PATTERN_KEY_ALIASES.get(raw_key, raw_key)
    if canonical in PATTERN_KEYS:
        return canonical
    if default is not None:
        return default
    raise KeyError(f"Unknown Folio pattern key: {raw_key!r}")


def build_gallery_nav(
    active_key: str,
    *,
    hrefs: Mapping[str, str],
    catalogue_href: str,
) -> dict[str, object]:
    """Build gallery navigation context shared between Django views and static releases."""
    links = [
        {
            "key": key,
            "label": label,
            "href": hrefs[key],
            "active": key == active_key,
        }
        for key, label in PATTERN_LABELS
    ]
    links.append(
        {
            "key": "elements",
            "label": "Design-system elements",
            "href": hrefs["elements"],
            "active": active_key == "elements",
        }
    )
    return {
        "catalogue_href": catalogue_href,
        "pattern_links": links,
    }
