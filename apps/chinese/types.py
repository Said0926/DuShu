"""Data structures produced by the text processing pipeline.

Every feature (reader, shadowing, and later the personal dictionary) consumes
these objects, so they are deliberately dumb: plain immutable containers with no
behaviour and no database access.
"""

from dataclasses import dataclass
from enum import StrEnum

# Нейтральный тон. В пиньине он не обозначается диакритикой, но подсветке нужен
# свой класс, поэтому даём ему номер 5.
NEUTRAL_TONE = 5


class WordKind(StrEnum):
    """What a token is, so the template knows how to render it.

    ``StrEnum`` compares equal to plain strings, which means a Django template
    can write ``{% if word.kind == "chinese" %}`` without any extra filters.
    """

    CHINESE = "chinese"
    PUNCT = "punct"
    OTHER = "other"


# frozen=True — объекты нельзя изменить после создания: обработанный текст
# читают несколько мест, и случайная правка в одном из них не должна влиять на другие.
# slots=True — экономит память: в тексте на 5000 символов таких объектов тысячи.
@dataclass(frozen=True, slots=True)
class Syllable:
    """One hanzi together with its reading.

    Attributes:
        char: The character itself.
        pinyin: Reading with a tone diacritic, e.g. ``"hǎo"``.
        tone: Tone number 1-4, or 5 for the neutral tone.
    """

    char: str
    pinyin: str
    tone: int


@dataclass(frozen=True, slots=True)
class Word:
    """A token produced by the segmenter.

    Attributes:
        text: The token as it appears in the source.
        pinyin: Readings joined by spaces, ready for a ``data-pinyin`` attribute.
            Empty for anything that is not chinese.
        syllables: One entry per hanzi. Empty for anything that is not chinese.
        kind: Decides how the template renders this token.
    """

    text: str
    pinyin: str
    syllables: tuple[Syllable, ...]
    kind: WordKind


@dataclass(frozen=True, slots=True)
class Sentence:
    """One sentence with its tokens.

    Attributes:
        index: Position in the text, starting at zero. Used as the cache key for
            translations and as the sentence number in shadowing.
        text: The sentence as it appears in the source, punctuation included.
        words: Tokens in reading order.
    """

    index: int
    text: str
    words: tuple[Word, ...]


@dataclass(frozen=True, slots=True)
class ProcessedText:
    """The result of processing a whole text."""

    sentences: tuple[Sentence, ...]
