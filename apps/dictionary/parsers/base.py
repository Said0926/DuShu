"""Shared pieces for dictionary parsers."""

import gzip
import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from pypinyin.contrib.tone_convert import to_tone


@contextmanager
def open_dump(path: Path, encoding: str = "utf-8") -> Iterator[TextIO]:
    """Open a dump, transparently decompressing ``.gz`` files.

    Dumps are published compressed and are hundreds of megabytes unpacked, so
    reading them through gzip avoids writing that to disk just to read it once.

    Args:
        path: Path to the dump, compressed or not.
        encoding: File encoding. БКРС dumps need ``utf-8-sig`` to drop the BOM.

    Yields:
        An open text file.
    """
    if path.suffix == ".gz":
        handle: TextIO = gzip.open(path, mode="rt", encoding=encoding)
    else:
        handle = path.open(encoding=encoding)

    try:
        yield handle
    finally:
        handle.close()


@dataclass(frozen=True, slots=True)
class ParsedEntry:
    """One entry as read from a dump, before it reaches the database.

    Parsers return these instead of model instances so they stay testable
    without a database and independent of the model.
    """

    simplified: str
    traditional: str
    pinyin: str
    definitions: list[str] = field(default_factory=list)


# Отсылки вида "old variant of 俊[jun4]" — не перевод, а указание на другое
# написание. Они полезны, но показывать их вместо значения нельзя.
_CROSS_REFERENCE = re.compile(r"^(old |Japanese )?variant of ", re.IGNORECASE)


def _merge_definitions(first: list[str], second: list[str]) -> list[str]:
    """Combine two definition lists, keeping the useful ones first.

    ``dict.fromkeys`` removes duplicates while preserving order, which matters
    because the first definition is what the tooltip shows when space is tight.
    """
    combined = list(dict.fromkeys(first + second))

    substantive = [text for text in combined if not _CROSS_REFERENCE.match(text)]
    references = [text for text in combined if _CROSS_REFERENCE.match(text)]

    return substantive + references


def merge_duplicates(entries: Iterable[ParsedEntry]) -> Iterator[ParsedEntry]:
    """Merge entries that share a word and a reading.

    CC-CEDICT lists every traditional spelling separately, so 俊 appears three
    times as jùn: once with its real meanings and twice as "old variant of".
    Inserting them as separate rows is not an option — the unique constraint
    keeps whichever arrives first, and in the dump the variants come first, so
    the real meanings would be dropped.

    Merging instead of picking a winner means nothing is lost: the variants end
    up at the end of the definition list where they belong.

    Note this holds every entry in memory until the input is exhausted. For a
    dump of a few hundred thousand entries that is tens of megabytes, which is
    an acceptable price for not losing translations.

    Args:
        entries: Parsed entries, in dump order.

    Yields:
        One entry per word and reading, in order of first appearance.
    """
    merged: dict[tuple[str, str], ParsedEntry] = {}

    for entry in entries:
        key = (entry.simplified, entry.pinyin)
        existing = merged.get(key)

        if existing is None:
            merged[key] = entry
            continue

        # Традиционное написание, совпадающее с упрощённым, — основное;
        # остальные это варианты, и предпочитать их незачем.
        traditional = existing.traditional
        if traditional != existing.simplified and entry.traditional == entry.simplified:
            traditional = entry.traditional

        merged[key] = ParsedEntry(
            simplified=existing.simplified,
            traditional=traditional,
            pinyin=existing.pinyin,
            definitions=_merge_definitions(existing.definitions, entry.definitions),
        )

    yield from merged.values()


def _is_convertible(syllable: str) -> bool:
    """Return True if the syllable looks like pinyin that can be converted.

    Needed because ``to_tone`` does not reject nonsense, it mangles it: given
    ``"11"`` it treats the trailing digit as a tone mark and returns ``"1"``,
    losing a character with no error. Dumps contain such entries — 11区 is a real
    CC-CEDICT headword.
    """
    body = syllable[:-1] if syllable[-1:].isdigit() else syllable
    return bool(body) and body.isalpha()


def numbered_pinyin_to_diacritics(numbered: str) -> str:
    """Convert ``"yin2 hang2"`` into ``"yín háng"``.

    Dictionary dumps store tones as digits because that is easy to type, but the
    tooltip shows diacritics, which is what learners read.

    Two details make this less trivial than it looks:

    - ``to_tone`` handles one syllable at a time. Given a whole phrase it
      converts the first syllable and silently drops the remaining tones, so the
      string is split first.
    - CC-CEDICT writes ü as ``u:`` because the format is plain ASCII. Left as is,
      女 ``nu:3`` would come out as ``nǔ:`` instead of ``nǚ`` — a wrong reading
      for a very common word.

    Args:
        numbered: Pinyin with tone digits, syllables separated by spaces.

    Returns:
        Pinyin with diacritics. Anything that is not pinyin is kept unchanged
        rather than mangled or dropped.
    """
    converted: list[str] = []

    for syllable in numbered.split():
        # u: и U: — запись ü в ASCII-совместимом формате CC-CEDICT.
        normalised = syllable.replace("u:", "ü").replace("U:", "Ü")

        if not _is_convertible(normalised):
            converted.append(syllable)
            continue

        try:
            converted.append(to_tone(normalised))
        except (ValueError, KeyError):
            # Проверка выше отсеивает основные случаи, но словарь большой и
            # может содержать неожиданное. Запись целиком терять не будем.
            converted.append(syllable)

    return " ".join(converted)
