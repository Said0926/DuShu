"""Tests for the limit on processing texts and on dictionary lookups."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

TEXT = {"text": "你好。", "lang": "ru"}


def _submit(client: Client) -> int:
    return client.post(reverse("reader:read"), TEXT).status_code


@pytest.mark.django_db
def test_a_guest_runs_out_after_the_configured_number(client: Client) -> None:
    codes = [_submit(client) for _ in range(6)]

    assert codes == [200, 200, 200, 200, 200, 429]


@pytest.mark.django_db
def test_a_signed_in_user_gets_further(client: Client, user: User) -> None:
    """The whole point of the two rates: the guest limit must not apply here."""
    client.force_login(user)

    codes = [_submit(client) for _ in range(6)]

    assert codes == [200] * 6


@pytest.mark.django_db
def test_opening_the_page_does_not_spend_the_limit(client: Client) -> None:
    """The decorator sits on post(), so a GET never reaches it."""
    for _ in range(10):
        client.get(reverse("reader:read"))

    assert _submit(client) == 200


@pytest.mark.django_db
def test_the_limit_page_invites_a_guest_to_register(client: Client) -> None:
    for _ in range(6):
        response = client.post(reverse("reader:read"), TEXT)

    html = response.content.decode()

    assert response.status_code == 429
    assert reverse("account_signup") in html


@pytest.mark.django_db
def test_the_limit_page_does_not_invite_a_signed_in_user(
    client: Client, user: User, settings: pytest.FixtureRequest
) -> None:
    """Nothing to offer someone who already registered — they are on the top tier."""
    settings.RATELIMIT_TEXT_USER = "2/h"
    client.force_login(user)

    for _ in range(3):
        response = client.post(reverse("reader:read"), TEXT)

    assert response.status_code == 429
    assert reverse("account_signup") not in response.content.decode()


@pytest.mark.django_db
def test_lookups_are_limited_separately(client: Client, settings: pytest.FixtureRequest) -> None:
    """Tooltips cost nothing, so they get their own, much softer counter.

    Sharing one counter with text processing would mean a few dozen hovers could
    lock a visitor out of reading anything at all.
    """
    settings.RATELIMIT_LOOKUP_GUEST = "2/m"
    url = reverse("reader:lookup")

    codes = [client.get(url, {"word": "你好", "lang": "ru"}).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    # Лимит на тексты при этом не тронут.
    assert _submit(client) == 200


@pytest.mark.django_db
def test_a_limited_lookup_answers_in_json(client: Client, settings: pytest.FixtureRequest) -> None:
    """tooltip.js reads this with fetch, so an HTML page would be unreadable to it."""
    settings.RATELIMIT_LOOKUP_GUEST = "1/m"
    url = reverse("reader:lookup")

    client.get(url, {"word": "你好", "lang": "ru"})
    response = client.get(url, {"word": "喝茶", "lang": "ru"})

    assert response.status_code == 429
    assert response.json()["error"] == "rate_limited"
