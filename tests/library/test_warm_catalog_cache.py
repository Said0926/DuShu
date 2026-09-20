"""Tests for warming the shared catalog.

The point of warming is that a cache hit never reaches a provider: once the
shared texts are translated and spoken, opening one is free and instant for
everybody. So what is checked here is the cache filling up, staying filled, and
surviving a provider that fails.
"""

from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.library.models import Collection, SavedText
from apps.translation.exceptions import TranslationError
from apps.translation.models import SentenceTranslation
from apps.tts.exceptions import TTSError
from apps.tts.models import SentenceAudio

pytestmark = pytest.mark.django_db

CONTENT = "我叫小明。我很高兴。"


@pytest.fixture
def catalog_text() -> SavedText:
    """One shared text on the HSK 1 shelf."""
    return SavedText.objects.create(
        owner=None,
        title="我的一天",
        content=CONTENT,
        content_hash="a" * 64,
        collection=Collection.objects.get(owner__isnull=True, hsk_level=1),
    )


def test_warming_fills_both_caches(catalog_text: SavedText) -> None:
    call_command("warm_catalog_cache")

    # Два предложения на каждый из языков сайта, плюс два аудио.
    assert SentenceTranslation.objects.count() == 4
    assert SentenceAudio.objects.count() == 2


def test_warming_one_language_leaves_the_other_alone(catalog_text: SavedText) -> None:
    call_command("warm_catalog_cache", "--language", "ru")

    assert set(SentenceTranslation.objects.values_list("target_language", flat=True)) == {"ru"}


def test_each_half_can_be_skipped(catalog_text: SavedText) -> None:
    call_command("warm_catalog_cache", "--skip-audio")

    assert SentenceTranslation.objects.exists()
    assert not SentenceAudio.objects.exists()


def test_warming_twice_asks_the_provider_nothing(catalog_text: SavedText, monkeypatch: Any) -> None:
    """The second run must be free: that is the whole point of the cache."""
    call_command("warm_catalog_cache")

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a warmed text must not reach a provider again")

    monkeypatch.setattr("apps.translation.services.get_provider", refuse)
    monkeypatch.setattr("apps.tts.services.get_provider", refuse)

    call_command("warm_catalog_cache")


def test_one_failing_text_does_not_stop_the_run(
    catalog_text: SavedText, monkeypatch: Any
) -> None:
    """A run of fifty texts must survive one 503 from an unofficial endpoint."""
    collection = Collection.objects.get(owner__isnull=True, hsk_level=2)
    SavedText.objects.create(
        owner=None, title="第二", content="我去学校。", content_hash="b" * 64, collection=collection
    )

    def fail(*args: Any, **kwargs: Any) -> None:
        raise TTSError("the endpoint said 503")

    monkeypatch.setattr(
        "apps.library.management.commands.warm_catalog_cache.get_sentence_audio", fail
    )

    call_command("warm_catalog_cache")

    # Озвучка не вышла ни у одного, а перевод всё равно доехал у обоих.
    assert not SentenceAudio.objects.exists()
    assert SentenceTranslation.objects.exists()


def test_a_failing_translation_does_not_stop_the_run(
    catalog_text: SavedText, monkeypatch: Any
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise TranslationError("the key is gone")

    monkeypatch.setattr(
        "apps.library.management.commands.warm_catalog_cache.translate_sentences", fail
    )

    call_command("warm_catalog_cache")

    assert not SentenceTranslation.objects.exists()
    assert SentenceAudio.objects.exists()


def test_an_empty_catalog_is_not_an_error() -> None:
    call_command("warm_catalog_cache")


def test_a_warmed_text_costs_no_limit(client: Client, catalog_text: SavedText) -> None:
    """The reason warming is worth doing at all.

    The hourly limit counts work sent to a provider, and a warmed text sends
    none — so a guest can open every shared text without spending anything.
    """
    call_command("warm_catalog_cache")

    for _ in range(10):
        response = client.post(reverse("reader:read"), {"text": CONTENT, "lang": "ru"})
        assert response.status_code == 200
