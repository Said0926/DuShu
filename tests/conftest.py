"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import User

USER_PASSWORD = "very-secret-passphrase"


@pytest.fixture
def client() -> Client:
    """Django test client for anonymous requests."""
    return Client()


@pytest.fixture
def password() -> str:
    """The password every test user is created with."""
    return USER_PASSWORD


@pytest.fixture
def user(db: None) -> User:
    """A fully registered user: password set and email address confirmed.

    The confirmed ``EmailAddress`` is what makes this user able to log in at
    all: ``ACCOUNT_EMAIL_VERIFICATION`` is "mandatory", and allauth checks the
    address, not the user record.
    """
    user = User.objects.create_user(email="li@example.com", password=USER_PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    return user


@pytest.fixture
def unverified_user(db: None) -> User:
    """A user who signed up but never followed the link from the email."""
    return User.objects.create_user(email="pending@example.com", password=USER_PASSWORD)


@pytest.fixture(autouse=True)
def clear_cache() -> Iterator[None]:
    """Wipe the Django cache around every test.

    Both allauth and django-ratelimit keep their counters in the cache, and in
    tests that cache is a single in-process LocMemCache shared by the whole run.
    Without this fixture one test's sign-up eats allauth's "confirm_email" limit
    and the next test silently receives no mail — a failure that reads like
    broken code rather than leaked state.
    """
    cache.clear()
    yield
    cache.clear()
