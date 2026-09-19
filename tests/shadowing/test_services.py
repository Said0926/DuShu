"""Tests for assembling the shadowing page."""

import pytest

from apps.chinese.services import process_text
from apps.shadowing.services import format_duration, speak_text

pytestmark = pytest.mark.django_db


class TestFormatDuration:
    """Lengths shown in the sentence list."""

    def test_seconds_are_two_digits(self) -> None:
        assert format_duration(4000) == "0:04"

    def test_minutes_are_split_off(self) -> None:
        assert format_duration(95_000) == "1:35"

    def test_it_rounds_to_the_nearest_second(self) -> None:
        assert format_duration(2208) == "0:02"

    def test_zero_is_not_a_special_case(self) -> None:
        assert format_duration(0) == "0:00"


class TestSpeakText:
    """Sentences paired with their audio and karaoke marks."""

    def test_every_sentence_comes_back_in_order(self) -> None:
        processed = process_text("我去。你好。")

        spoken = speak_text(processed)

        assert [sentence.text for sentence in spoken] == ["我去。", "你好。"]
        assert [sentence.number for sentence in spoken] == [1, 2]

    def test_words_are_paired_with_their_timings(self) -> None:
        spoken = speak_text(process_text("我去。"))

        words = spoken[0].words

        assert [item.word.text for item in words] == ["我", "去", "。"]
        assert words[0].timing is not None
        # Пунктуация не подсвечивается: у неё нет события от провайдера.
        assert words[-1].timing is None

    def test_each_sentence_gets_its_own_audio(self) -> None:
        spoken = speak_text(process_text("我去。你好。"))

        assert spoken[0].audio_url != spoken[1].audio_url
        assert spoken[0].audio_url.startswith("/media/")

    def test_duration_is_reported_both_ways(self) -> None:
        """The progress track needs milliseconds, the sentence list needs 0:04."""
        sentence = speak_text(process_text("我去。"))[0]

        assert sentence.duration_ms > 0
        assert sentence.duration_label == format_duration(sentence.duration_ms)

    def test_an_empty_text_gives_nothing(self) -> None:
        assert speak_text(process_text("")) == []
