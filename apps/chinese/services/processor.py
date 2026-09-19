"""The single entry point into text processing."""

from django.conf import settings

from apps.chinese.exceptions import TextTooLongError
from apps.chinese.types import ProcessedText, Sentence

from .normalize import collapse_chinese_spaces
from .pinyin import build_word
from .segmenter import segment
from .splitter import split_into_sentences


def process_text(raw_text: str) -> ProcessedText:
    """Turn raw text into sentences, words and syllables.

    This is the only function other apps should call. Reader, shadowing and the
    library all go through it, so they always see the same structure.

    Args:
        raw_text: Text as submitted by the user.

    Returns:
        The processed text. Empty input gives a result with no sentences.

    Raises:
        TextTooLongError: If the text exceeds ``settings.MAX_TEXT_LENGTH``.
    """
    # Нормализуем до всего остального, чтобы дальше по конвейеру — сегментация,
    # хэши кэша, озвучка — все видели один и тот же текст. Иначе один и тот же
    # отрывок с пробелами и без попадал бы в разные записи кэша.
    text = collapse_chinese_spaces(raw_text.strip())

    # Проверяем до обработки: смысла сегментировать текст, который мы всё равно
    # отклоним, нет — а на длинном тексте это заметная работа.
    if len(text) > settings.MAX_TEXT_LENGTH:
        raise TextTooLongError(
            f"Text is {len(text)} characters long, the limit is {settings.MAX_TEXT_LENGTH}."
        )

    sentences = tuple(
        Sentence(
            index=index,
            text=sentence_text,
            words=tuple(build_word(token) for token in segment(sentence_text)),
        )
        for index, sentence_text in enumerate(split_into_sentences(text))
    )

    return ProcessedText(sentences=sentences)
