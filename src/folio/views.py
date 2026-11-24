"""Django views for the Folio reference gallery and catalogue."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse

from folio.catalogue import build_catalogue_detail_page, build_catalogue_page
from folio.contracts import PrintMode, ThemeMode
from folio.fixtures import get_pattern_page
from folio.navigation import PATTERN_KEYS, build_gallery_nav, resolve_pattern_key
from folio.renderer import render


def _parse_theme_and_print(request: HttpRequest) -> tuple[ThemeMode, PrintMode]:
    raw_theme = request.GET.get("theme", "light")
    theme: ThemeMode = "dark" if raw_theme == "dark" else "light"
    raw_print = request.GET.get("print", "colour")
    print_mode: PrintMode = raw_print if raw_print in {"colour", "greyscale", "black-white"} else "colour"  # type: ignore[assignment]
    return theme, print_mode


def _gallery_nav(active_key: str, theme: ThemeMode) -> dict[str, object]:
    hrefs = {key: f"/?page={key}&theme={theme}" for key in (*PATTERN_KEYS, "elements")}
    return build_gallery_nav(
        active_key,
        hrefs=hrefs,
        catalogue_href=f"/catalogue/?theme={theme}",
    )


def gallery_view(request: HttpRequest) -> HttpResponse:
    """Render any of the 7 reference patterns or the elements view."""
    raw_page = request.GET.get("page", "launchpad")
    theme, print_mode = _parse_theme_and_print(request)

    if raw_page == "elements":
        cat_page = build_catalogue_page(theme=theme, print_mode=print_mode)
        return render(
            request,
            cat_page,
            extra_context={
                "gallery_nav": _gallery_nav("elements", theme),
                "show_print_selector": True,
            },
        )

    key = resolve_pattern_key(raw_page, default="launchpad")
    page = get_pattern_page(key, theme=theme, print_mode=print_mode)
    extra = {}
    if not getattr(page, "is_stage1_shell", False):
        extra = {
            "gallery_nav": _gallery_nav(key, theme),
            "show_print_selector": True,
        }
    return render(request, page, extra_context=extra)


def catalogue_index_view(request: HttpRequest) -> HttpResponse:
    """Render the single-source SK Design System element catalogue."""
    theme, print_mode = _parse_theme_and_print(request)
    page = build_catalogue_page(theme=theme, print_mode=print_mode)
    return render(
        request,
        page,
        extra_context={
            "gallery_nav": _gallery_nav("elements", theme),
            "show_print_selector": True,
        },
    )


def catalogue_detail_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Render a single catalogue entry detail page."""
    theme, print_mode = _parse_theme_and_print(request)
    try:
        page = build_catalogue_detail_page(slug, theme=theme, print_mode=print_mode)
    except KeyError as exc:
        raise Http404(str(exc)) from exc
    return render(
        request,
        page,
        extra_context={
            "gallery_nav": _gallery_nav("elements", theme),
            "show_print_selector": True,
        },
    )
