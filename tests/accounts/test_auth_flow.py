"""Tests for the allauth sign-up, login and logout flow.

These check the wiring rather than allauth itself: that login really goes by
email, that the confirmation mail is sent, and that the redirects land where the
settings say they should.
"""

import pytest
from django.contrib.auth import get_user
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

PASSWORD = "very-secret-passphrase"


@pytest.fixture
def user(db: None) -> User:
    """A registered user, ready to log in."""
    return User.objects.create_user(email="li@example.com", password=PASSWORD)


@pytest.mark.django_db
def test_signup_creates_a_user_and_logs_them_in(client: Client) -> None:
    response = client.post(
        reverse("account_signup"),
        {
            "email": "new@example.com",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert User.objects.filter(email="new@example.com").exists()
    assert get_user(client).is_authenticated


@pytest.mark.django_db
def test_signup_sends_the_confirmation_email(client: Client) -> None:
    """ACCOUNT_EMAIL_VERIFICATION is "optional": the mail is sent, login still works."""
    client.post(
        reverse("account_signup"),
        {"email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@example.com"]


@pytest.mark.django_db
def test_signup_rejects_an_email_that_is_taken(client: Client, user: User) -> None:
    response = client.post(
        reverse("account_signup"),
        {"email": user.email, "password1": PASSWORD, "password2": PASSWORD},
    )

    # Форма возвращается со своей ошибкой, а не редиректом на успех.
    assert response.status_code == 200
    assert User.objects.filter(email=user.email).count() == 1


@pytest.mark.django_db
def test_login_by_email_works(client: Client, user: User) -> None:
    """The login field holds an email: ACCOUNT_LOGIN_METHODS is {"email"}."""
    response = client.post(
        reverse("account_login"),
        {"login": user.email, "password": PASSWORD},
    )

    assert response.status_code == 302
    assert get_user(client) == user


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
