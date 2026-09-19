"""Tests for the speech providers.

Only the dummy one is tested here. The Edge provider talks to somebody else's
websocket, so a test of it would report the state of that service rather than of
our code; what our code does with its events is covered in test_alignment.py.
"""

import io
import wave

import pytest
from django.test import override_settings

from apps.chinese.services import process_text
from apps.tts.alignment import map_to_words
from apps.tts.exceptions import TTSError
from apps.tts.providers.dummy import MS_PER_CHARACTER, DummyTTSProvider
from apps.tts.services import get_provider


class TestDummyProvider:
    """Silence of the right length, with timings a player can follow."""

    def test_one_result_per_sentence_in_order(self) -> None:
        results = DummyTTSProvider().synthesize(["我去。", "你好。"], "any-voice")

        assert len(results) == 2
        assert results[0].timings[0].start == 0

    def test_empty_input_gives_empty_output(self) -> None:
        assert DummyTTSProvider().synthesize([], "any-voice") == []

    def test_the_audio_is_a_playable_wav_of_the_stated_length(self) -> None:
        synthesis = DummyTTSProvider().synthesize(["我去公园。"], "any-voice")[0]

        with wave.open(io.BytesIO(synthesis.audio)) as wav:
            length_ms = 1000 * wav.getnframes() // wav.getframerate()

        assert synthesis.extension == "wav"
        assert length_ms == synthesis.duration_ms

    def test_only_hanzi_get_timings(self) -> None:
        """Punctuation gets none, exactly as a real service gives it no boundary."""
        synthesis = DummyTTSProvider().synthesize(["我去。"], "any-voice")[0]

        assert len(synthesis.timings) == 2

    def test_timings_do_not_overlap_and_follow_the_text(self) -> None:
        synthesis = DummyTTSProvider().synthesize(["我打算去。"], "any-voice")[0]

        assert [timing.start for timing in synthesis.timings] == [0, 1, 2, 3]
        assert [timing.start_ms for timing in synthesis.timings] == [
            0,
            MS_PER_CHARACTER,
            2 * MS_PER_CHARACTER,
            3 * MS_PER_CHARACTER,
        ]

    def test_the_file_outlasts_the_speech(self) -> None:
        """A real synthesis ends in silence, and the progress bar must show the file."""
        synthesis = DummyTTSProvider().synthesize(["我去。"], "any-voice")[0]

        assert synthesis.duration_ms > synthesis.timings[-1].end_ms

    def test_its_output_maps_onto_words(self) -> None:
        """The dummy has to be good enough to develop the player against."""
        sentence = process_text("我打算去公园。").sentences[0]
        synthesis = DummyTTSProvider().synthesize([sentence.text], "any-voice")[0]

        mapped = map_to_words(sentence, synthesis.timings)

        assert all(timing is not None for timing in mapped[:-1])
        assert mapped[-1] is None


class TestGetProvider:
    """A misconfigured provider must not produce a 500."""

    def test_the_configured_provider_is_built(self) -> None:
        assert isinstance(get_provider(), DummyTTSProvider)

    @override_settings(TTS_PROVIDER="apps.tts.providers.nope.Missing")
    def test_bad_path_reports_a_readable_error(self) -> None:
        with pytest.raises(TTSError, match="TTS_PROVIDER"):
            get_provider()

    @override_settings(TTS_PROVIDER="apps.chinese.services.sentence_hash")
    def test_setting_pointing_at_something_that_is_not_a_provider(self) -> None:
        """The path imports fine but calling it does not give a provider."""
        with pytest.raises(TTSError, match="not a usable provider"):
            get_provider()


def test_tests_never_use_the_real_provider() -> None:
    """Guard against a test quietly depending on somebody else's websocket."""
    from django.conf import settings as django_settings

    assert "dummy" in django_settings.TTS_PROVIDER.lower()
