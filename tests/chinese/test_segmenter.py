"""Tests for word segmentation."""

from apps.chinese.services import segment


def test_splits_a_sentence_into_words() -> None:
    assert segment("我打算去公园") == ["我", "打算", "去", "公园"]


def test_punctuation_becomes_its_own_token() -> None:
    """DESIGN.md renders punctuation as a separate span, never inside a word."""
    tokens = segment("你好，世界。")

    assert "，" in tokens
    assert "。" in tokens
    assert "你好" in tokens


def test_whitespace_is_dropped() -> None:
    """Spacing between words comes from CSS, not from tokens."""
    assert segment("你好 世界") == ["你好", "世界"]


def test_empty_sentence_gives_no_tokens() -> None:
    assert segment("") == []


def test_latin_words_survive_segmentation() -> None:
    tokens = segment("我喜欢Python")

    assert "Python" in tokens
