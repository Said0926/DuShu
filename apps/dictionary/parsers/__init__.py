"""Parsers turning dictionary dumps into ParsedEntry objects.

Kept free of Django imports so they can be tested without a database.
"""

from .base import ParsedEntry, merge_duplicates, numbered_pinyin_to_diacritics, open_dump

__all__ = [
    "ParsedEntry",
    "merge_duplicates",
    "numbered_pinyin_to_diacritics",
    "open_dump",
]
