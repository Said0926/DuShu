"""Turning tokens into words with readings and tones."""

import unicodedata

from pypinyin import Style, pinyin

from apps.chinese.types import NEUTRAL_TONE, Syllable, Word, WordKind

# Основной блок иероглифов (CJK Unified Ideographs). Редкие знаки из расширений
# сюда не попадают, но в обычных текстах они не встречаются.
_HANZI_START = "一"
_HANZI_END = "鿿"


def _contains_hanzi(text: str) -> bool:
    """Return True if the token contains at least one chinese character."""
    return any(_HANZI_START <= char <= _HANZI_END for char in text)


def _is_punctuation(text: str) -> bool:
    """Return True if every character is a punctuation mark.

    ``unicodedata.category`` returns codes starting with ``P`` for punctuation,
    which covers both chinese marks (。，「) and latin ones (.,") without
    listing them by hand.
    """
    return all(unicodedata.category(char).startswith("P") for char in text)


def classify(token: str) -> WordKind:
    """Decide how a token should be rendered."""
    if _contains_hanzi(token):
        return WordKind.CHINESE
    if _is_punctuation(token):
        return WordKind.PUNCT
    return WordKind.OTHER


def _extract_tone(numbered_syllable: str) -> int:
    """Read the tone number off a TONE3 syllable.

    ``"hao3"`` gives 3. Anything without a trailing digit is treated as neutral,
    which happens for latin letters and digits mixed into a chinese token.
    """
    if numbered_syllable and numbered_syllable[-1].isdigit():
        return int(numbered_syllable[-1])
    return NEUTRAL_TONE


def _build_syllables(
    token: str,
    display: list[list[str]],
    numbered: list[list[str]],
) -> tuple[Syllable, ...]:
    """Pair each piece of the token with its reading.

    Cannot simply zip the token with the readings character by character:
    pypinyin merges a run of non-chinese characters into a single entry, so
    ``CT扫描`` comes back as three readings for four characters. Zipping would
    then hand 扫's reading to the letter T.

    Instead we walk the token and the readings together, taking one character
    for a hanzi and as many characters as the entry is long for anything else.

    Args:
        token: The token being processed.
        display: pypinyin output with tone diacritics.
        numbered: pypinyin output with tone numbers, same length as display.

    Returns:
        Syllables in order. Non-chinese pieces carry an empty reading, which is
        how the template knows to render them without a ruby annotation.
    """
    syllables: list[Syllable] = []
    position = 0

    # strict=True здесь безопасно: оба списка — результат одной функции на одном
    # и том же входе, поэтому разная длина означала бы поломку в pypinyin.
    for shown, numeric in zip(display, numbered, strict=True):
        reading = shown[0]

        if _contains_hanzi(token[position]):
            syllables.append(
                Syllable(char=token[position], pinyin=reading, tone=_extract_tone(numeric[0]))
            )
            position += 1
        else:
            # Для нераспознанного куска pypinyin возвращает его самого,
            # поэтому длина куска равна длине ответа.
            piece = token[position : position + len(reading)]
            syllables.append(Syllable(char=piece, pinyin="", tone=NEUTRAL_TONE))
            position += len(piece)

    return tuple(syllables)


def build_word(token: str) -> Word:
    """Build a Word from a token, looking up readings when it is chinese.

    The token is passed to pypinyin whole, never character by character. That is
    the point of segmenting first: pypinyin picks the reading from the context of
    the surrounding characters, so 银行 comes out as ``yín háng`` while 行走 comes
    out as ``xíng zǒu``. Per-character lookups would get both wrong.

    Args:
        token: A single token from the segmenter.

    Returns:
        A Word. Non-chinese tokens carry no pinyin and no syllables.
    """
    kind = classify(token)
    if kind is not WordKind.CHINESE:
        return Word(text=token, pinyin="", syllables=(), kind=kind)

    # Два вызова, потому что pypinyin не отдаёт диакритику и номер тона сразу:
    # Style.TONE даёт "hǎo" для показа, Style.TONE3 даёт "hao3" для класса тона.
    # neutral_tone_with_five=True заставляет его писать "de5" вместо "de",
    # иначе нейтральный тон пришлось бы угадывать по отсутствию цифры.
    display = pinyin(token, style=Style.TONE, heteronym=False)
    numbered = pinyin(token, style=Style.TONE3, heteronym=False, neutral_tone_with_five=True)

    syllables = _build_syllables(token, display, numbered)

    return Word(
        text=token,
        # Куски без чтения в data-pinyin не попадают: атрибут нужен для подсказки
        # словаря, а латиница там только мешает.
        pinyin=" ".join(syllable.pinyin for syllable in syllables if syllable.pinyin),
        syllables=syllables,
        kind=kind,
    )
