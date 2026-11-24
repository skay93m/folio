"""Slice 1 tests: Launchpad contract validation and dual rendering seams."""

from dataclasses import FrozenInstanceError

import pytest
from django.test import RequestFactory

import folio
from folio.contracts import Launchpad, LaunchpadCard


def _sample_launchpad(**overrides) -> Launchpad:
    defaults = {
        "title": "Launchpad",
        "intro": "Choose one activity and give it your full attention.",
        "cards": (
            LaunchpadCard(
                title="Overview",
                description="See progress, changes and the work that needs your attention.",
                href="?page=dashboard",
                status_role="info",
                status_label="Ready",
            ),
        ),
    }
    defaults.update(overrides)
    return Launchpad(**defaults)


def test_launchpad_is_immutable_and_validates_fields():
    page = _sample_launchpad()
    with pytest.raises(FrozenInstanceError):
        page.title = "Changed"  # type: ignore[misc]

    with pytest.raises(ValueError, match="home_aria_label"):
        _sample_launchpad(home_aria_label="   ")

    with pytest.raises(ValueError, match="sentence-case"):
        _sample_launchpad(title="LAUNCHPAD")

    with pytest.raises(ValueError, match="semantic role"):
        _sample_launchpad(
            cards=(
                LaunchpadCard(
                    title="Overview",
                    description="Valid description",
                    href="?page=dashboard",
                    status_role="urgent",  # type: ignore[arg-type]
                ),
            )
        )

    with pytest.raises(ValueError, match="theme"):
        _sample_launchpad(theme="sepia")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="print_mode"):
        _sample_launchpad(print_mode="sepia")  # type: ignore[arg-type]


def test_launchpad_renders_via_static_and_django_http_adapters():
    page = _sample_launchpad()
    static_html = folio.render_static(page)
    assert "<!doctype html>" in static_html.lower()
    assert 'data-bs-theme="light"' in static_html
    assert 'data-print-mode="colour"' in static_html
    assert "sk-design-system.css" in static_html
    assert "Overview" in static_html
    assert 'aria-label="SK launchpad"' in static_html

    rf = RequestFactory()
    request = rf.get("/?page=launchpad")
    response = folio.render(request, page)
    assert response.status_code == 200
    assert "Overview" in response.content.decode("utf-8")

    htmx_request = rf.get("/?page=launchpad", HTTP_HX_REQUEST="true")
    partial_response = folio.render(htmx_request, page)
    partial_body = partial_response.content.decode("utf-8")
    assert "<!doctype html>" not in partial_body.lower()
    assert "Overview" in partial_body


def test_two_door_dialog_contract():
    from folio import Dialog, HeaderAction

    page = _sample_launchpad(
        cards=(_sample_launchpad().cards[0], LaunchpadCard("Review", "Defend an answer.", "/review/")),
        layout="two-door",
        show_theme_toggle=False,
        header_actions=(HeaderAction("Session tools", "tools"),),
        dialogs=(Dialog("tools", "Session tools", "folio/includes/elements/empty_state.html"),),
    )
    for html in (
        folio.render_static(page),
        folio.render(RequestFactory().get("/"), page).content.decode("utf-8"),
    ):
        assert "col-md-6" in html
        assert "sk-two-door" in html
        assert 'aria-controls="tools"' in html
        assert 'data-folio-dialog="tools"' in html
        assert '<dialog class="sk-dialog" id="tools" aria-labelledby="tools-title"' in html
        assert 'aria-label="Close Session tools"' in html
        assert 'id="theme-toggle"' not in html

    with pytest.raises(ValueError, match="two"):
        _sample_launchpad(layout="two-door")
    with pytest.raises(ValueError, match="dialog"):
        _sample_launchpad(header_actions=(HeaderAction("Tools", "missing"),))
    with pytest.raises(ValueError, match="unique"):
        _sample_launchpad(dialogs=page.dialogs * 2)
    with pytest.raises(ValueError, match="shell"):
        _sample_launchpad(dialogs=(Dialog("main", "Tools", "unused.html"),))
    with pytest.raises(ValueError, match="dialog ID"):
        HeaderAction("Tools", "two words")
    with pytest.raises(ValueError, match="label"):
        HeaderAction(" ", "tools")
