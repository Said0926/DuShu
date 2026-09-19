"""Turning a provider's word boundaries into karaoke marks.

Two different alignment problems live here, and both are solved the same way —
by searching for the next piece from a moving cursor.

The first is that a speech service reports what it spoke as *text*, not as
positions. The second is that the service segments chinese its own way, and that
way does not match jieba: 银行 may arrive as one boundary or as two, and our
words come from jieba. So a boundary can cover several words and a word can be
built from several boundaries, and both cases have to work.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from apps.chinese.types import Sentence

from .providers.base import CharTiming

logger = logging.getLogger(__name__)

# Тик — сотня наносекунд. В таких единицах Microsoft сообщает границы слов.
TICKS_PER_MILLISECOND = 10_000


@dataclass(frozen=True, slots=True)
class SpokenChunk:
    """One boundary event as the provider reported it.

    Attributes:
        text: The stretch of the source the service says it just spoke.
        offset_ticks: When it started, in ticks from the start of the audio.
        duration_ticks: How long it sounded, in ticks.
    """

    text: str
    offset_ticks: int
    duration_ticks: int


@dataclass(frozen=True, slots=True)
class WordTiming:
    """When one word of a sentence is spoken.

    Attributes:
        start_ms: When the word starts sounding.
        end_ms: When it stops.
    """

    start_ms: int
    end_ms: int


def _find_from(haystack: str, needle: str, cursor: int) -> int:
    """Find ``needle`` at or after ``cursor``.

    Searching from a cursor rather than from the start is what makes a repeated
    word work: in 很好很好 both halves must land on their own position instead of
    both matching the first one.
    """
    return haystack.find(needle, cursor)


def align(sentence: str, chunks: Sequence[SpokenChunk]) -> tuple[CharTiming, ...]:
    """Place boundary events onto character positions in the sentence.

    Args:
        sentence: The sentence exactly as it was sent to the provider.
        chunks: Boundary events in the order they arrived.

    Returns:
        One timing per event that could be located, in reading order. Events
        that cannot be found are dropped: a service may normalise what it speaks
        (a digit read as a word, for instance), and losing the highlight on one
        word is much better than shifting every following word onto the wrong
        position.
    """
    timings: list[CharTiming] = []
    cursor = 0

    for chunk in chunks:
        if not chunk.text:
            continue

        position = _find_from(sentence, chunk.text, cursor)

        if position == -1:
            logger.warning(
                "Boundary %r not found in sentence %r after position %s",
                chunk.text,
                sentence,
                cursor,
            )
            continue

        end = position + len(chunk.text)
        cursor = end

        timings.append(
            CharTiming(
                start=position,
                end=end,
                start_ms=chunk.offset_ticks // TICKS_PER_MILLISECOND,
                end_ms=(chunk.offset_ticks + chunk.duration_ticks) // TICKS_PER_MILLISECOND,
            )
        )

    return tuple(timings)


def map_to_words(
    sentence: Sentence,
    timings: Sequence[CharTiming],
) -> tuple[WordTiming | None, ...]:
    """Spread character timings over the words of a sentence.

    A word takes the earliest start and the latest end among the timings it
    overlaps. That single rule covers both kinds of disagreement with jieba: one
    boundary spanning two words gives both the same interval, and a word built
    from two boundaries gets the union of them.

    Args:
        sentence: The processed sentence, with words in reading order.
        timings: Character timings from :func:`align`.

    Returns:
        One entry per word in ``sentence.words``, aligned by position. ``None``
        means the word is never highlighted — punctuation, for example, gets no
        boundary event of its own.
    """
    result: list[WordTiming | None] = []
    cursor = 0

    for word in sentence.words:
        # Позиции слов ищем, а не считаем накоплением длин: сегментатор
        # выбрасывает пробелы, поэтому склейка слов короче самого предложения,
        # и после первого же пробела смещения разошлись бы с таймингами.
        position = _find_from(sentence.text, word.text, cursor)

        if position == -1:
            logger.warning("Word %r not found in sentence %r", word.text, sentence.text)
            result.append(None)
            continue

        start = position
        end = position + len(word.text)
        cursor = end

        # Перебор по всем таймингам: и слов, и событий в предложении десятки,
        # так что квадратичность здесь дешевле, чем поиск по интервальному дереву,
        # и читается несравнимо лучше.
        overlapping = [timing for timing in timings if timing.start < end and timing.end > start]

        if not overlapping:
            result.append(None)
            continue

        result.append(
            WordTiming(
                start_ms=min(timing.start_ms for timing in overlapping),
                end_ms=max(timing.end_ms for timing in overlapping),
            )
        )

    return tuple(result)
