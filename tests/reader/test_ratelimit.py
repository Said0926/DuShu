"""Tests for the limit on processing texts and on dictionary lookups."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

TEXT = {"text": "你好。", "lang": "ru"}


def _new_text(number: int) -> dict[str, str]:
    """A text nobody has translated yet.

    Every test that means to spend the limit needs distinct texts: a repeated
    one is answered from the translation cache and deliberately costs nothing.
    """
    return {"text": f"这是第{number}句话。", "lang": "ru"}


def _submit(client: Client, number: int = 0) -> int:
    return client.post(reverse("reader:read"), _new_text(number)).status_code


@pytest.mark.django_db
def test_a_guest_runs_out_after_the_configured_number(client: Client) -> None:
    codes = [_submit(client, number) for number in range(6)]

    assert codes == [200, 200, 200, 200, 200, 429]


@pytest.mark.django_db
def test_a_signed_in_user_gets_further(client: Client, user: User) -> None:
    """The whole point of the two rates: the guest limit must not apply here."""
    client.force_login(user)

    codes = [_submit(client, number) for number in range(6)]

    assert codes == [200] * 6


@pytest.mark.django_db
def test_opening_the_page_does_not_spend_the_limit(client: Client) -> None:
    """The decorator sits on post(), so a GET never reaches it."""
    for _ in range(10):
        client.get(reverse("reader:read"))

    assert _submit(client) == 200


@pytest.mark.django_db
def test_rereading_a_cached_text_is_free(client: Client) -> None:
    """Reopening costs nothing, so the library is not capped at a few opens an hour.

    The limit guards the translation budget. A text whose sentences are all in
    the cache never reaches the provider, so counting it would be counting
    nothing.
    """
    assert _submit(client, 1) == 200

    codes = [_submit(client, 1) for _ in range(20)]

    assert codes == [200] * 20


@pytest.mark.django_db
def test_the_limit_page_invites_a_guest_to_register(client: Client) -> None:
    for number in range(6):
        response = client.post(reverse("reader:read"), _new_text(number))

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

    for number in range(3):
        response = client.post(reverse("reader:read"), _new_text(number))

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
