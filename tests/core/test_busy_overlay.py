"""Tests for the "please wait" overlay.

Only the markup can be checked from here: whether the overlay appears, whether a
second click is swallowed and whether the back button leaves it behind are all
browser behaviour, and those are verified by hand.

What these tests do guard is the contract between the templates and ``busy.js``:
the overlay is in the frame of every page, and exactly the slow buttons carry
``data-busy``. Get that wrong and the overlay silently never shows up.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.library.models import SavedText

pytestmark = pytest.mark.django_db

HOME = reverse("core:home")
READ = reverse("reader:read")
LISTEN = reverse("shadowing:listen")

# Открывающие теги кнопок. Искать целую строку с атрибутами нельзя: они
# переносятся по строкам и их порядок — дело вёрстки, а не контракта.
BUTTON_TAG = re.compile(r"<button[^>]*>")


def slow_buttons(html: str) -> list[str]:
    """Return the opening tag of every button marked as slow."""
    return [tag for tag in BUTTON_TAG.findall(html) if "data-busy=" in tag]


@pytest.mark.parametrize("url", [HOME, READ, LISTEN])
def test_every_page_carries_the_overlay(client: Client, url: str) -> None:
    """It comes from base.html, so no page has to remember to include it."""
    html = client.get(url).content.decode()

    assert 'id="busy"' in html


def test_the_library_carries_the_overlay(client: Client, user: User) -> None:
    """Separate from the rest because the library needs a signed-in user."""
    client.force_login(user)

    html = client.get(reverse("library:list")).content.decode()

    assert 'id="busy"' in html


def test_the_overlay_arrives_hidden(client: Client) -> None:
    """Rendered open it would cover the page for everyone, JS or no JS."""
    html = client.get(HOME).content.decode()

    assert 'class="busy"' in html
    assert "is-on" not in html


def test_the_script_is_loaded(client: Client) -> None:
    html = client.get(HOME).content.decode()

    assert "js/busy.js" in html


def test_the_input_card_marks_both_buttons(client: Client) -> None:
    """Both destinations wait on the server, so both say so."""
    html = client.get(HOME).content.decode()

    assert len(slow_buttons(html)) == 2


def test_the_input_card_names_the_two_waits_differently(client: Client) -> None:
    """One waits for a translation, the other for speech — and they differ in length.

    Checked by substring rather than by the whole sentence: the wording will be
    edited, and a test should not fail over that.
    """
    html = client.get(HOME).content.decode()
    by_destination = {
        "shadowing" if f'formaction="{LISTEN}"' in tag else "reader": tag
        for tag in slow_buttons(html)
    }

    assert "озвуч" in by_destination["shadowing"]
    assert "перев" in by_destination["reader"]


def test_the_library_marks_the_opening_buttons_only(client: Client, user: User) -> None:
    """Renaming, moving and creating a collection are instant.

    An overlay there would claim a wait that never happens, so the count is the
    test: two buttons open a text, everything else on the page stays unmarked.
    """
    client.force_login(user)
    SavedText.objects.create(owner=user, title="Банк", content="我去银行。")

    html = client.get(reverse("library:list")).content.decode()

    assert len(slow_buttons(html)) == 2


def test_the_reader_marks_the_button_that_leads_to_shadowing(client: Client) -> None:
    """It sits in the header, outside the form it submits, and is bound by id."""
    html = client.post(READ, {"text": "我去。", "lang": "ru"}).content.decode()
    marked = [tag for tag in slow_buttons(html) if f'formaction="{LISTEN}"' in tag]

    assert marked
    assert 'form="language-form"' in marked[0]


def test_the_language_form_carries_its_own_label(client: Client) -> None:
    """Switching the language re-translates everything, which takes just as long.

    The label goes on the form because the segments are ``type="button"`` and
    ``reader.js`` submits with ``requestSubmit()`` — there is no pressed button
    for the script to read it from.
    """
    html = client.post(READ, {"text": "我去。", "lang": "ru"}).content.decode()

    assert re.search(r'<form[^>]*id="language-form"[^>]*data-busy=', html, re.DOTALL)


def test_shadowing_marks_the_way_back_to_the_reader(client: Client) -> None:
    html = client.post(LISTEN, {"text": "我去。"}).content.decode()

    assert len(slow_buttons(html)) == 1
