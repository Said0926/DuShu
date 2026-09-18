"""Tests for the landing page and the placeholder view."""

from django.conf import settings
from django.test import Client
from django.urls import reverse


def test_home_page_renders(client: Client) -> None:
    """The landing page is reachable and uses the expected template."""
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "core/home.html" in [template.name for template in response.templates]


def test_home_page_exposes_text_limit(client: Client) -> None:
    """The character counter needs the limit from settings, not a hardcoded number."""
    response = client.get(reverse("core:home"))

    assert response.context["max_text_length"] == settings.MAX_TEXT_LENGTH


def test_home_page_lists_every_configured_language(client: Client) -> None:
    """Adding a language to settings must be enough to show it in the UI."""
    response = client.get(reverse("core:home"))

    assert response.context["translation_languages"] == settings.TRANSLATION_LANGUAGES
    for label in settings.TRANSLATION_LANGUAGES.values():
        assert label in response.content.decode()


def test_default_language_is_a_configured_one() -> None:
    """A default that is not in the registry would break the language switcher."""
    assert settings.DEFAULT_TRANSLATION_LANGUAGE in settings.TRANSLATION_LANGUAGES


def test_coming_soon_page_renders(client: Client) -> None:
    """Navigation links point here until the real pages exist."""
    response = client.get(reverse("core:coming-soon"))

    assert response.status_code == 200
