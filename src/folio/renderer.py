"""Dual rendering adapters for Django HTTP/HTMX and standalone static HTML."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import django
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string


def ensure_django_setup() -> None:
    """Configure minimal in-memory Django settings when Folio is used standalone."""
    if settings.configured:
        return
    settings.configure(
        DEBUG=False,
        SECRET_KEY="folio-standalone-renderer",
        INSTALLED_APPS=["folio"],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [],
                },
            }
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        STATIC_URL="/static/",
        USE_TZ=True,
    )
    django.setup()


def _resolve_asset_urls(static_prefix: str | None = None) -> dict[str, str]:
    if static_prefix is None:
        try:
            from django.templatetags.static import static

            return {
                "bootstrap_css": static("folio/vendor/bootstrap.min.css"),
                "sk_css": static("folio/css/sk-design-system.css"),
                "bootstrap_js": static("folio/vendor/bootstrap.bundle.min.js"),
                "folio_js": static("folio/js/folio.js"),
            }
        except Exception:
            prefix = "/static/folio/"
    else:
        prefix = static_prefix if static_prefix.endswith("/") else f"{static_prefix}/"

    return {
        "bootstrap_css": f"{prefix}vendor/bootstrap.min.css",
        "sk_css": f"{prefix}css/sk-design-system.css",
        "bootstrap_js": f"{prefix}vendor/bootstrap.bundle.min.js",
        "folio_js": f"{prefix}js/folio.js",
    }


def _build_context(
    page: Any,
    *,
    asset_urls: dict[str, str],
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "page": page,
        "lang": getattr(page, "lang", "en-GB"),
        "meta_description": getattr(page, "meta_description", ""),
        "canonical_url": getattr(page, "canonical_url", ""),
        "author_meta": getattr(page, "author_meta", ""),
        "citation_date": getattr(page, "citation_date", ""),
        "include_scripts": getattr(page, "include_scripts", True),
        "page_title": getattr(page, "title", "SK Design System"),
        "theme": getattr(page, "theme", "light"),
        "print_mode": getattr(page, "print_mode", "colour"),
        "partial_template": getattr(page, "partial_template"),
        "body_classes": getattr(page, "body_classes", ""),
        "asset_urls": asset_urls,
        "show_theme_toggle": getattr(page, "show_theme_toggle", True),
        "home_href": getattr(page, "home_href", "?page=launchpad"),
        "home_aria_label": getattr(page, "home_aria_label", "SK launchpad"),
        "socials": getattr(page, "socials", ()),
        "socials_aria_label": getattr(
            page, "socials_aria_label", "Social and academic profiles"
        ),
        "footer_copyright": getattr(page, "footer_copyright", ""),
        "footer_note": getattr(page, "footer_note", ""),
        "footer_source_url": getattr(page, "footer_source_url", ""),
        "footer_source_label": getattr(page, "footer_source_label", "open source"),
        "is_stage1_shell": getattr(page, "is_stage1_shell", False),
    }
    if hasattr(page, "to_json_data"):
        context["page_json_data"] = page.to_json_data()
    elif hasattr(page, "periods"):
        context["page_json_data"] = {
            p.period_key: asdict(p) for p in page.periods
        }
    if extra_context:
        context.update(extra_context)
    return context


def render(
    request: HttpRequest,
    page: Any,
    *,
    status: int = 200,
    partial: bool | None = None,
    extra_context: dict[str, Any] | None = None,
) -> HttpResponse:
    """Render a typed Folio page or HTMX partial into a Django HttpResponse."""
    ensure_django_setup()
    is_partial = (
        partial
        if partial is not None
        else request.headers.get("HX-Request", "").lower() == "true"
    )
    template_name = (
        getattr(page, "partial_template") if is_partial else "folio/base.html"
    )
    context = _build_context(
        page,
        asset_urls=_resolve_asset_urls(None),
        extra_context=extra_context,
    )
    html = render_to_string(template_name, context, request=request)
    return HttpResponse(html, status=status)


def render_static(
    page: Any,
    *,
    static_prefix: str = "/static/folio/",
    asset_urls: dict[str, str] | None = None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Render a complete standalone HTML string for a typed Folio page."""
    ensure_django_setup()
    resolved_assets = asset_urls or _resolve_asset_urls(static_prefix)
    context = _build_context(
        page,
        asset_urls=resolved_assets,
        extra_context=extra_context,
    )
    return render_to_string("folio/base.html", context)
