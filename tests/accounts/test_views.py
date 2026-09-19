"""Tests for the profile page and for the account templates in the site's shell."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

PASSWORD = "very-secret-passphrase"


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(email="li@example.com", password=PASSWORD)


@pytest.mark.django_db
def test_profile_requires_login(client: Client) -> None:
    """LoginRequiredMixin sends the visitor to the login page and remembers where to return."""
    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert response.url == f"{reverse('account_login')}?next={reverse('accounts:profile')}"


@pytest.mark.django_db
def test_profile_shows_the_email(client: Client, user: User) -> None:
    client.force_login(user)

    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 200
    assert user.email in response.content.decode()


@pytest.mark.django_db
def test_header_offers_login_to_a_guest(client: Client) -> None:
    html = client.get(reverse("core:home")).content.decode()

    assert reverse("account_login") in html
    assert reverse("accounts:profile") not in html


@pytest.mark.django_db
def test_header_links_to_the_profile_when_signed_in(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.get(reverse("core:home")).content.decode()

    assert reverse("accounts:profile") in html


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["account_login", "account_signup", "account_reset_password"])
def test_account_pages_use_the_project_shell(client: Client, url_name: str) -> None:
    """A guard on templates/allauth/layouts/base.html.

    If that override stops being found, the pages still work but silently lose
    the site header, footer and styles — a regression easy to miss in tests that
    only check status codes.
    """
    html = client.get(reverse(url_name)).content.decode()

    assert "auth__card" in html
    assert "site-header" in html


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["account_login", "account_signup"])
def test_account_forms_have_no_placeholders(client: Client, url_name: str) -> None:
    """A guard on ACCOUNT_FORMS.

    allauth fills every placeholder with the field's own label. Our templates
    render labels, so a placeholder would print the same words twice.
    """
    html = client.get(reverse(url_name)).content.decode()

    assert "placeholder=" not in html
