"""Tests for the caching speech service."""

from unittest.mock import Mock, patch

import pytest

from apps.chinese.services import process_text, sentence_hash
from apps.tts.exceptions import TTSError
from apps.tts.models import SentenceAudio
from apps.tts.providers.base import CharTiming, Synthesis
from apps.tts.services import (
    get_sentence_audio,
    has_cached_audio,
    word_timings,
)

VOICE = "zh-CN-XiaoxiaoNeural"


def fake_synthesis(timings: tuple[CharTiming, ...] = ()) -> Synthesis:
    """A result shaped like a provider's, with audio short enough to be cheap."""
    return Synthesis(audio=b"not-really-audio", extension="mp3", duration_ms=1000, timings=timings)


@pytest.mark.django_db
class TestCache:
    """Nothing is spoken twice."""

    def test_a_sentence_is_stored_with_its_timings(self) -> None:
        timing = CharTiming(start=0, end=1, start_ms=0, end_ms=250)
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis((timing,))]

        with patch("apps.tts.services.get_provider", return_value=provider):
            result = get_sentence_audio(["我去。"], VOICE)

        row = result["我去。"]

        assert row.source_hash == sentence_hash("我去。")
        assert row.voice == VOICE
        assert row.duration_ms == 1000
        assert row.timings == [{"start": 0, "end": 1, "start_ms": 0, "end_ms": 250}]
        assert row.audio.read() == b"not-really-audio"

    def test_a_second_call_never_reaches_the_provider(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["我去。"], VOICE)
            get_sentence_audio(["我去。"], VOICE)

        assert provider.synthesize.call_count == 1

    def test_only_the_missing_sentences_are_spoken(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["我去。"], VOICE)

            provider.synthesize.return_value = [fake_synthesis()]
            get_sentence_audio(["我去。", "你好。"], VOICE)

        assert provider.synthesize.call_args.args[0] == ["你好。"]

    def test_a_repeated_sentence_is_spoken_once(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            result = get_sentence_audio(["好。", "好。"], VOICE)

        assert provider.synthesize.call_args.args[0] == ["好。"]
        assert SentenceAudio.objects.count() == 1
        assert len(result) == 1

    def test_another_voice_is_a_separate_entry(self) -> None:
        """Otherwise switching the voice in settings would keep serving the old sound."""
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["我去。"], VOICE)
            get_sentence_audio(["我去。"], "zh-CN-YunxiNeural")

        assert SentenceAudio.objects.count() == 2

    def test_empty_input_asks_for_nothing(self) -> None:
        provider = Mock()

        with patch("apps.tts.services.get_provider", return_value=provider):
            assert get_sentence_audio([], VOICE) == {}

        provider.synthesize.assert_not_called()


@pytest.mark.django_db
class TestProviderContractViolations:
    """A provider that breaks its contract must not produce a 500."""

    def test_provider_returning_too_few_results(self) -> None:
        sloppy = Mock()
        sloppy.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=sloppy):
            with pytest.raises(TTSError, match="1 results"):
                get_sentence_audio(["一。", "二。"], VOICE)

    def test_provider_returning_too_many_results(self) -> None:
        sloppy = Mock()
        sloppy.synthesize.return_value = [fake_synthesis(), fake_synthesis(), fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=sloppy):
            with pytest.raises(TTSError):
                get_sentence_audio(["一。", "二。"], VOICE)

    def test_a_failing_provider_caches_nothing(self) -> None:
        angry = Mock()
        angry.synthesize.side_effect = TTSError("the service is down")

        with patch("apps.tts.services.get_provider", return_value=angry):
            with pytest.raises(TTSError):
                get_sentence_audio(["我去。"], VOICE)

        assert SentenceAudio.objects.count() == 0


@pytest.mark.django_db
class TestHasCachedAudio:
    """This is what lets a re-open skip the hourly limit."""

    def test_nothing_cached_means_it_is_not_free(self) -> None:
        assert has_cached_audio(["我去。"], VOICE) is False

    def test_a_fully_spoken_text_is_free_to_reopen(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis(), fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["一。", "二。"], VOICE)

        assert has_cached_audio(["一。", "二。"], VOICE) is True

    def test_one_missing_sentence_makes_the_whole_text_paid(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["一。"], VOICE)

        assert has_cached_audio(["一。", "二。"], VOICE) is False

    def test_another_voice_is_not_cached(self) -> None:
        provider = Mock()
        provider.synthesize.return_value = [fake_synthesis()]

        with patch("apps.tts.services.get_provider", return_value=provider):
            get_sentence_audio(["一。"], VOICE)

        assert has_cached_audio(["一。"], "zh-CN-YunxiNeural") is False

    def test_an_empty_text_costs_nothing(self) -> None:
        assert has_cached_audio([], VOICE) is True


@pytest.mark.django_db
def test_word_timings_are_recomputed_from_stored_positions() -> None:
    """Stored marks are character positions, so they survive a changed segmentation."""
    sentence = process_text("我打算去。").sentences[0]
    provider = Mock()
    provider.synthesize.return_value = [
        fake_synthesis(
            (
                CharTiming(start=0, end=1, start_ms=0, end_ms=100),
                CharTiming(start=1, end=3, start_ms=100, end_ms=400),
            )
        )
    ]

    with patch("apps.tts.services.get_provider", return_value=provider):
        row = get_sentence_audio([sentence.text], VOICE)[sentence.text]

    mapped = word_timings(sentence, row)

    assert [word.text for word in sentence.words] == ["我", "打算", "去", "。"]
    assert (mapped[0].start_ms, mapped[0].end_ms) == (0, 100)
    assert (mapped[1].start_ms, mapped[1].end_ms) == (100, 400)
    assert mapped[2] is None
    assert mapped[3] is None
