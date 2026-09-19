"""Text processing services.

Re-exported here so other apps can write ``from apps.chinese.services import
process_text`` without knowing which module it lives in. That keeps the internal
layout free to change.
"""

from .hashing import sentence_hash
from .pinyin import build_word, classify
from .processor import process_text
from .segmenter import segment, warm_up
from .splitter import split_into_sentences

__all__ = [
    "build_word",
    "classify",
    "process_text",
    "segment",
    "sentence_hash",
    "split_into_sentences",
    "warm_up",
]
