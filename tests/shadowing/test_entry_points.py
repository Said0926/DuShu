"""Tests for the four places that lead into shadowing.

They are all plain form submits with ``formaction``, so what matters is that the
address is right and that the hidden fields travel with it — no JS involved.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.library.models import Collection, SavedText

pytestmark = pytest.mark.django_db

LISTEN = reverse("shadowing:listen")


def test_the_navigation_points_at_the_page(client: Client) -> None:
    """It used to lead to the "coming soon" placeholder."""
    html = client.get(reverse("core:home")).content.decode()

    assert f'href="{LISTEN}"' in html


def test_the_landing_card_can_submit_to_shadowing(client: Client) -> None:
    html = client.get(reverse("core:home")).content.decode()

    assert f'formaction="{LISTEN}"' in html


def test_the_reader_offers_the_same_text(client: Client) -> None:
    """The button lives in the header and submits the sidebar form by its id."""
    html = client.post(reverse("reader:read"), {"text": "我去。", "lang": "ru"}).content.decode()

    assert f'formaction="{LISTEN}"' in html
    assert 'form="language-form"' in html


def test_the_reader_carries_the_title_onwards(client: Client, user: User) -> None:
    """Without this a saved text would arrive at shadowing unnamed."""
    client.force_login(user)

    response = client.post(
        reverse("reader:read"),
        {"text": "我去。", "lang": "ru", "title": "Про банк", "saved": "1", "saved_id": "3"},
    )
    html = response.content.decode()

    assert 'name="title" value="Про банк"' in html


def test_the_library_offers_shadowing_for_a_saved_text(client: Client, user: User) -> None:
    client.force_login(user)
    collection = Collection.objects.create(owner=user, title="Моё")
    SavedText.objects.create(owner=user, title="Банк", content="我去银行。", collection=collection)

    html = client.get(reverse("library:list")).content.decode()

    assert f'formaction="{LISTEN}"' in html


def test_shadowing_offers_the_way_back_to_the_reader(client: Client) -> None:
    html = client.post(LISTEN, {"text": "我去。"}).content.decode()

    assert f'action="{reverse("reader:read")}"' in html
