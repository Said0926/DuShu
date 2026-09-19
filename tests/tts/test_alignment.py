"""Tests for turning boundary events into karaoke marks.

This is the part of the stage where a bug would be invisible: a wrong mapping
does not raise, it just highlights the wrong word. So the cases that matter most
here are the ones where the speech service and jieba disagree.
"""

from apps.chinese.services import process_text
from apps.tts.alignment import SpokenChunk, align, map_to_words
from apps.tts.providers.base import CharTiming

# Одна миллисекунда — десять тысяч тиков по сто наносекунд.
MS = 10_000


def chunk(text: str, start_ms: int, length_ms: int) -> SpokenChunk:
    """Build an event the way the provider reports it, in ticks."""
    return SpokenChunk(text=text, offset_ticks=start_ms * MS, duration_ticks=length_ms * MS)


def only_sentence(text: str):
    """Process a text known to be a single sentence."""
    return process_text(text).sentences[0]


class TestAlign:
    """Placing events onto character positions."""

    def test_events_land_on_their_positions(self) -> None:
        sentence = "我打算去公园。"
        timings = align(sentence, [chunk("我", 0, 100), chunk("打算", 100, 300)])

        assert timings == (
            CharTiming(start=0, end=1, start_ms=0, end_ms=100),
            CharTiming(start=1, end=3, start_ms=100, end_ms=400),
        )

    def test_ticks_become_milliseconds(self) -> None:
        timings = align(
            "好", [SpokenChunk(text="好", offset_ticks=1_250_000, duration_ticks=3_750_000)]
        )

        assert timings[0].start_ms == 125
        assert timings[0].end_ms == 500

    def test_a_repeated_word_lands_on_both_positions(self) -> None:
        """The cursor is what makes this work: without it both events match the first 很."""
        timings = align(
            "很好很好", [chunk("很", 0, 100), chunk("好", 100, 100), chunk("很", 200, 100)]
        )

        assert [(timing.start, timing.end) for timing in timings] == [(0, 1), (1, 2), (2, 3)]

    def test_an_event_that_is_not_in_the_sentence_is_dropped(self) -> None:
        """A service may normalise what it speaks; one lost highlight beats shifting the rest."""
        timings = align(
            "我去公园。", [chunk("我", 0, 100), chunk("银行", 100, 200), chunk("去", 300, 100)]
        )

        # 去 стоит на позиции 1: 我=0, 去=1, 公=2, 园=3.
        assert [(timing.start, timing.end) for timing in timings] == [(0, 1), (1, 2)]

    def test_an_empty_event_is_ignored(self) -> None:
        assert align("我去。", [chunk("", 0, 100)]) == ()

    def test_no_events_give_no_timings(self) -> None:
        assert align("我去。", []) == ()


class TestMapToWords:
    """Spreading character timings over jieba's words."""

    def test_words_get_their_own_intervals(self) -> None:
        sentence = only_sentence("我打算去公园。")
        timings = align(
            sentence.text,
            [
                chunk("我", 0, 100),
                chunk("打算", 100, 300),
                chunk("去", 400, 100),
                chunk("公园", 500, 400),
            ],
        )

        mapped = map_to_words(sentence, timings)
        words = [word.text for word in sentence.words]

        assert words == ["我", "打算", "去", "公园", "。"]
        assert [(timing.start_ms, timing.end_ms) if timing else None for timing in mapped] == [
            (0, 100),
            (100, 400),
            (400, 500),
            (500, 900),
            None,
        ]

    def test_punctuation_is_never_highlighted(self) -> None:
        sentence = only_sentence("我去。")
        mapped = map_to_words(sentence, align(sentence.text, [chunk("我", 0, 100)]))

        assert mapped[-1] is None

    def test_one_event_covering_two_words_highlights_both(self) -> None:
        """Microsoft may report 公园 and 走走 as one stretch while jieba splits them."""
        sentence = only_sentence("公园走走。")
        wide = align(sentence.text, [chunk("公园走走", 0, 800)])

        mapped = map_to_words(sentence, wide)

        assert [word.text for word in sentence.words] == ["公园", "走走", "。"]
        assert mapped[0] == mapped[1]
        assert mapped[0] is not None
        assert (mapped[0].start_ms, mapped[0].end_ms) == (0, 800)

    def test_a_word_built_from_two_events_takes_their_union(self) -> None:
        """And the other way round: 银行 as two single-character events is one jieba word."""
        sentence = only_sentence("银行在哪儿？")
        split = align(sentence.text, [chunk("银", 0, 200), chunk("行", 200, 300)])

        mapped = map_to_words(sentence, split)

        assert sentence.words[0].text == "银行"
        assert mapped[0] is not None
        assert (mapped[0].start_ms, mapped[0].end_ms) == (0, 500)

    def test_words_after_a_space_keep_their_timings(self) -> None:
        """The segmenter drops whitespace, so word positions have to be searched for.

        Counting word lengths instead would shift every timing after the space.
        """
        sentence = only_sentence("我说 hello 你好。")
        timings = align(sentence.text, [chunk("我", 0, 100), chunk("你好", 900, 400)])

        mapped = map_to_words(sentence, timings)
        marked = [
            (word.text, (timing.start_ms, timing.end_ms))
            for word, timing in zip(sentence.words, mapped, strict=True)
            if timing is not None
        ]

        assert marked == [("我", (0, 100)), ("你好", (900, 1300))]

    def test_no_timings_leave_every_word_unmarked(self) -> None:
        sentence = only_sentence("我去公园。")

        assert all(timing is None for timing in map_to_words(sentence, []))
