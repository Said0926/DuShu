"""Tests for the allauth sign-up, login and logout flow.

These check the wiring rather than allauth itself: that login really goes by
email, that an unconfirmed address cannot get in, and that the redirects land
where the settings say they should.
"""

import pytest
from django.contrib.auth import get_user
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_signup_creates_a_user_but_does_not_let_them_in(client: Client, password: str) -> None:
    """ACCOUNT_EMAIL_VERIFICATION is "mandatory": the account waits for the link."""
    response = client.post(
        reverse("account_signup"),
        {"email": "new@example.com", "password1": password, "password2": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("account_email_verification_sent")
    assert User.objects.filter(email="new@example.com").exists()
    assert not get_user(client).is_authenticated


@pytest.mark.django_db
def test_signup_sends_the_confirmation_email(client: Client, password: str) -> None:
    client.post(
        reverse("account_signup"),
        {"email": "new@example.com", "password1": password, "password2": password},
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@example.com"]


@pytest.mark.django_db
def test_signup_with_a_taken_email_creates_nothing(
    client: Client, user: User, password: str
) -> None:
    """The answer deliberately looks like success.

    allauth hides whether an address is registered — a form error saying "taken"
    would turn the sign-up page into a tool for checking who has an account here.
    """
    response = client.post(
        reverse("account_signup"),
        {"email": user.email, "password1": password, "password2": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("account_email_verification_sent")
    assert User.objects.filter(email=user.email).count() == 1


@pytest.mark.django_db
def test_login_by_email_works(client: Client, user: User, password: str) -> None:
    """The login field holds an email: ACCOUNT_LOGIN_METHODS is {"email"}."""
    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": password},
    )

    assert response.status_code == 302
    assert get_user(client) == user


@pytest.mark.django_db
def test_login_is_refused_until_the_email_is_confirmed(
    client: Client, unverified_user: User, password: str
) -> None:
    """The password is right; the address is not confirmed, so the door stays shut."""
    response = client.post(
        reverse("account_login"),
        {"login": unverified_user.email, "password": password},
    )

    assert response.status_code == 302
    assert response.url == reverse("account_email_verification_sent")
    assert not get_user(client).is_authenticated


@pytest.mark.django_db
def test_login_with_a_wrong_password_fails(client: Client, user: User) -> None:
    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": "not-the-password"},
    )

    assert response.status_code == 200
    assert not get_user(client).is_authenticated


@pytest.mark.django_db
def test_logout_returns_to_the_home_page(client: Client, user: User) -> None:
    """Logout is POST-only by default, which is what keeps CSRF meaningful."""
    client.force_login(user)

    response = client.post(reverse("account_logout"))

    assert response.status_code == 302
    assert response.url == "/"
    assert not get_user(client).is_authenticated
