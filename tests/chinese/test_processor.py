"""Tests for the full processing pipeline."""

import pytest
from django.test import override_settings

from apps.chinese.exceptions import TextTooLongError
from apps.chinese.services import process_text
from apps.chinese.types import WordKind


def test_processes_a_short_text() -> None:
    result = process_text("今天天气很好。")

    assert len(result.sentences) == 1
    assert result.sentences[0].text == "今天天气很好。"


@pytest.mark.parametrize(
    "text",
    [
        "今天天气很好。",
        "我打算去公园走走。",
        "「你好！」他说。",
        "我用Python写代码，很方便。",
    ],
)
def test_tokens_reassemble_into_the_sentence(text: str) -> None:
    """Nothing may be lost or invented during segmentation.

    Asserting an exact token list would test jieba's dictionary rather than our
    code, and that dictionary changes between versions. What matters to us is
    that the rendered page shows the same text the user submitted.
    """
    sentence = process_text(text).sentences[0]

    assert "".join(word.text for word in sentence.words) == sentence.text


def test_sentence_indexes_start_at_zero_and_increase() -> None:
    """Indexes are the cache key for translations and the sentence number in shadowing."""
    result = process_text("第一句。第二句。第三句。")

    assert [sentence.index for sentence in result.sentences] == [0, 1, 2]


def test_words_carry_readings_and_tones() -> None:
    result = process_text("我打算去公园走走。")
    words = {word.text: word for word in result.sentences[0].words}

    assert words["打算"].pinyin == "dǎ suàn"
    assert [syllable.tone for syllable in words["打算"].syllables] == [3, 4]


def test_punctuation_is_marked_as_such() -> None:
    result = process_text("你好，世界。")
    kinds = {word.text: word.kind for word in result.sentences[0].words}

    assert kinds["，"] is WordKind.PUNCT
    assert kinds["。"] is WordKind.PUNCT
    assert kinds["你好"] is WordKind.CHINESE


def test_ambiguous_reading_resolved_through_the_whole_pipeline() -> None:
    """The end-to-end version of the segmentation-before-pinyin rule."""
    result = process_text("我行了。银行在哪儿？")

    first, second = result.sentences
    walking = next(word for word in first.words if "行" in word.text)
    bank = next(word for word in second.words if word.text == "银行")

    assert "xíng" in walking.pinyin
    assert bank.pinyin == "yín háng"


@pytest.mark.parametrize("text", ["", "   ", "\n\n"])
def test_empty_input_gives_no_sentences(text: str) -> None:
    assert process_text(text).sentences == ()


def test_mixed_chinese_and_latin_text() -> None:
    result = process_text("我用Python写代码。")
    kinds = {word.text: word.kind for word in result.sentences[0].words}

    assert kinds["Python"] is WordKind.OTHER
    assert kinds["代码"] is WordKind.CHINESE


@override_settings(MAX_TEXT_LENGTH=10)
def test_text_over_the_limit_is_rejected() -> None:
    with pytest.raises(TextTooLongError):
        process_text("一" * 11)


@override_settings(MAX_TEXT_LENGTH=10)
def test_text_exactly_at_the_limit_is_accepted() -> None:
    """Off-by-one guard: the limit itself must still pass."""
    result = process_text("一" * 10)

    assert len(result.sentences) == 1


@override_settings(MAX_TEXT_LENGTH=10)
def test_limit_applies_after_trimming_whitespace() -> None:
    """Trailing newlines from a paste should not push a valid text over the limit."""
    result = process_text("   " + "一" * 10 + "\n\n")

    assert len(result.sentences) == 1


@override_settings(MAX_TEXT_LENGTH=10)
def test_error_message_names_both_numbers() -> None:
    """The view turns this into a user-facing message, so it has to be readable."""
    with pytest.raises(TextTooLongError, match=r"11.*10"):
        process_text("一" * 11)


def test_result_is_immutable() -> None:
    """Several features read the same processed text; none may mutate it."""
    result = process_text("你好。")

    with pytest.raises(AttributeError):
        result.sentences[0].words[0].pinyin = "changed"  # type: ignore[misc]
