"""Tests for the saved text model helpers."""

from apps.library.models import TITLE_LENGTH, content_hash, make_title


def test_short_text_becomes_the_whole_title() -> None:
    assert make_title("今天天气很好。") == "今天天气很好。"


def test_long_text_is_cut_with_an_ellipsis() -> None:
    title = make_title("中" * 100)

    assert len(title) == TITLE_LENGTH + 1
    assert title.endswith("…")


def test_title_takes_only_the_first_line() -> None:
    """A poem glued into one line would read as noise in the list."""
    assert make_title("床前明月光\n疑是地上霜") == "床前明月光"


def test_title_of_an_empty_text_is_empty() -> None:
    """Saving is refused earlier, so this only has to not explode."""
    assert make_title("   \n  ") == ""


def test_same_text_with_different_surrounding_space_has_one_hash() -> None:
    """Otherwise pasting the same text twice would make two library entries."""
    assert content_hash("你好。") == content_hash("  你好。\n")


def test_different_texts_have_different_hashes() -> None:
    assert content_hash("你好。") != content_hash("再见。")
