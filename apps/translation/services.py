"""Translating sentences, with everything cached in the database."""

import logging
from collections.abc import Iterator

from django.conf import settings
from django.utils.module_loading import import_string

from apps.chinese.services import sentence_hash
from apps.translation.exceptions import TranslationError
from apps.translation.models import SentenceTranslation
from apps.translation.providers import TranslationProvider

logger = logging.getLogger(__name__)


def get_provider() -> TranslationProvider:
    """Build the provider named in settings.

    ``import_string`` turns the dotted path from ``TRANSLATION_PROVIDER`` into a
    class, so switching backends is a settings change rather than a code change.

    Raises:
        TranslationError: If the path is wrong or the provider cannot start.
    """
    try:
        provider_class = import_string(settings.TRANSLATION_PROVIDER)
    except ImportError as error:
        raise TranslationError(
            f"Cannot import TRANSLATION_PROVIDER {settings.TRANSLATION_PROVIDER!r}."
        ) from error

    try:
        return provider_class()
    except TranslationError:
        raise
    except (TypeError, AttributeError) as error:
        # Путь ведёт не на класс провайдера, или конструктор не принимает
        # нулевые аргументы. Это ошибка настройки, а не сбой перевода, но
        # наружу она должна выйти тем же типом: страница обязана пережить её.
        raise TranslationError(
            f"TRANSLATION_PROVIDER {settings.TRANSLATION_PROVIDER!r} is not a usable provider."
        ) from error


def _batched(items: list[str], size: int) -> Iterator[list[str]]:
    """Split a list into chunks of at most ``size`` items."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def translate_sentences(sentences: list[str], target_lang: str) -> list[str]:
    """Translate sentences, reusing anything already translated.

    Three things happen here, and each one saves money:

    - the cache is read first, so a text that was opened before costs nothing;
    - duplicates within one request are collapsed, so a repeated line is paid
      for once;
    - what is left goes out in batches instead of one request per sentence.

    Args:
        sentences: Sentences in reading order.
        target_lang: Language code.

    Returns:
        Translations aligned with the input: same length, same order.

    Raises:
        TranslationError: If the provider fails. Nothing is cached in that case.
    """
    if not sentences:
        return []

    # Одинаковые предложения в одном тексте переводим один раз.
    unique_sentences = list(dict.fromkeys(sentences))
    hashes = {sentence: sentence_hash(sentence) for sentence in unique_sentences}

    cached_rows = SentenceTranslation.objects.filter(
        source_hash__in=hashes.values(),
        target_language=target_lang,
    )
    by_hash = {row.source_hash: row.translated_text for row in cached_rows}

    missing = [sentence for sentence in unique_sentences if hashes[sentence] not in by_hash]

    if missing:
        provider = get_provider()
        provider_name = type(provider).__name__
        batch_size = settings.TRANSLATION_BATCH_SIZE

        fresh_rows: list[SentenceTranslation] = []

        for batch in _batched(missing, batch_size):
            translations = provider.translate(batch, target_lang)

            # Провайдер обязан вернуть по переводу на предложение. Свой мы
            # проверяем, но сторонний может нарушить контракт — тогда strict=True
            # бросит ValueError, и его нужно превратить в ошибку перевода,
            # иначе страница упадёт с 500 вместо понятного сообщения.
            try:
                pairs = list(zip(batch, translations, strict=True))
            except ValueError as error:
                raise TranslationError(
                    f"Provider returned {len(translations)} translations "
                    f"for {len(batch)} sentences."
                ) from error

            for sentence, translation in pairs:
                by_hash[hashes[sentence]] = translation
                fresh_rows.append(
                    SentenceTranslation(
                        source_hash=hashes[sentence],
                        target_language=target_lang,
                        source_text=sentence,
                        translated_text=translation,
                        provider=provider_name,
                    )
                )

        # ignore_conflicts — на случай, если те же предложения параллельно
        # перевёл другой запрос: тогда запись уже есть, и это не ошибка.
        SentenceTranslation.objects.bulk_create(fresh_rows, ignore_conflicts=True)
        logger.info("Translated %s new sentences into %s", len(fresh_rows), target_lang)

    return [by_hash[hashes[sentence]] for sentence in sentences]


def has_cached_translations(sentences: list[str], target_lang: str) -> bool:
    """Whether every sentence is already translated into this language.

    Lets a caller tell a free re-read from one that will cost money. Reopening a
    saved text is answered entirely from the cache, so it should not spend the
    hourly limit — that limit exists to bound what goes out to a paid provider,
    not to count page views.

    Args:
        sentences: Sentences in reading order.
        target_lang: Language code.

    Returns:
        ``True`` when nothing would have to be sent to the provider.
    """
    if not sentences:
        return True

    hashes = {sentence_hash(sentence) for sentence in sentences}

    cached = set(
        SentenceTranslation.objects.filter(
            source_hash__in=hashes,
            target_language=target_lang,
        ).values_list("source_hash", flat=True)
    )

    return hashes <= cached
