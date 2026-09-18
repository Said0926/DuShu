"""Tests for readings, tones and token classification."""

import pytest

from apps.chinese.services import build_word, classify
from apps.chinese.types import WordKind


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("你好", WordKind.CHINESE),
        ("X光", WordKind.CHINESE),
        ("。", WordKind.PUNCT),
        ("，", WordKind.PUNCT),
        ("「", WordKind.PUNCT),
        ("...", WordKind.PUNCT),
        ("hello", WordKind.OTHER),
        ("2024", WordKind.OTHER),
    ],
)
def test_classify(token: str, expected: WordKind) -> None:
    assert classify(token) is expected


def test_word_kind_compares_to_plain_string() -> None:
    """Templates compare against strings, so StrEnum has to behave like one."""
    assert build_word("你好").kind == "chinese"


class TestAmbiguousReadings:
    """The whole reason segmentation happens before pinyin lookup."""

    def test_hang_in_bank(self) -> None:
        assert build_word("银行").pinyin == "yín háng"

    def test_xing_in_walking(self) -> None:
        assert build_word("行走").pinyin == "xíng zǒu"

    def test_chang_in_great_wall(self) -> None:
        assert build_word("长城").pinyin == "cháng chéng"

    def test_zhang_in_growth(self) -> None:
        assert build_word("生长").pinyin == "shēng zhǎng"

    def test_liao_in_understand(self) -> None:
        assert build_word("了解").pinyin == "liǎo jiě"


def test_neutral_tone_gets_number_five() -> None:
    """了 as a particle has no diacritic, but highlighting still needs a class."""
    word = build_word("他了")

    assert [syllable.tone for syllable in word.syllables] == [1, 5]
    assert word.syllables[1].pinyin == "le"


@pytest.mark.parametrize(
    ("token", "expected_tones"),
    [
        ("妈", [1]),
        ("麻", [2]),
        ("马", [3]),
        ("骂", [4]),
    ],
)
def test_all_four_tones_are_detected(token: str, expected_tones: list[int]) -> None:
    assert [syllable.tone for syllable in build_word(token).syllables] == expected_tones


def test_syllables_line_up_with_characters() -> None:
    """Ruby markup pairs each hanzi with its own reading, so counts must match."""
    word = build_word("公园")

    assert [syllable.char for syllable in word.syllables] == ["公", "园"]
    assert [syllable.pinyin for syllable in word.syllables] == ["gōng", "yuán"]


def test_pinyin_field_is_ready_for_the_data_attribute() -> None:
    """DESIGN.md renders data-pinyin="dǎ suàn" — syllables joined by a space."""
    assert build_word("打算").pinyin == "dǎ suàn"


@pytest.mark.parametrize("token", ["。", "hello", "2024"])
def test_non_chinese_tokens_carry_no_reading(token: str) -> None:
    word = build_word(token)

    assert word.pinyin == ""
    assert word.syllables == ()
    assert word.text == token


class TestMixedTokens:
    """Tokens holding both hanzi and latin characters.

    pypinyin merges a run of non-chinese characters into one entry, so its output
    is shorter than the token. Pairing them up naively gives hanzi the wrong
    readings, and nothing about the result looks broken enough to notice.
    """

    def test_single_latin_letter(self) -> None:
        word = build_word("X光")

        assert word.kind is WordKind.CHINESE
        assert [(s.char, s.pinyin) for s in word.syllables] == [("X", ""), ("光", "guāng")]

    def test_multi_letter_run_stays_one_piece(self) -> None:
        """CT扫描 is four characters but only three pypinyin entries."""
        word = build_word("CT扫描")

        assert [(s.char, s.pinyin) for s in word.syllables] == [
            ("CT", ""),
            ("扫", "sǎo"),
            ("描", "miáo"),
        ]

    def test_long_latin_run(self) -> None:
        word = build_word("iPhone手机")

        assert [s.char for s in word.syllables] == ["iPhone", "手", "机"]
        assert [s.pinyin for s in word.syllables] == ["", "shǒu", "jī"]

    def test_latin_run_after_hanzi(self) -> None:
        word = build_word("光ABC")

        assert [(s.char, s.pinyin) for s in word.syllables] == [("光", "guāng"), ("ABC", "")]

    def test_digits_are_handled_like_latin(self) -> None:
        word = build_word("3个")

        assert [(s.char, s.pinyin) for s in word.syllables] == [("3", ""), ("个", "gè")]

    @pytest.mark.parametrize("token", ["X光", "CT扫描", "iPhone手机", "光ABC", "3个"])
    def test_syllables_reassemble_into_the_token(self, token: str) -> None:
        """The invariant that catches any future off-by-one in the pairing."""
        word = build_word(token)

        assert "".join(syllable.char for syllable in word.syllables) == token

    def test_data_pinyin_skips_pieces_without_a_reading(self) -> None:
        """The attribute feeds dictionary lookups, where latin text is noise."""
        assert build_word("CT扫描").pinyin == "sǎo miáo"
