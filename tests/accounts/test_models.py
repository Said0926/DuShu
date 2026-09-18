"""Tests for the custom user model."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import User


def test_project_uses_the_custom_user_model() -> None:
    """A regression guard: switching AUTH_USER_MODEL later requires recreating the DB."""
    assert get_user_model() is User


@pytest.mark.django_db
def test_user_str_returns_username() -> None:
    user = User.objects.create_user(username="li", password="secret")

    assert str(user) == "li"
