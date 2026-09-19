"""Tests for the limit counter in the header."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

TEXT = {"text": "你好。", "lang": "ru"}


@pytest.mark.django_db
def test_header_shows_the_guest_limit(client: Client) -> None:
    html = client.get(reverse("core:home")).content.decode()

    assert "Осталось 5 из 5" in html


@pytest.mark.django_db
def test_header_shows_the_larger_limit_to_a_signed_in_user(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.get(reverse("core:home")).content.decode()

    assert "Осталось 30 из 30" in html


@pytest.mark.django_db
def test_the_counter_goes_down_after_a_submission(client: Client) -> None:
    client.post(reverse("reader:read"), TEXT)

    html = client.get(reverse("core:home")).content.decode()

    assert "Осталось 4 из 5" in html


@pytest.mark.django_db
def test_reading_the_counter_does_not_spend_it(client: Client) -> None:
    """The counter is rendered on every page, so a counting read would be fatal.

    Ten page views would eat twice a guest's hourly allowance without them ever
    submitting anything.
    """
    for _ in range(10):
        client.get(reverse("core:home"))

    html = client.get(reverse("core:home")).content.decode()

    assert "Осталось 5 из 5" in html


@pytest.mark.django_db
def test_an_exhausted_limit_is_marked_in_the_header(client: Client) -> None:
    for _ in range(5):
        client.post(reverse("reader:read"), TEXT)

    html = client.get(reverse("core:home")).content.decode()

    assert "Осталось 0 из 5" in html
    assert "quota--empty" in html
