"""Splitting chinese text into sentences."""

# Символы, которыми заканчивается предложение. Они остаются в предложении:
# без них пропадает интонация, а для озвучки это разные паузы.
SENTENCE_TERMINATORS = frozenset("。！？；…")

# Закрывающие кавычки и скобки. Если они идут сразу после точки, то принадлежат
# предыдущему предложению: 「你好！」— это одна реплика, а не реплика и обрывок.
CLOSING_CHARACTERS = frozenset("」』”’）〉》】｝\"')]}>»")


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping punctuation attached.

    Sentences end at ``。！？；…`` or at a line break. A line break is a boundary
    but is not part of the text, unlike the punctuation marks.

    Args:
        text: Raw text as submitted by the user.

    Returns:
        Sentences in order. Empty and whitespace-only fragments are dropped.

    Examples:
        >>> split_into_sentences("「你好！」他说。")
        ['「你好！」', '他说。']
        >>> split_into_sentences("真的吗？！")
        ['真的吗？！']
    """
    sentences: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        """Move whatever is in the buffer into the result, if it is not empty."""
        sentence = "".join(buffer).strip()
        buffer.clear()
        if sentence:
            sentences.append(sentence)

    # Идём вручную по индексу, а не через for: после терминатора нужно заглядывать
    # вперёд и забирать ещё несколько символов, а for такой возможности не даёт.
    position = 0
    length = len(text)

    while position < length:
        char = text[position]

        if char == "\n":
            flush()
            position += 1
            continue

        buffer.append(char)
        position += 1

        if char not in SENTENCE_TERMINATORS:
            continue

        # Подряд идущие терминаторы — одна концовка, а не несколько пустых
        # предложений: 真的吗？！ и 他说…… должны остаться целыми.
        while position < length and text[position] in SENTENCE_TERMINATORS:
            buffer.append(text[position])
            position += 1

        # Забираем закрывающие кавычки и скобки.
        while position < length and text[position] in CLOSING_CHARACTERS:
            buffer.append(text[position])
            position += 1

        flush()

    # Последнее предложение может не иметь завершающего знака.
    flush()

    return sentences
