"""Tests for the caching translation service."""

from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from apps.translation.exceptions import TranslationError
from apps.translation.models import SentenceTranslation, sentence_hash
from apps.translation.services import (
    get_provider,
    has_cached_translations,
    translate_sentences,
)

pytestmark = pytest.mark.django_db

DUMMY = "apps.translation.providers.dummy.DummyProvider"


def _counting_provider(translations: list[str] | None = None) -> Mock:
    """A provider that records how it was called."""
    provider = Mock()
    provider.translate.side_effect = (
        (lambda sentences, lang: list(sentences)) if translations is None else None
    )
    if translations is not None:
        provider.translate.return_value = translations
    return provider


class TestTranslateSentences:
    @pytest.fixture(autouse=True)
    def _dummy_provider(self, settings: pytest.FixtureRequest) -> None:
        settings.TRANSLATION_PROVIDER = DUMMY

    def test_returns_one_translation_per_sentence(self) -> None:
        result = translate_sentences(["你好。", "再见。"], "ru")

        assert len(result) == 2

    def test_empty_input_needs_no_provider(self) -> None:
        with patch("apps.translation.services.get_provider") as provider:
            assert translate_sentences([], "ru") == []

        provider.assert_not_called()

    def test_results_are_cached(self) -> None:
        translate_sentences(["你好。"], "ru")

        assert SentenceTranslation.objects.filter(target_language="ru").count() == 1

    def test_second_call_does_not_reach_the_provider(self) -> None:
        """The whole point of the cache: reopening a text must be free."""
        translate_sentences(["你好。", "再见。"], "ru")

        with patch("apps.translation.services.get_provider") as provider:
            translate_sentences(["你好。", "再见。"], "ru")

        provider.assert_not_called()

    def test_only_missing_sentences_are_sent(self) -> None:
        translate_sentences(["你好。"], "ru")
        fake = _counting_provider()

        with patch("apps.translation.services.get_provider", return_value=fake):
            translate_sentences(["你好。", "再见。"], "ru")

        assert fake.translate.call_args.args[0] == ["再见。"]

    def test_duplicate_sentences_are_paid_for_once(self) -> None:
        """A repeated line in a text is common and should not be billed twice."""
        fake = _counting_provider()

        with patch("apps.translation.services.get_provider", return_value=fake):
            result = translate_sentences(["你好。", "你好。", "再见。"], "ru")

        assert fake.translate.call_args.args[0] == ["你好。", "再见。"]
        assert len(result) == 3

    def test_order_is_preserved(self) -> None:
        fake = _counting_provider(translations=["первое", "второе"])

        with patch("apps.translation.services.get_provider", return_value=fake):
            result = translate_sentences(["一。", "二。"], "ru")

        assert result == ["первое", "второе"]

    def test_duplicates_get_the_same_translation(self) -> None:
        fake = _counting_provider(translations=["привет", "пока"])

        with patch("apps.translation.services.get_provider", return_value=fake):
            result = translate_sentences(["你好。", "再见。", "你好。"], "ru")

        assert result == ["привет", "пока", "привет"]

    @override_settings(TRANSLATION_BATCH_SIZE=2, TRANSLATION_PROVIDER=DUMMY)
    def test_long_texts_go_out_in_batches(self) -> None:
        """DeepL takes at most 50 texts per request, so batching is not optional."""
        fake = _counting_provider()
        sentences = [f"第{index}句。" for index in range(5)]

        with patch("apps.translation.services.get_provider", return_value=fake):
            translate_sentences(sentences, "ru")

        assert fake.translate.call_count == 3

    def test_languages_are_cached_separately(self) -> None:
        translate_sentences(["你好。"], "ru")
        translate_sentences(["你好。"], "en")

        assert SentenceTranslation.objects.count() == 2

    def test_whitespace_does_not_create_a_second_cache_entry(self) -> None:
        """The same sentence pasted with stray spaces is the same sentence."""
        translate_sentences(["你好。"], "ru")
        translate_sentences(["  你好。  "], "ru")

        assert SentenceTranslation.objects.count() == 1

    def test_provider_failure_caches_nothing(self) -> None:
        """A half-written cache would serve broken translations forever."""
        failing = Mock()
        failing.translate.side_effect = TranslationError("service down")

        with patch("apps.translation.services.get_provider", return_value=failing):
            with pytest.raises(TranslationError):
                translate_sentences(["你好。"], "ru")

        assert SentenceTranslation.objects.count() == 0

    def test_provider_name_is_recorded(self) -> None:
        """Lets one provider's cache be dropped without touching the rest."""
        translate_sentences(["你好。"], "ru")

        assert SentenceTranslation.objects.first().provider == "DummyProvider"


