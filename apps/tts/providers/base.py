"""The provider interface every speech backend implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharTiming:
    """When one stretch of a sentence is spoken.

    Positions are character indices rather than word indices on purpose. Words
    exist only because jieba segmented them, so a future jieba dictionary would
    silently shift every cached timing onto the wrong word. Characters never
    shift, which is why the mapping onto words is recomputed at render time.

    Attributes:
        start: Index of the first character, as a slice bound of the sentence.
        end: Index one past the last character.
        start_ms: Offset from the beginning of the audio.
        end_ms: When this stretch stops sounding.
    """

    start: int
    end: int
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class Synthesis:
    """One spoken sentence.

    Attributes:
        audio: The encoded audio, ready to be written to storage.
        extension: File extension without the dot, e.g. ``"mp3"``. Providers may
            return different formats, and the browser picks the decoder by the
            content type the file is served with.
        duration_ms: Length of the audio, trailing silence included. Not the end
            of the last timing: real speech ends before the file does.
        timings: Karaoke marks, in reading order.
    """

    audio: bytes
    extension: str
    duration_ms: int
    timings: tuple[CharTiming, ...]


class TTSProvider(ABC):
    """Turns sentences into audio with word-level timings.

    Everything that talks to a speech service goes through this class, so
    swapping the unofficial Edge endpoint for paid Azure means writing one new
    subclass and changing one setting.

    The method takes a batch rather than one sentence because concurrency is a
    property of the backend, not of the caller: this provider opens several
    websockets at once, another might send one request. That knowledge belongs
    inside the provider instead of leaking into the service.

    Implementations must honour two rules, for the same reason the translation
    providers do — a mismatch would put one sentence's audio under another
    sentence's text:

    - the result has exactly as many items as the input;
    - the order is preserved.
    """

    @abstractmethod
    def synthesize(self, sentences: list[str], voice: str) -> list[Synthesis]:
        """Speak a batch of sentences.

        Args:
            sentences: Sentences to speak, already deduplicated by the caller.
            voice: Provider-specific voice name, e.g. ``"zh-CN-XiaoxiaoNeural"``.

        Returns:
            One synthesis per input sentence, in the same order.

        Raises:
            TTSError: If the service is unreachable or refuses the request.
        """
