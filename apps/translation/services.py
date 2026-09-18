"""Translating sentences, with everything cached in the database."""

import logging
from collections.abc import Iterator

from django.conf import settings
from django.utils.module_loading import import_string

from apps.translation.exceptions import TranslationError
from apps.translation.models import SentenceTranslation, sentence_hash
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

    return provider_class()


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

            for sentence, translation in zip(batch, translations, strict=True):
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
