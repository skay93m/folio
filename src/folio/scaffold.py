"""Declarative standalone HTML and multi-variant prototype scaffolder."""

from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser

from folio.contracts import (
    PrintMode,
    ThemeMode,
    require_non_empty,
    validate_print_mode,
    validate_theme,
)
from folio.renderer import render_static

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_VARIANT_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_PAGE_SHELL_MARKER_RE = re.compile(r'class\s*=\s*["\'][^"\']*\bpage-shell\b', re.IGNORECASE)
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)


@dataclass(frozen=True, slots=True)
class ScaffoldVariant:
    """Single switchable variant panel inside a scaffolded prototype."""

    key: str
    label: str
    body_html: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not _VARIANT_KEY_RE.fullmatch(self.key):
            raise ValueError(f"Invalid variant key {self.key!r}: must match ^[A-Za-z0-9][A-Za-z0-9_-]*$")
        require_non_empty(self.label, "ScaffoldVariant.label")
        if not isinstance(self.body_html, str) or not self.body_html.strip():
            raise ValueError(f"ScaffoldVariant({self.key!r}).body_html must not be empty")


@dataclass(frozen=True, slots=True)
class ScaffoldPage:
    """Typed declarative shell contract for standalone SK Design System HTML artifacts."""

    title: str
    body_html: str = ""
    variants: tuple[ScaffoldVariant, ...] = ()
    theme: ThemeMode = "light"
    print_mode: PrintMode = "colour"
    lang: str = "en-GB"
    home_href: str = "#main"
    home_aria_label: str = "SK Design System"
    show_theme_toggle: bool = True
    show_print_selector: bool = True
    include_scripts: bool = True
    partial_template: str = "folio/patterns/scaffold.html"

    def __post_init__(self) -> None:
        require_non_empty(self.title, "ScaffoldPage.title")
        require_non_empty(self.lang, "ScaffoldPage.lang")
        require_non_empty(self.home_aria_label, "ScaffoldPage.home_aria_label")
        validate_theme(self.theme)
        validate_print_mode(self.print_mode)
        if not self.variants and not self.body_html.strip():
            raise ValueError("ScaffoldPage requires either non-empty body_html or variants")
        seen_keys: set[str] = set()
        for variant in self.variants:
            norm = variant.key.lower()
            if norm in seen_keys:
                raise ValueError(f"Duplicate variant key: {variant.key!r}")
            seen_keys.add(norm)

    @property
    def wrap_page_shell(self) -> bool:
        if self.variants:
            return not any(_PAGE_SHELL_MARKER_RE.search(v.body_html) for v in self.variants)
        return not bool(_PAGE_SHELL_MARKER_RE.search(self.body_html))


