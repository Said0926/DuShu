"""Tests for dictionary import and lookup."""

import pytest
from django.test import override_settings

from apps.dictionary.exceptions import UnknownLanguageError
from apps.dictionary.models import DictionaryEntry
from apps.dictionary.parsers import ParsedEntry
from apps.dictionary.services import import_entries, lookup, lookup_with_fallback

pytestmark = pytest.mark.django_db


@pytest.fixture
def entries() -> list[ParsedEntry]:
    return [
        ParsedEntry("银行", "銀行", "yín háng", ["bank"]),
        ParsedEntry("你好", "你好", "nǐ hǎo", ["hello", "hi"]),
        ParsedEntry("猫", "貓", "māo", ["cat"]),
        ParsedEntry("狗", "狗", "gǒu", ["dog"]),
    ]


class TestImport:
    def test_creates_entries(self, entries: list[ParsedEntry]) -> None:
        created = import_entries(entries, language="en", source="test")

        assert created == 4
        assert DictionaryEntry.objects.count() == 4

    def test_running_twice_does_not_duplicate(self, entries: list[ParsedEntry]) -> None:
        """Re-running an import must be safe: dumps get refreshed regularly."""
        import_entries(entries, language="en", source="test")
        import_entries(entries, language="en", source="test")

        assert DictionaryEntry.objects.count() == 4

    def test_same_word_in_two_languages_coexists(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="cc-cedict")
        import_entries(entries, language="ru", source="bkrs")

        assert DictionaryEntry.objects.filter(simplified="猫").count() == 2

    def test_batching_does_not_lose_entries(self, entries: list[ParsedEntry]) -> None:
        """Real dumps are written in batches of a thousand; boundaries must be clean."""
        created = import_entries(entries, language="en", source="test", batch_size=1)

        assert created == 4
        assert DictionaryEntry.objects.count() == 4

    def test_unknown_language_is_rejected(self, entries: list[ParsedEntry]) -> None:
        with pytest.raises(UnknownLanguageError):
            import_entries(entries, language="de", source="test")

    @override_settings(TRANSLATION_LANGUAGES={"ru": "Русский", "en": "English", "de": "Deutsch"})
    def test_a_new_language_needs_no_migration(self, entries: list[ParsedEntry]) -> None:
        """The whole point of keeping `language` a plain CharField without choices."""
        import_entries(entries, language="de", source="test")

        assert DictionaryEntry.objects.filter(language="de").count() == 4


class TestLookup:
    def test_finds_a_word(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="test")

        found = lookup("银行", "en")

        assert len(found) == 1
        assert found[0].definitions == ["bank"]

    def test_returns_every_reading(self) -> None:
        """行 is both xíng and háng with different meanings; the tooltip shows both."""
        import_entries(
            [
                ParsedEntry("行", "行", "xíng", ["to walk"]),
                ParsedEntry("行", "行", "háng", ["row"]),
            ],
            language="en",
            source="test",
        )

        assert {entry.pinyin for entry in lookup("行", "en")} == {"xíng", "háng"}

    def test_missing_word_gives_nothing(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="test")

        assert lookup("龘", "en") == ()

    def test_language_is_respected(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="test")

        assert lookup("猫", "ru") == ()

    def test_unknown_language_is_rejected(self) -> None:
        with pytest.raises(UnknownLanguageError):
            lookup("猫", "de")


class TestLookupWithFallback:
    def test_known_word_is_returned_directly(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="test")

        result = lookup_with_fallback("银行", "en")

        assert result.found
        assert result.entries[0].definitions == ["bank"]
        assert result.characters == ()

    def test_unknown_word_falls_back_to_characters(self, entries: list[ParsedEntry]) -> None:
        """Compounds and names are often missing while their characters are not."""
        import_entries(entries, language="en", source="test")

        result = lookup_with_fallback("猫狗", "en")

        assert not result.found
        assert [c.character for c in result.characters] == ["猫", "狗"]
        assert result.characters[0].entries[0].definitions == ["cat"]

    def test_character_order_follows_the_word(self, entries: list[ParsedEntry]) -> None:
        import_entries(entries, language="en", source="test")

        result = lookup_with_fallback("狗猫", "en")

        assert [c.character for c in result.characters] == ["狗", "猫"]

    def test_characters_missing_from_the_dictionary_are_skipped(
        self, entries: list[ParsedEntry]
    ) -> None:
        import_entries(entries, language="en", source="test")

        result = lookup_with_fallback("猫龘", "en")

        assert [c.character for c in result.characters] == ["猫"]

    def test_repeated_character_is_queried_once_and_shown_twice(
        self, entries: list[ParsedEntry]
    ) -> None:
        import_entries(entries, language="en", source="test")

        result = lookup_with_fallback("猫猫", "en")

        assert [c.character for c in result.characters] == ["猫", "猫"]

    def test_word_with_nothing_known_gives_an_empty_result(self) -> None:
        result = lookup_with_fallback("龘龖", "en")

        assert not result.found
        assert result.characters == ()

    def test_fallback_uses_a_single_query(
        self, entries: list[ParsedEntry], django_assert_num_queries: pytest.FixtureRequest
    ) -> None:
        """One query for the word, one for all its characters — not one per character."""
        import_entries(entries, language="en", source="test")

        with django_assert_num_queries(2):
            lookup_with_fallback("猫狗猫狗", "en")
