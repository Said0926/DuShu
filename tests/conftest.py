"""Shared pytest fixtures."""

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    """Django test client for anonymous requests."""
    return Client()
