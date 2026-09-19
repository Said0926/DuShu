"""Speaking sentences, with audio and timings cached in the database."""

import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils.module_loading import import_string

from apps.chinese.services import sentence_hash
from apps.chinese.types import Sentence
from apps.tts.alignment import WordTiming, map_to_words
from apps.tts.exceptions import TTSError
from apps.tts.models import SentenceAudio
from apps.tts.providers import CharTiming, Synthesis, TTSProvider

logger = logging.getLogger(__name__)


def get_provider() -> TTSProvider:
    """Build the provider named in settings.

    ``import_string`` turns the dotted path from ``TTS_PROVIDER`` into a class,
    so switching from the free Edge endpoint to paid Azure is a settings change.

    Raises:
        TTSError: If the path is wrong or the provider cannot start.
    """
    try:
        provider_class = import_string(settings.TTS_PROVIDER)
    except ImportError as error:
        raise TTSError(f"Cannot import TTS_PROVIDER {settings.TTS_PROVIDER!r}.") from error

    try:
        return provider_class()
    except TTSError:
        raise
    except (TypeError, AttributeError) as error:
        # Путь ведёт не на класс провайдера, или конструктор требует аргументов.
        # Это ошибка настройки, а не сбой озвучки, но наружу она должна выйти
        # тем же типом: страница обязана пережить её.
        raise TTSError(
            f"TTS_PROVIDER {settings.TTS_PROVIDER!r} is not a usable provider."
        ) from error


def current_voice() -> str:
    """The voice every new synthesis uses."""
    return settings.TTS_VOICE


def get_sentence_audio(sentences: list[str], voice: str | None = None) -> dict[str, SentenceAudio]:
    """Return audio for every sentence, speaking only what is missing.

    Args:
        sentences: Sentences in reading order.
        voice: Voice name, or ``None`` for the one in settings.

    Returns:
        A row per distinct sentence, keyed by the sentence text.

    Raises:
        TTSError: If the provider fails. Whatever was already cached stays.
    """
    if not sentences:
        return {}

    voice = voice or current_voice()

    # Одинаковые предложения в одном тексте озвучиваем один раз.
    unique_sentences = list(dict.fromkeys(sentences))
    hashes = {sentence: sentence_hash(sentence) for sentence in unique_sentences}

    cached = SentenceAudio.objects.filter(source_hash__in=hashes.values(), voice=voice)
    by_hash = {row.source_hash: row for row in cached}

    missing = [sentence for sentence in unique_sentences if hashes[sentence] not in by_hash]

    if missing:
        provider = get_provider()
        provider_name = type(provider).__name__
        results = provider.synthesize(missing, voice)

        # Провайдер обязан вернуть по результату на предложение. Свои мы
        # проверяем, но сторонний может нарушить контракт — тогда strict=True
        # бросит ValueError, и его нужно превратить в ошибку озвучки, иначе
        # страница упадёт с 500 вместо понятного сообщения.
        try:
            pairs = list(zip(missing, results, strict=True))
        except ValueError as error:
            raise TTSError(
                f"Provider returned {len(results)} results for {len(missing)} sentences."
            ) from error

        for sentence, synthesis in pairs:
            by_hash[hashes[sentence]] = _store(
                source_hash=hashes[sentence],
                voice=voice,
                sentence=sentence,
                synthesis=synthesis,
                provider_name=provider_name,
            )

        logger.info("Spoke %s new sentences with %s", len(pairs), voice)

    return {sentence: by_hash[hashes[sentence]] for sentence in unique_sentences}


def _store(
    *,
    source_hash: str,
    voice: str,
    sentence: str,
    synthesis: Synthesis,
    provider_name: str,
) -> SentenceAudio:
    """Write one synthesis to storage and to the database."""
    row = SentenceAudio(
        source_hash=source_hash,
        voice=voice,
        source_text=sentence,
        duration_ms=synthesis.duration_ms,
        timings=[timing_as_dict(timing) for timing in synthesis.timings],
        provider=provider_name,
    )

    # Имя файла из хэша и голоса: файл виден в media/ и понятно, чей он,
    # а два голоса одного предложения не спорят за одно имя.
    filename = f"{source_hash}-{voice}.{synthesis.extension}"
    row.audio.save(filename, ContentFile(synthesis.audio), save=False)

    try:
        # IntegrityError ловим снаружи atomic: внутри блока транзакция уже
        # помечена сломанной, и любой следующий запрос в ней тоже упал бы.
        with transaction.atomic():
            row.save()
    except IntegrityError:
        # То же предложение параллельно озвучил другой запрос. Это не ошибка:
        # берём его запись, а свой файл убираем, чтобы не оставлять сироту.
        row.audio.delete(save=False)
        logger.info("Audio for %r was stored by a parallel request", sentence)
        return SentenceAudio.objects.get(source_hash=source_hash, voice=voice)

    return row


def timing_as_dict(timing: CharTiming) -> dict[str, int]:
    """Flatten one timing for the ``timings`` JSON column."""
    return {
        "start": timing.start,
        "end": timing.end,
        "start_ms": timing.start_ms,
        "end_ms": timing.end_ms,
    }


def timing_from_dict(data: dict[str, int]) -> CharTiming:
    """Read one timing back from the ``timings`` JSON column."""
    return CharTiming(
        start=data["start"],
        end=data["end"],
        start_ms=data["start_ms"],
        end_ms=data["end_ms"],
    )


def word_timings(sentence: Sentence, audio: SentenceAudio) -> tuple[WordTiming | None, ...]:
    """Karaoke marks for every word of a sentence.

    Recomputed from stored character positions on every render rather than saved
    per word, so the marks always match the current segmentation.

    Args:
        sentence: The processed sentence.
        audio: Its cached audio.

    Returns:
        One entry per word, ``None`` where the word is never highlighted.
    """
    timings = [timing_from_dict(data) for data in audio.timings]
    return map_to_words(sentence, timings)


def has_cached_audio(sentences: list[str], voice: str | None = None) -> bool:
    """Whether every sentence is already spoken by this voice.

    Lets a caller tell a free re-open from one that reaches the service. Speech
    costs no money here, but the endpoint is unofficial and the synthesis is not
    free in CPU, so reopening a cached text should not spend the hourly limit.

    Args:
        sentences: Sentences in reading order.
        voice: Voice name, or ``None`` for the one in settings.

    Returns:
        ``True`` when nothing would have to be sent to the provider.
    """
    if not sentences:
        return True

    voice = voice or current_voice()
    hashes = {sentence_hash(sentence) for sentence in sentences}

    cached = set(
        SentenceAudio.objects.filter(source_hash__in=hashes, voice=voice).values_list(
            "source_hash", flat=True
        )
    )

    return hashes <= cached
