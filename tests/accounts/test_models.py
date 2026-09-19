"""Tests for the custom user model and its manager."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import User


def test_project_uses_the_custom_user_model() -> None:
    """A regression guard: switching AUTH_USER_MODEL later requires recreating the DB."""
    assert get_user_model() is User


def test_email_is_the_login_identifier() -> None:
    """allauth, the admin and createsuperuser all read USERNAME_FIELD."""
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []


def test_username_field_is_gone() -> None:
    """The field is removed, not merely unused, so nothing can start filling it again."""
    field_names = {field.name for field in User._meta.get_fields()}

    assert "username" not in field_names


@pytest.mark.django_db
def test_user_str_returns_email() -> None:
    user = User.objects.create_user(email="li@example.com", password="secret")

    assert str(user) == "li@example.com"


@pytest.mark.django_db
def test_create_user_lowercases_the_domain() -> None:
    """Mail.RU and mail.ru are one address, but a unique index would accept both."""
    user = User.objects.create_user(email="Li@Mail.RU", password="secret")

    assert user.email == "Li@mail.ru"


@pytest.mark.django_db
def test_create_user_without_email_is_rejected() -> None:
    """Without an email there is no way to log in at all."""
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="secret")


@pytest.mark.django_db
def test_create_user_without_password_gets_an_unusable_one() -> None:
    """This is the shape of a Google-only account: it exists, but no password works."""
    user = User.objects.create_user(email="li@example.com")

    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_superuser_sets_both_flags() -> None:
    user = User.objects.create_superuser(email="root@example.com", password="secret")

    assert user.is_staff
    assert user.is_superuser


@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_a_cleared_flag(flag: str) -> None:
    """Passed explicitly, a false flag would produce an admin that cannot open the admin."""
    with pytest.raises(ValueError, match=flag):
        User.objects.create_superuser(email="root@example.com", password="secret", **{flag: False})
