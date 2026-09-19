"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.test import Client


@pytest.fixture
def client() -> Client:
    """Django test client for anonymous requests."""
    return Client()


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
