"""Parser for CC-CEDICT dumps.

CC-CEDICT is a plain text file, one entry per line:

    銀行 银行 [yin2 hang2] /bank/CL:家[jia1],個|个[ge4]/

Lines starting with ``#`` are comments. Licensed CC BY-SA 3.0, which is why the
footer and the README credit it.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from .base import ParsedEntry, numbered_pinyin_to_diacritics, open_dump

# traditional simplified [pinyin] /definition/definition/
_ENTRY_PATTERN = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]*)\]\s+/(.*)/\s*$")


def parse_line(line: str) -> ParsedEntry | None:
    """Parse one line of a CC-CEDICT dump.

    Args:
        line: A single line, with or without a trailing newline.

    Returns:
        The entry, or None for comments, blank lines and anything malformed.
        A dump of hundreds of thousands of lines is expected to contain a few
        broken ones, and one bad line must not abort the whole import.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    match = _ENTRY_PATTERN.match(stripped)
    if match is None:
        return None

    traditional, simplified, pinyin, definitions_part = match.groups()

    # Значения разделены слэшами: /bank/CL:家[jia1]/ — пустые куски отбрасываем.
    definitions = [piece.strip() for piece in definitions_part.split("/") if piece.strip()]
    if not definitions:
        return None

    return ParsedEntry(
        simplified=simplified,
        traditional=traditional,
        pinyin=numbered_pinyin_to_diacritics(pinyin),
        definitions=definitions,
    )


def parse_file(path: Path) -> Iterator[ParsedEntry]:
    """Read a CC-CEDICT dump entry by entry.

    A generator rather than a list: the dump holds hundreds of thousands of
    entries, and the import writes them in batches, so there is no reason to
    hold them all in memory at once.

    Args:
        path: Path to the dump, compressed or not.

    Yields:
        Entries in file order.
    """
    with open_dump(path) as dump:
        for line in dump:
            entry = parse_line(line)
            if entry is not None:
                yield entry