class _VariantExtractor(HTMLParser):
    """Extract top-level [data-variant] blocks from an HTML fragment."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.extracted: list[tuple[str, str, str]] = []
        self._active_key: str | None = None
        self._active_label: str = ""
        self._active_tag: str = ""
        self._depth: int = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = dict(attrs)
        raw = self.get_starttag_text() or f"<{tag}>"
        if self._active_key is None:
            vkey = (attr_map.get("data-variant") or "").strip()
            if vkey:
                self._active_key = vkey
                self._active_label = (attr_map.get("data-variant-label") or "").strip()
                self._active_tag = tag_l
                self._depth = 0 if tag_l in _VOID_TAGS else 1
                self._buf = []
                if self._depth == 0:
                    self.extracted.append((self._active_key, self._active_label, raw))
                    self._active_key = None
                return
        else:
            if tag_l == self._active_tag and tag_l not in _VOID_TAGS:
                self._depth += 1
            self._buf.append(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag} />"
        if self._active_key is not None:
            self._buf.append(raw)

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if self._active_key is None:
            return
        if tag_l == self._active_tag:
            self._depth -= 1
            if self._depth == 0:
                self.extracted.append((self._active_key, self._active_label, "".join(self._buf).strip()))
                self._active_key = None
                self._active_label = ""
                self._active_tag = ""
                self._buf = []
                return
        self._buf.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._active_key is not None:
            self._buf.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._active_key is not None:
            self._buf.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._active_key is not None:
            self._buf.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        if self._active_key is not None:
            self._buf.append(f"<!--{data}-->")


def validate_slug(slug: str) -> str:
    """Validate a safe lowercase kebab/snake prototype slug."""
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise ValueError(
            f"Invalid prototype slug {slug!r}: must match ^[a-z0-9][a-z0-9_-]*$"
        )
    return slug


def default_prototype_filename(slug: str) -> str:
    """Return canonical prototype filename (`prototype-<slug>.html` unless already prefixed)."""
    validated = validate_slug(slug)
    return f"{validated}.html" if validated.startswith("prototype-") else f"prototype-{validated}.html"


def parse_variants_spec(spec: str | Sequence[str] | None) -> list[tuple[str, str]]:
    """Parse `--variants A,B,C` or `A:Map,B:Dashboard` into `(key, label)` pairs."""
    if spec is None:
        return []
    raw_items = [part.strip() for part in spec.split(",")] if isinstance(spec, str) else [str(item).strip() for item in spec]
    items = [item for item in raw_items if item]
    if not items:
        return []

    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if ":" in item:
            key_raw, label_raw = item.split(":", 1)
            key = key_raw.strip()
            label = label_raw.strip() or key
            display = f"{key}: {label}" if label != key else key
        else:
            key = item
            display = key
        if not _VARIANT_KEY_RE.fullmatch(key):
            raise ValueError(f"Invalid variant key {key!r}: must match ^[A-Za-z0-9][A-Za-z0-9_-]*$")
        if key.lower() in seen:
            raise ValueError(f"Duplicate variant key: {key!r}")
        seen.add(key.lower())
        parsed.append((key, display))
    return parsed


def _default_title_from_slug(slug: str) -> str:
    cleaned = slug.removeprefix("prototype-").replace("-", " ").replace("_", " ").strip()
    if not cleaned:
        return "SK Design System Prototype"
    return cleaned[0].upper() + cleaned[1:]


def _starter_variant_body(key: str, label: str) -> str:
    safe_label = html.escape(label)
    safe_key = html.escape(key)
    return (
        f'<section class="surface p-4">\n'
        f'  <span class="eyebrow">Variant {safe_key}</span>\n'
        f'  <h1 class="mt-2">{safe_label}</h1>\n'
        f'  <p>Semantic prototype surface for variant {safe_key}.</p>\n'
        f'</section>'
    )


def scaffold_html(
    slug: str,
    *,
    fragment_html: str | None = None,
    variants: Sequence[str] | str | None = None,
    variant_bodies: Mapping[str, str] | None = None,
    title: str | None = None,
    theme: ThemeMode = "light",
    static_prefix: str = "assets/",
) -> str:
    """Compile semantic body HTML (and optional variants) into a complete SK Design System page."""
    validated_slug = validate_slug(slug)
    resolved_title = title.strip() if isinstance(title, str) and title.strip() else _default_title_from_slug(validated_slug)
    parsed_variants = parse_variants_spec(variants)

    extracted: list[tuple[str, str, str]] = []
    if fragment_html is not None and fragment_html.strip():
        extractor = _VariantExtractor()
        extractor.feed(fragment_html)
        extractor.close()
        extracted = extractor.extracted

    extracted_by_key = {k.lower(): (k, lbl or k, body) for k, lbl, body in extracted}

    variant_objs: list[ScaffoldVariant] = []
    if parsed_variants:
        for idx, (vkey, default_label) in enumerate(parsed_variants):
            if variant_bodies and vkey in variant_bodies and variant_bodies[vkey].strip():
                vbody = variant_bodies[vkey].strip()
                vlabel = default_label
            elif vkey.lower() in extracted_by_key:
                _, ext_label, ext_body = extracted_by_key[vkey.lower()]
                vbody = ext_body or _starter_variant_body(vkey, default_label)
                vlabel = ext_label if ext_label != vkey else default_label
            elif idx == 0 and fragment_html and fragment_html.strip() and not extracted:
                vbody = fragment_html.strip()
                vlabel = default_label
            else:
                vbody = _starter_variant_body(vkey, default_label)
                vlabel = default_label
            variant_objs.append(ScaffoldVariant(key=vkey, label=vlabel, body_html=vbody))
    elif extracted:
        for vkey, ext_label, ext_body in extracted:
            variant_objs.append(
                ScaffoldVariant(
                    key=vkey,
                    label=ext_label or vkey,
                    body_html=ext_body or _starter_variant_body(vkey, ext_label or vkey),
                )
            )

    if variant_objs:
        page = ScaffoldPage(
            title=resolved_title,
            variants=tuple(variant_objs),
            theme=theme,
            home_aria_label=resolved_title,
        )
    else:
        body = (
            fragment_html.strip()
            if fragment_html is not None and fragment_html.strip()
            else (
                f'<section class="surface p-4">\n'
                f'  <h1 class="mt-0">{html.escape(resolved_title)}</h1>\n'
                f'  <p>Semantic prototype surface.</p>\n'
                f'</section>'
            )
        )
        page = ScaffoldPage(
            title=resolved_title,
            body_html=body,
            theme=theme,
            home_aria_label=resolved_title,
        )

    return render_static(page, static_prefix=static_prefix)
