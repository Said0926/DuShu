"""Tests for the Google sign-in wiring.

The point of these is the on/off switch: the button must appear exactly when
credentials are present in the environment, and stay away when they are not.
Without that, a project cloned without keys would show a button leading to an
allauth error page.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User

PASSWORD = "very-secret-passphrase"

GOOGLE_APP = {
    "google": {
        "SCOPE": ["profile", "email"],
        "APP": {"client_id": "test-client-id", "secret": "test-secret", "key": ""},
    }
}


@pytest.fixture
def google_configured(settings: pytest.FixtureRequest) -> None:
    """Pretend GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are filled in."""
    settings.SOCIALACCOUNT_PROVIDERS = GOOGLE_APP


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(email="li@example.com", password=PASSWORD)


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["account_login", "account_signup"])
def test_button_is_hidden_without_credentials(client: Client, url_name: str) -> None:
    """Default test settings carry no APP section, which is how allauth knows."""
    html = client.get(reverse(url_name)).content.decode()

    assert "Google" not in html


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["account_login", "account_signup"])
def test_button_appears_when_credentials_are_set(
    client: Client, google_configured: None, url_name: str
) -> None:
    html = client.get(reverse(url_name)).content.decode()

    assert "Google" in html
    # Форма, а не ссылка: на GET allauth показал бы лишнюю страницу-подтверждение.
    assert 'class="auth__social" method="post"' in html
    assert f"{reverse('google_login')}?process=login" in html


@pytest.mark.django_db
def test_profile_hides_the_google_row_without_credentials(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.get(reverse("accounts:profile")).content.decode()

    assert "Google" not in html


@pytest.mark.django_db
def test_profile_offers_to_connect_google(
    client: Client, user: User, google_configured: None
) -> None:
    client.force_login(user)

    html = client.get(reverse("accounts:profile")).content.decode()

    assert "не привязан" in html
    assert f"{reverse('google_login')}?process=connect" in html


@pytest.mark.django_db
def test_profile_offers_to_set_a_password_when_there_is_none(client: Client) -> None:
    """This is what a Google-only account looks like: nothing to change, only to set."""
    user = User.objects.create_user(email="google-only@example.com")
    client.force_login(user)

    html = client.get(reverse("accounts:profile")).content.decode()

    assert reverse("account_set_password") in html
    assert reverse("account_change_password") not in html
