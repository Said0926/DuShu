"""Splitting a sentence into words."""

import logging

import jieba

# jieba заводит собственный обработчик логов при импорте и на уровне DEBUG
# печатает построение словаря при каждом запуске. Настройка LOGGING в settings
# его не перекрывает — у библиотеки для этого своя функция.
jieba.setLogLevel(logging.WARNING)


def segment(sentence: str) -> list[str]:
    """Split a sentence into tokens.

    Chinese is written without spaces, so word boundaries have to be guessed.
    jieba does that, and its output is what makes per-word pinyin and dictionary
    lookups possible at all.

    Punctuation comes back as its own token, which is exactly what the markup
    needs: it must not end up inside a word element.

    Args:
        sentence: A single sentence.

    Returns:
        Tokens in order, without whitespace-only entries.

    Examples:
        >>> segment("我打算去公园。")
        ['我', '打算', '去', '公园', '。']
    """
    # jieba возвращает пробелы отдельными токенами — в разметке они не нужны,
    # отступы между словами задаёт CSS.
    return [token for token in jieba.lcut(sentence) if token.strip()]


def warm_up() -> None:
    """Load the jieba dictionary ahead of time.

    The first call to jieba loads a dictionary and takes about a second. Doing it
    on startup keeps that delay out of the first user request.
    """
    jieba.initialize()
