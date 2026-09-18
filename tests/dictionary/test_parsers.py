"""Tests for the dictionary dump parsers.

No database is involved: parsers return plain objects on purpose.
"""

import gzip
from pathlib import Path

import pytest

from apps.dictionary.parsers import ParsedEntry, merge_duplicates, numbered_pinyin_to_diacritics
from apps.dictionary.parsers.bkrs import parse_block
from apps.dictionary.parsers.bkrs import parse_file as parse_bkrs
from apps.dictionary.parsers.cedict import parse_file as parse_cedict
from apps.dictionary.parsers.cedict import parse_line

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestPinyinConversion:
    """Dumps store tones as digits; the tooltip shows diacritics."""

    @pytest.mark.parametrize(
        ("numbered", "expected"),
        [
            ("yin2", "yín"),
            ("yin2 hang2", "yín háng"),
            ("xue2 xi2", "xué xí"),
            ("de5", "de"),
        ],
    )
    def test_converts_tones(self, numbered: str, expected: str) -> None:
        assert numbered_pinyin_to_diacritics(numbered) == expected

    @pytest.mark.parametrize(
        ("numbered", "expected"),
        [
            ("nu:3", "nǚ"),
            ("lu:4", "lǜ"),
            ("nu:e4", "nüè"),
        ],
    )
    def test_ascii_umlaut_becomes_a_real_one(self, numbered: str, expected: str) -> None:
        """CC-CEDICT writes ü as u:. Left alone, 女 would read nǔ: instead of nǚ."""
        assert numbered_pinyin_to_diacritics(numbered) == expected

    def test_every_syllable_keeps_its_tone(self) -> None:
        """Converting the phrase in one go drops all tones but the first."""
        assert numbered_pinyin_to_diacritics("xue2 xi2 zhong1 wen2") == "xué xí zhōng wén"

    @pytest.mark.parametrize("value", ["11", "2019", "CD"])
    def test_non_pinyin_is_left_alone(self, value: str) -> None:
        """to_tone mangles these instead of failing: "11" would come back as "1"."""
        assert numbered_pinyin_to_diacritics(value) == value

    def test_mixed_pinyin_and_digits(self) -> None:
        """11区 is a real CC-CEDICT headword."""
        assert numbered_pinyin_to_diacritics("11 Qu1") == "11 Qū"


class TestCedictParser:
    def test_parses_a_normal_line(self) -> None:
        entry = parse_line("銀行 银行 [yin2 hang2] /bank/CL:家[jia1]/")

        assert entry == ParsedEntry(
            simplified="银行",
            traditional="銀行",
            pinyin="yín háng",
            definitions=["bank", "CL:家[jia1]"],
        )

    @pytest.mark.parametrize(
        "line",
        ["# comment", "#! version=1", "", "   ", "нет формата", "銀行 银行 [yin2 hang2] //"],
    )
    def test_skips_lines_that_are_not_entries(self, line: str) -> None:
        """A dump of 125k lines will contain a few odd ones; they must not abort it."""
        assert parse_line(line) is None

    def test_reads_the_whole_file(self) -> None:
        entries = list(parse_cedict(FIXTURES / "cedict_sample.txt"))

        assert len(entries) == 9
        assert entries[0].simplified == "银行"

    def test_reads_a_gzipped_file(self, tmp_path: Path) -> None:
        """Dumps are published compressed; unpacking 300 MB just to read it is waste."""
        source = (FIXTURES / "cedict_sample.txt").read_bytes()
        archive = tmp_path / "dump.txt.gz"
        archive.write_bytes(gzip.compress(source))

        assert len(list(parse_cedict(archive))) == 9


class TestBkrsParser:
    def test_parses_an_entry(self) -> None:
        entry = parse_block("银行\n yínháng\n [m1]банк[/m]")

        assert entry is not None
        assert entry.simplified == "银行"
        assert entry.pinyin == "yínháng"
        assert entry.definitions == ["банк"]

    def test_splits_numbered_senses(self) -> None:
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["三岛"].definitions == [
            "1) Три острова (Англия, Шотландия)",
            "2) Мисима (фамилия)",
        ]

    def test_drops_usage_examples(self) -> None:
        """Examples run several lines and would make the tooltip unreadable."""
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["学习"].definitions == ["учиться, изучать"]

    def test_keeps_labels_as_text(self) -> None:
        """[p]разг.[/p] is a useful hint, only the markup goes away."""
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["你好"].definitions == ["разг. привет"]

    def test_skips_the_file_header(self) -> None:
        entries = list(parse_bkrs(FIXTURES / "bkrs_sample.txt"))

        assert len(entries) == 7
        assert all(not e.simplified.startswith("#") for e in entries)

    def test_dsl_escapes_are_removed(self) -> None:
        """A leftover backslash made 公园 read as "1) \\ парк" — 21k entries were affected."""
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["公园"].definitions == ["1) парк", "2) казённые земли"]

    def test_space_left_by_an_escape_is_closed_up(self) -> None:
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["歪曲"].definitions == ["извращать; искажать"]

    def test_stray_backslash_is_dropped(self) -> None:
        """A doubled backslash in the dump leaves one behind; it means nothing here."""
        entries = {e.simplified: e for e in parse_bkrs(FIXTURES / "bkrs_sample.txt")}

        assert entries["口探"].definitions == ["оральное измерение"]


class TestMergeDuplicates:
    """CC-CEDICT lists each traditional spelling separately."""

    def test_variants_merge_into_one_entry(self) -> None:
        entries = {
            (e.simplified, e.pinyin): e
            for e in merge_duplicates(parse_cedict(FIXTURES / "cedict_sample.txt"))
        }

        assert ("俊", "jùn") in entries
        assert len([key for key in entries if key[0] == "俊"]) == 1

    def test_real_meanings_come_before_cross_references(self) -> None:
        """Without this, 俊 would show "old variant of 俊" as its translation."""
        entries = {
            (e.simplified, e.pinyin): e
            for e in merge_duplicates(parse_cedict(FIXTURES / "cedict_sample.txt"))
        }

        definitions = entries[("俊", "jùn")].definitions
        assert definitions[:3] == ["smart", "eminent", "handsome"]
        assert all("variant of" in text for text in definitions[3:])

    def test_different_readings_stay_separate(self) -> None:
        """行 as xíng and as háng are different words, not one word with two readings."""
        entries = [
            e
            for e in merge_duplicates(parse_cedict(FIXTURES / "cedict_sample.txt"))
            if e.simplified == "行"
        ]

        assert {e.pinyin for e in entries} == {"xíng", "háng"}

    def test_prefers_the_main_traditional_spelling(self) -> None:
        entries = {
            (e.simplified, e.pinyin): e
            for e in merge_duplicates(parse_cedict(FIXTURES / "cedict_sample.txt"))
        }

        assert entries[("俊", "jùn")].traditional == "俊"

    def test_entries_without_duplicates_pass_through(self) -> None:
        source = [
            ParsedEntry("你好", "你好", "nǐ hǎo", ["hello"]),
            ParsedEntry("银行", "銀行", "yín háng", ["bank"]),
        ]

        assert list(merge_duplicates(source)) == source
