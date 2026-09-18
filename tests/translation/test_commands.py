"""Tests for the translation cache command."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.translation.models import SentenceTranslation

pytestmark = pytest.mark.django_db


@pytest.fixture
def cached() -> None:
    SentenceTranslation.objects.bulk_create(
        [
            SentenceTranslation(
                source_hash="a" * 64,
                target_language="ru",
                source_text="你好。",
                translated_text="你好。",
                provider="DummyProvider",
            ),
            SentenceTranslation(
                source_hash="b" * 64,
                target_language="ru",
                source_text="再见。",
                translated_text="пока",
                provider="DeepLProvider",
            ),
            SentenceTranslation(
                source_hash="c" * 64,
                target_language="en",
                source_text="你好。",
                translated_text="hello",
                provider="DeepLProvider",
            ),
        ]
    )


def test_clears_everything_by_default(cached: None) -> None:
    call_command("clear_translation_cache", stdout=StringIO())

    assert SentenceTranslation.objects.count() == 0


def test_clears_only_one_provider(cached: None) -> None:
    """The point of the command: drop placeholder translations, keep real ones."""
    call_command("clear_translation_cache", "--provider", "DummyProvider", stdout=StringIO())

    remaining = SentenceTranslation.objects.values_list("provider", flat=True)
    assert set(remaining) == {"DeepLProvider"}


def test_clears_only_one_language(cached: None) -> None:
    call_command("clear_translation_cache", "--language", "en", stdout=StringIO())

    assert SentenceTranslation.objects.filter(target_language="en").count() == 0
    assert SentenceTranslation.objects.filter(target_language="ru").count() == 2
