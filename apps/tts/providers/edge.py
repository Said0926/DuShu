"""Speech from the engine behind Edge's "Read Aloud"."""

import asyncio
import logging

import aiohttp
from django.conf import settings
from edge_tts import Communicate
from edge_tts.exceptions import EdgeTTSException

from apps.tts.alignment import SpokenChunk, align
from apps.tts.exceptions import TTSError

from .base import Synthesis, TTSProvider

logger = logging.getLogger(__name__)

# edge-tts всегда просит у сервиса audio-24khz-48kbitrate-mono-mp3 — поток с
# постоянным битрейтом. Для CBR длительность считается из размера точно:
# 48 000 бит в секунду это 6 000 байт в секунду, то есть 6 байт на миллисекунду.
# Той же арифметикой edge-tts сам сшивает смещения длинных текстов.
BYTES_PER_MILLISECOND = 6

# Одна повторная попытка. Эндпоинт неофициальный и временами отвечает 503 или
# отдаёт пустой поток; второй заход обычно проходит. Больше двух не делаем —
# это уже не «икнуло», а сервис недоступен, и пользователю нужен ответ, а не
# страница, висящая минуту.
MAX_ATTEMPTS = 2

# Что считаем сбоем сети или сервиса. TimeoutError наследуется от OSError,
# поэтому отдельно его не перечисляем.
TRANSPORT_ERRORS = (EdgeTTSException, aiohttp.ClientError, OSError)


class EdgeTTSProvider(TTSProvider):
    """Speaks chinese with Microsoft Neural voices, free and without a key.

    The library talks to the endpoint Edge itself uses, which has two
    consequences worth knowing. The voices and the timings are the same ones
    Azure sells — it is one engine. And nobody promised us this endpoint, so it
    breaks sometimes; that is survivable only because every result is cached, so
    a failure costs one text's first open rather than the feature.
    """

    def synthesize(self, sentences: list[str], voice: str) -> list[Synthesis]:
        if not sentences:
            return []

        try:
            # asyncio.run внутри синхронного метода — осознанно: наружу торчит
            # обычный синхронный интерфейс провайдера, а асинхронность остаётся
            # деталью реализации этого класса. Django-view про неё не знает.
            return asyncio.run(self._synthesize_all(sentences, voice))
        except TRANSPORT_ERRORS as error:
            raise TTSError(
                f"Speech service failed for {len(sentences)} sentences: {error}"
            ) from error

    async def _synthesize_all(self, sentences: list[str], voice: str) -> list[Synthesis]:
        """Speak every sentence, a few at a time."""
        semaphore = asyncio.Semaphore(settings.TTS_CONCURRENCY)

        # gather сохраняет порядок аргументов независимо от порядка завершения,
        # а это и есть контракт провайдера: i-й результат для i-го предложения.
        return list(
            await asyncio.gather(
                *(self._synthesize_one(sentence, voice, semaphore) for sentence in sentences)
            )
        )

    async def _synthesize_one(
        self,
        sentence: str,
        voice: str,
        semaphore: asyncio.Semaphore,
    ) -> Synthesis:
        """Speak one sentence, retrying once on a transport failure."""
        async with semaphore:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    return await self._speak(sentence, voice)
                except TRANSPORT_ERRORS as error:
                    if attempt == MAX_ATTEMPTS:
                        raise

                    logger.warning(
                        "Speech attempt %s for %r failed (%s), retrying", attempt, sentence, error
                    )

        # Недостижимо: последняя попытка либо возвращает результат, либо бросает.
        raise TTSError(f"Speech produced nothing for {sentence!r}.")

    async def _speak(self, sentence: str, voice: str) -> Synthesis:
        """Run one websocket session and collect audio plus boundaries."""
        # boundary="WordBoundary" — обязательно и явно: по умолчанию в edge-tts
        # стоит "SentenceBoundary", и тогда караоке подсвечивало бы предложения
        # целиком, не сообщая об этом никакой ошибкой.
        communicate = Communicate(sentence, voice, boundary="WordBoundary")

        audio = bytearray()
        chunks: list[SpokenChunk] = []

        async for message in communicate.stream():
            if message["type"] == "audio":
                audio.extend(message["data"])
            elif message["type"] == "WordBoundary":
                chunks.append(
                    SpokenChunk(
                        text=message["text"],
                        offset_ticks=message["offset"],
                        duration_ticks=message["duration"],
                    )
                )

        if not audio:
            raise TTSError(f"Speech service returned no audio for {sentence!r}.")

        return Synthesis(
            audio=bytes(audio),
            extension="mp3",
            duration_ms=len(audio) // BYTES_PER_MILLISECOND,
            timings=align(sentence, chunks),
        )
