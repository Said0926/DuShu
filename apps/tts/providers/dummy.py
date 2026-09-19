"""A provider that speaks nothing."""

import io
import wave

from apps.chinese.services import classify
from apps.chinese.types import WordKind

from .base import CharTiming, Synthesis, TTSProvider

# Частота и разрядность взяты как у edge-tts (24 кГц, 16 бит моно) — чтобы
# заглушка отличалась от настоящего провайдера только содержимым, а не форматом.
SAMPLE_RATE = 24_000
BYTES_PER_SAMPLE = 2

# Сколько «звучит» один иероглиф. Близко к настоящей речи: в живой проверке
# 我打算去公园走走 уложилось в 2,2 секунды на восемь иероглифов.
MS_PER_CHARACTER = 250

# Хвостовая тишина, как у настоящего синтеза: файл заканчивается позже речи.
TAIL_MS = 400


def _silence(duration_ms: int) -> bytes:
    """Build a valid WAV file of the given length.

    WAV rather than MP3 because the standard library can write it in five lines,
    while an MP3 would mean either a new dependency or hand-assembled frames.
    The browser plays both, and the file name carries the format.
    """
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(BYTES_PER_SAMPLE)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(BYTES_PER_SAMPLE * SAMPLE_RATE * duration_ms // 1000))

    return buffer.getvalue()


class DummyTTSProvider(TTSProvider):
    """Returns silence with evenly spread timings.

    Used in tests and for work on the page without a network. It exercises the
    cache, the player and the karaoke markup at full size while reaching no
    service at all — so a failing test points at our code rather than at
    someone's endpoint.

    Timings are given to hanzi only, exactly as a real service gives no boundary
    to punctuation.
    """

    def synthesize(self, sentences: list[str], voice: str) -> list[Synthesis]:
        return [self._speak(sentence) for sentence in sentences]

    def _speak(self, sentence: str) -> Synthesis:
        timings: list[CharTiming] = []
        elapsed = 0

        for position, character in enumerate(sentence):
            if classify(character) is not WordKind.CHINESE:
                continue

            timings.append(
                CharTiming(
                    start=position,
                    end=position + 1,
                    start_ms=elapsed,
                    end_ms=elapsed + MS_PER_CHARACTER,
                )
            )
            elapsed += MS_PER_CHARACTER

        duration_ms = elapsed + TAIL_MS

        return Synthesis(
            audio=_silence(duration_ms),
            extension="wav",
            duration_ms=duration_ms,
            timings=tuple(timings),
        )
