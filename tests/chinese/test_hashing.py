"""Tests for the sentence cache key."""

from apps.chinese.services import sentence_hash


def test_sentence_hash_ignores_surrounding_whitespace() -> None:
    """The same sentence with stray whitespace must hit the same cache entry."""
    assert sentence_hash("你好。") == sentence_hash("  你好。\n")


def test_sentence_hash_differs_for_different_text() -> None:
    assert sentence_hash("你好。") != sentence_hash("再见。")


def test_sentence_hash_is_stable_across_calls() -> None:
    """Cached rows outlive the process, so the key must not depend on it."""
    assert sentence_hash("银行在哪儿？") == sentence_hash("银行在哪儿？")
