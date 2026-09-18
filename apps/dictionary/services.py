"""Importing dictionary dumps and looking words up."""

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from django.conf import settings

from apps.dictionary.exceptions import UnknownLanguageError
from apps.dictionary.models import DictionaryEntry
from apps.dictionary.parsers import ParsedEntry

logger = logging.getLogger(__name__)

# Сколько записей отправлять в базу за один запрос. Дампы содержат сотни тысяч
# записей — вставлять их по одной слишком медленно, а все разом не поместится
# в память и в лимит параметров запроса.
IMPORT_BATCH_SIZE = 1000


@dataclass(frozen=True, slots=True)
class CharacterLookup:
    """Entries found for a single character when the whole word was not found."""

    character: str
    entries: tuple[DictionaryEntry, ...]


@dataclass(frozen=True, slots=True)
class LookupResult:
    """What the tooltip needs to show for one word.

    Either the word itself was found, or it was not and the characters are
    offered instead. Both lists can be empty for a word that is missing entirely.
    """

    word: str
    entries: tuple[DictionaryEntry, ...]
    characters: tuple[CharacterLookup, ...]

    @property
    def found(self) -> bool:
        """True if the word itself is in the dictionary."""
        return bool(self.entries)


def validate_language(language: str) -> None:
    """Check the language is one the project knows about.

    Raises:
        UnknownLanguageError: If the code is not in settings.TRANSLATION_LANGUAGES.
    """
    if language not in settings.TRANSLATION_LANGUAGES:
        known = ", ".join(sorted(settings.TRANSLATION_LANGUAGES))
        raise UnknownLanguageError(f"Unknown language {language!r}. Known languages: {known}.")


def _batched(entries: Iterable[ParsedEntry], size: int) -> Iterator[list[ParsedEntry]]:
    """Group entries into lists of at most ``size`` items."""
    batch: list[ParsedEntry] = []

    for entry in entries:
        batch.append(entry)
        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def import_entries(
    entries: Iterable[ParsedEntry],
    *,
    language: str,
    source: str,
    batch_size: int = IMPORT_BATCH_SIZE,
) -> int:
    """Write parsed entries into the database.

    Safe to run twice: the unique constraint plus ``ignore_conflicts`` means a
    repeated import adds nothing instead of duplicating the dictionary.

    Args:
        entries: Parsed entries, usually a generator over a dump.
        language: Language code, must be known to the project.
        source: Which dictionary the entries come from.
        batch_size: How many rows to insert per query.

    Returns:
        How many entries were processed. Note this counts entries handed to the
        database, not rows actually created — conflicts are skipped silently,
        and PostgreSQL does not report how many.

    Raises:
        UnknownLanguageError: If the language code is unknown.
    """
    validate_language(language)

    processed = 0

    for batch in _batched(entries, batch_size):
        DictionaryEntry.objects.bulk_create(
            [
                DictionaryEntry(
                    simplified=entry.simplified,
                    traditional=entry.traditional,
                    pinyin=entry.pinyin,
                    language=language,
                    source=source,
                    definitions=entry.definitions,
                )
                for entry in batch
            ],
            ignore_conflicts=True,
        )
        processed += len(batch)

    logger.info("Imported %s entries from %s (%s)", processed, source, language)
    return processed


def lookup(word: str, language: str) -> tuple[DictionaryEntry, ...]:
    """Find every entry for a word.

    A word can have several entries: 行 is both xíng and háng, and they mean
    different things, so the tooltip shows both rather than guessing.

    Args:
        word: The word as it appears in the text.
        language: Language code.

    Returns:
        Entries, empty if the word is not in the dictionary.

    Raises:
        UnknownLanguageError: If the language code is unknown.
    """
    validate_language(language)

    return tuple(DictionaryEntry.objects.filter(simplified=word, language=language))


def lookup_with_fallback(word: str, language: str) -> LookupResult:
    """Find a word, falling back to its individual characters.

    Compounds and names are often missing from a dictionary while their
    characters are not, so showing the parts beats showing nothing.

    Args:
        word: The word as it appears in the text.
        language: Language code.

    Returns:
        The result. ``characters`` is empty when the word itself was found —
        there is no reason to break up a word that already has a translation.

    Raises:
        UnknownLanguageError: If the language code is unknown.
    """
    entries = lookup(word, language)
    if entries:
        return LookupResult(word=word, entries=entries, characters=())

    # Один запрос на все иероглифы вместо запроса на каждый: слово из четырёх
    # знаков иначе стоило бы четырёх обращений к базе на одно наведение мыши.
    unique_characters = list(dict.fromkeys(word))
    found = DictionaryEntry.objects.filter(simplified__in=unique_characters, language=language)

    by_character: dict[str, list[DictionaryEntry]] = {char: [] for char in unique_characters}
    for entry in found:
        by_character[entry.simplified].append(entry)

    # Порядок иероглифов сохраняем как в слове, пропуская ненайденные.
    characters = tuple(
        CharacterLookup(character=char, entries=tuple(by_character[char]))
        for char in word
        if by_character.get(char)
    )

    return LookupResult(word=word, entries=(), characters=characters)
