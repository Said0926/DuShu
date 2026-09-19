"""Building what the shadowing page renders.

The page needs every sentence paired with its audio and with per-word karaoke
marks. Assembling that here keeps the view thin and the template free of logic:
a Django template cannot zip two sequences, and it should not have to.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from apps.chinese.types import ProcessedText, Sentence, Word
from apps.tts.alignment import WordTiming
from apps.tts.models import SentenceAudio
from apps.tts.services import get_sentence_audio, word_timings


@dataclass(frozen=True, slots=True)
class SpokenWord:
    """One word together with the moment it is spoken.

    Attributes:
        word: The word itself, for the ruby markup.
        timing: When to highlight it, or ``None`` if it is never highlighted.
    """

    word: Word
    timing: WordTiming | None


@dataclass(frozen=True, slots=True)
class SpokenSentence:
    """One sentence ready to be rendered and played.

    Attributes:
        number: Position in the text, starting at one — this is what the sentence
            list and the "Предложение N из M" line show.
        text: The sentence as written.
        words: Words paired with their timings.
        translation: The sentence in the reader's language, or an empty string
            when the translation service could not be reached.
        audio_url: Where the browser fetches the audio.
        duration_ms: Length of the audio, for the progress track.
        duration_label: The same length as ``0:04``, for the sentence list.
    """

    number: int
    text: str
    words: tuple[SpokenWord, ...]
    translation: str
    audio_url: str
    duration_ms: int
    duration_label: str


def format_duration(duration_ms: int) -> str:
    """Render a length as ``M:SS``.

    Formatted here rather than by a template filter: ``timesince`` and friends
    work on dates, and a filter for this would be a new shared concept for one
    use.
    """
    total_seconds = round(duration_ms / 1000)
    return f"{total_seconds // 60}:{total_seconds % 60:02d}"


def _as_spoken(sentence: Sentence, audio: SentenceAudio, translation: str) -> SpokenSentence:
    """Pair one processed sentence with its cached audio and its translation."""
    timings = word_timings(sentence, audio)

    return SpokenSentence(
        number=sentence.index + 1,
        text=sentence.text,
        words=tuple(
            SpokenWord(word=word, timing=timing)
            for word, timing in zip(sentence.words, timings, strict=True)
        ),
        translation=translation,
        audio_url=audio.audio.url,
        duration_ms=audio.duration_ms,
        duration_label=format_duration(audio.duration_ms),
    )


def speak_text(
    processed: ProcessedText,
    translations: Sequence[str] = (),
) -> list[SpokenSentence]:
    """Speak every sentence of a text and pair it with its karaoke marks.

    Args:
        processed: The processed text.
        translations: One translation per sentence, in the same order. Empty when
            the translation service failed or the page asked for no translations
            — speech and translation are separate services, and one being down
            must not cost the other.

    Returns:
        Sentences in reading order.

    Raises:
        TTSError: If the speech provider fails. Nothing is rendered in that case,
            and the view decides what to show instead.
    """
    if not processed.sentences:
        return []

    audio = get_sentence_audio([sentence.text for sentence in processed.sentences])

    return [
        _as_spoken(
            sentence,
            audio[sentence.text],
            # Индекс, а не zip: переводов может не быть вовсе, и тогда каждое
            # предложение получает пустую строку, а не выпадает из списка.
            translations[index] if index < len(translations) else "",
        )
        for index, sentence in enumerate(processed.sentences)
    ]
