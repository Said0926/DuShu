"""Tests for sentence splitting."""

import pytest

from apps.chinese.services import split_into_sentences


def test_splits_on_full_stop() -> None:
    assert split_into_sentences("今天天气很好。我去公园。") == ["今天天气很好。", "我去公园。"]


def test_keeps_terminating_punctuation() -> None:
    """Punctuation carries intonation and becomes a different pause in shadowing."""
    sentences = split_into_sentences("你好！你是谁？")

    assert sentences == ["你好！", "你是谁？"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("他说。", ["他说。"]),
        ("真的吗？", ["真的吗？"]),
        ("不行！", ["不行！"]),
        ("第一；第二。", ["第一；", "第二。"]),
        ("他说…", ["他说…"]),
    ],
)
def test_every_terminator_is_recognised(text: str, expected: list[str]) -> None:
    assert split_into_sentences(text) == expected


def test_consecutive_terminators_stay_together() -> None:
    """真的吗？！ is one ending, not an empty sentence after the question mark."""
    assert split_into_sentences("真的吗？！我不信。") == ["真的吗？！", "我不信。"]


def test_ellipsis_is_not_split_into_pieces() -> None:
    assert split_into_sentences("他说……然后走了。") == ["他说……", "然后走了。"]


def test_closing_quote_belongs_to_the_previous_sentence() -> None:
    """「你好！」is one line of speech, not a line plus a stray bracket."""
    assert split_into_sentences("「你好！」他说。") == ["「你好！」", "他说。"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("“太好了！”", ["“太好了！”"]),
        ("『真的？』", ["『真的？』"]),
        ("（他笑了。）", ["（他笑了。）"]),
    ],
)
def test_all_closing_characters_are_attached(text: str, expected: list[str]) -> None:
    assert split_into_sentences(text) == expected


def test_line_break_ends_a_sentence_but_is_dropped() -> None:
    """Unlike punctuation, a line break is a boundary and not part of the text."""
    assert split_into_sentences("第一行\n第二行") == ["第一行", "第二行"]


def test_blank_lines_do_not_produce_empty_sentences() -> None:
    assert split_into_sentences("第一行\n\n\n第二行") == ["第一行", "第二行"]


def test_trailing_text_without_punctuation_is_kept() -> None:
    """Users paste fragments; dropping the tail would silently lose text."""
    assert split_into_sentences("你好。再见") == ["你好。", "再见"]


@pytest.mark.parametrize("text", ["", "   ", "\n\n", "  \n  \n "])
def test_empty_input_gives_no_sentences(text: str) -> None:
    assert split_into_sentences(text) == []


def test_punctuation_only_input_is_kept() -> None:
    """Odd input, but it must not crash or vanish."""
    assert split_into_sentences("。。。") == ["。。。"]


def test_nested_quotes_are_not_broken() -> None:
    text = "他说：「我觉得『好』很好。」"

    assert split_into_sentences(text) == ["他说：「我觉得『好』很好。」"]
