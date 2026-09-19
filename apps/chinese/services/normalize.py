"""Cleaning up text before it is processed."""

import re

# Что считаем китайским: иероглифы, расширение A, китайская пунктуация и
# полноширинные формы. Идеографический пробел U+3000 из диапазона пунктуации
# исключён намеренно — он сам пробел, а не сосед пробела.
CHINESE = r"[㐀-䶿一-鿿、-〿！-･]"

# Пробел, табуляция или идеографический пробел между двумя китайскими символами.
# Перевода строки здесь нет и быть не должно: по нему splitter режет предложения,
# и схлопывание строк склеило бы абзацы в одну фразу.
#
# Границы заданы просмотром вперёд и назад, а не обычными группами: они ничего
# не «съедают», поэтому в цепочке «老 人 看 着» убираются все пробелы за один
# проход, а не через один.
_SPACE_BETWEEN_CHINESE = re.compile(rf"(?<={CHINESE})[ \t　]+(?={CHINESE})")


def collapse_chinese_spaces(text: str) -> str:
    """Remove spacing printed between chinese words.

    Learner materials routinely print chinese with a space between every word,
    and that is exactly the audience this project has — so such a text arrives
    pasted as often as a normal one. It has to be cleaned up, because the spaces
    do real damage twice over:

    - the speech service treats a space as a boundary and pauses at every one of
      them, so the sentence is read word by word instead of spoken;
    - jieba takes the spacing as given and stops joining words, so 老人 becomes
      老 plus 人 — and the dictionary then explains "old" and "person" instead of
      "an old person".

    Only spacing between two chinese characters goes. Spaces around latin words
    and digits stay, or ``我说 hello world`` would become ``我说 helloworld``.

    Args:
        text: Text as submitted by the user.

    Returns:
        The same text with inter-word spacing removed and line breaks intact.
    """
    return _SPACE_BETWEEN_CHINESE.sub("", text)