class TestGetProvider:
    @override_settings(TRANSLATION_PROVIDER=DUMMY)
    def test_builds_the_configured_provider(self) -> None:
        from apps.translation.providers.dummy import DummyProvider

        assert isinstance(get_provider(), DummyProvider)

    @override_settings(TRANSLATION_PROVIDER="apps.translation.providers.nope.Missing")
    def test_bad_path_reports_a_readable_error(self) -> None:
        with pytest.raises(TranslationError, match="TRANSLATION_PROVIDER"):
            get_provider()


def test_sentence_hash_ignores_surrounding_whitespace() -> None:
    assert sentence_hash("你好。") == sentence_hash("  你好。\n")


def test_sentence_hash_differs_for_different_text() -> None:
    assert sentence_hash("你好。") != sentence_hash("再见。")


class TestProviderContractViolations:
    """A provider that breaks its contract must not produce a 500."""

    def test_provider_returning_too_few_translations(self) -> None:
        sloppy = Mock()
        sloppy.translate.return_value = ["только один"]

        with patch("apps.translation.services.get_provider", return_value=sloppy):
            with pytest.raises(TranslationError, match="1 translations"):
                translate_sentences(["一。", "二。"], "ru")

    def test_provider_returning_too_many_translations(self) -> None:
        sloppy = Mock()
        sloppy.translate.return_value = ["один", "два", "три"]

        with patch("apps.translation.services.get_provider", return_value=sloppy):
            with pytest.raises(TranslationError):
                translate_sentences(["一。", "二。"], "ru")

    @override_settings(TRANSLATION_PROVIDER="apps.translation.models.sentence_hash")
    def test_setting_pointing_at_something_that_is_not_a_provider(self) -> None:
        """The path imports fine but calling it does not give a provider."""
        with pytest.raises(TranslationError, match="not a usable provider"):
            get_provider()


def test_tests_never_use_the_real_provider() -> None:
    """Guard against a test quietly making billed DeepL calls."""
    from django.conf import settings as django_settings

    assert "dummy" in django_settings.TRANSLATION_PROVIDER.lower()


@pytest.mark.django_db
def test_nothing_cached_means_it_is_not_free() -> None:
    assert has_cached_translations(["你好。"], "ru") is False


@pytest.mark.django_db
def test_a_fully_translated_text_is_free_to_reopen() -> None:
    """This is what lets the reader skip the hourly limit on a re-read."""
    translate_sentences(["你好。", "再见。"], "ru")

    assert has_cached_translations(["你好。", "再见。"], "ru") is True


@pytest.mark.django_db
def test_one_missing_sentence_makes_the_whole_text_paid() -> None:
    """Partial cache still means a request to the provider, so it must count."""
    translate_sentences(["你好。"], "ru")

    assert has_cached_translations(["你好。", "再见。"], "ru") is False


@pytest.mark.django_db
def test_another_language_is_not_covered_by_the_cache() -> None:
    """Reopening a saved text in a new language is genuinely new paid work."""
    translate_sentences(["你好。"], "ru")

    assert has_cached_translations(["你好。"], "en") is False


@pytest.mark.django_db
def test_an_empty_text_is_free() -> None:
    assert has_cached_translations([], "ru") is True
