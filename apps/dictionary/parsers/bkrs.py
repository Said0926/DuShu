"""Parser for БКРС daily dumps.

The daily build is plain text, three lines per entry separated by a blank line:

    银行
     yínháng
     [m1]банк[/m][m2]2) казначейство[/m]

Definitions carry DSL markup: ``[m1]`` numbers a sense, ``[i]`` italicises a
comment, ``[p]`` marks a label, ``[*][ex]`` wraps usage examples.

Licence: the owners state that the databases may be used freely for any purpose
and ask only that the site is credited, which the footer and README do.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from .base import ParsedEntry, open_dump

# Блок примеров: [*][ex]...[/ex][/*]. В подсказке нужен краткий перевод,
# а примеры занимают несколько строк и делают её нечитаемой.
_EXAMPLE_BLOCK = re.compile(r"\[\*\].*?\[/\*\]", re.DOTALL)

# Начало значения: [m1], [m2], [m] — уровень вложенности нам не важен,
# каждый такой блок это отдельное значение.
_SENSE_START = re.compile(r"\[m\d*\]")

# Любой оставшийся тег DSL.
_ANY_TAG = re.compile(r"\[/?[^\]]*\]")


def _clean_definitions(raw: str) -> list[str]:
    """Strip DSL markup and split the line into separate senses.

    Args:
        raw: The definition line as it appears in the dump.

    Returns:
        Senses in order, without markup. Empty pieces are dropped.
    """
    without_examples = _EXAMPLE_BLOCK.sub("", raw)

    senses: list[str] = []
    for piece in _SENSE_START.split(without_examples):
        cleaned = _ANY_TAG.sub("", piece).strip()
        if cleaned:
            senses.append(cleaned)

    return senses


def parse_block(block: str) -> ParsedEntry | None:
    """Parse one entry.

    Args:
        block: The lines of a single entry, without the separating blank line.

    Returns:
        The entry, or None for file headers and anything malformed.
    """
    lines = [line.strip() for line in block.splitlines() if line.strip()]

    # Служебные строки в начале файла: #NAME, #INDEX_LANGUAGE, ...
    if not lines or lines[0].startswith("#"):
        return None

    # Минимум — слово и хотя бы одна строка под ним.
    if len(lines) < 2:
        return None

    word = lines[0]
    pinyin = lines[1]
    definition_lines = lines[2:]

    # Записей без пиньиня в дампе нет, но если такая встретится, вторая строка
    # окажется определением — лучше сохранить её как значение, чем как чтение.
    if not definition_lines:
        definition_lines = [pinyin]
        pinyin = ""

    definitions: list[str] = []
    for line in definition_lines:
        definitions.extend(_clean_definitions(line))

    if not definitions:
        return None

    return ParsedEntry(
        simplified=word,
        traditional="",
        pinyin=pinyin,
        definitions=definitions,
    )


def parse_file(path: Path) -> Iterator[ParsedEntry]:
    """Read a БКРС dump entry by entry.

    Args:
        path: Path to the dump, compressed or not.

    Yields:
        Entries in file order.
    """
    # utf-8-sig убирает BOM, с которого начинается файл.
    with open_dump(path, encoding="utf-8-sig") as dump:
        block: list[str] = []

        for line in dump:
            if line.strip():
                block.append(line)
                continue

            # Пустая строка — конец записи.
            entry = parse_block("".join(block))
            block.clear()
            if entry is not None:
                yield entry

        # Последняя запись может не заканчиваться пустой строкой.
        if block:
            entry = parse_block("".join(block))
            if entry is not None:
                yield entry
