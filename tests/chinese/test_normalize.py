"""Tests for cleaning up spacing before processing.

The spacing this removes is not exotic: learner materials print chinese with a
space between every word, and a reader pasting such a text is the normal case
for this project, not an edge one.
"""

from apps.chinese.services import collapse_chinese_spaces, process_text, segment


class TestCollapseChineseSpaces:
    """Only spacing between two chinese characters goes."""

    def test_spacing_between_words_is_removed(self) -> None:
        assert collapse_chinese_spaces("老 人 看 着 明信片") == "老人看着明信片"

    def test_several_spaces_go_together(self) -> None:
        assert collapse_chinese_spaces("老  人") == "老人"

    def test_tabs_count_as_spacing(self) -> None:
        assert collapse_chinese_spaces("老\t人") == "老人"

    def test_the_ideographic_space_counts_too(self) -> None:
        """U+3000 is what a chinese keyboard produces, and it is invisible in a diff."""
        assert collapse_chinese_spaces("老　人") == "老人"

    def test_spacing_before_punctuation_is_removed(self) -> None:
        assert collapse_chinese_spaces("你好 ，世界 。") == "你好，世界。"

    def test_line_breaks_survive(self) -> None:
        """The splitter ends a sentence at a line break, so collapsing them would
        glue separate paragraphs into one phrase."""
        assert collapse_chinese_spaces("第一句。\n第二句。") == "第一句。\n第二句。"

    def test_words_around_a_line_break_are_still_cleaned(self) -> None:
        assert collapse_chinese_spaces("老 人\n年轻 人") == "老人\n年轻人"

    def test_latin_keeps_its_spaces(self) -> None:
        """Otherwise 我说 hello world would become 我说 helloworld."""
        assert collapse_chinese_spaces("我说 hello world 你好") == "我说 hello world 你好"

    def test_text_without_chinese_is_untouched(self) -> None:
        assert collapse_chinese_spaces("hello world") == "hello world"

    def test_digits_keep_their_spaces(self) -> None:
        assert collapse_chinese_spaces("第 2 课") == "第 2 课"

    def test_text_without_spacing_is_unchanged(self) -> None:
        assert collapse_chinese_spaces("老人看着明信片") == "老人看着明信片"

    def test_empty_text_is_not_a_special_case(self) -> None:
        assert collapse_chinese_spaces("") == ""


class TestProcessingASpacedText:
    """What the reader actually gets out of a pasted learner text."""

    def test_it_segments_as_if_there_were_no_spaces(self) -> None:
        """The whole point: 老人 is one word again, not 老 plus 人.

        With the spacing left in, the dictionary explained "old" and "person"
        separately instead of "an old person".
        """
        spaced = process_text("老 人 看 着 明信片 说 。")

        assert [word.text for word in spaced.sentences[0].words] == segment("老人看着明信片说。")

    def test_the_sentence_text_carries_no_spacing_onwards(self) -> None:
        """This string is what goes to the speech service and what keys both caches.

        A space in it makes the synthesizer pause at every word, so the sentence
        is read word by word rather than spoken.
        """
        assert process_text("老 人 看 着 明信片 说 。").sentences[0].text == "老人看着明信片说。"

    def test_the_same_text_spaced_or_not_is_one_cache_entry(self) -> None:
        from apps.chinese.services import sentence_hash

        spaced = process_text("老 人 看 着 明信片 说 。").sentences[0].text
        plain = process_text("老人看着明信片说。").sentences[0].text

        assert sentence_hash(spaced) == sentence_hash(plain)

    def test_paragraphs_still_split_into_separate_sentences(self) -> None:
        processed = process_text("老 人 说 话\n年轻 人 写 字")

        assert [sentence.text for sentence in processed.sentences] == ["老人说话", "年轻人写字"]
