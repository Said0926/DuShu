"""Tests for the cache clearing command.

It matters more than it looks: silence cached by the dummy provider would go on
playing forever, because a cache hit never reaches the provider.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.core.management import call_command

from apps.tts.models import SentenceAudio
from apps.tts.providers.base import Synthesis

VOICE = "zh-CN-XiaoxiaoNeural"


def store(sentence: str, provider_name: str, voice: str = VOICE) -> SentenceAudio:
    """Put one entry in the cache as if a provider had produced it."""
    provider = Mock()
    provider.synthesize.return_value = [
        Synthesis(audio=b"sound", extension="mp3", duration_ms=1, timings=())
    ]
    type(provider).__name__ = provider_name

    from apps.tts.services import get_sentence_audio

    with patch("apps.tts.services.get_provider", return_value=provider):
        return get_sentence_audio([sentence], voice)[sentence]


@pytest.mark.django_db
def test_it_deletes_the_file_too(media_root: Path) -> None:
    """Django leaves files behind on delete, and an orphaned media/ is the result."""
    row = store("我去。", "DummyTTSProvider")
    path = Path(row.audio.path)

    assert path.exists()

    call_command("clear_audio_cache")

    assert SentenceAudio.objects.count() == 0
    assert not path.exists()


@pytest.mark.django_db
def test_it_can_delete_one_provider_only() -> None:
    store("我去。", "DummyTTSProvider")
    store("你好。", "EdgeTTSProvider")

    call_command("clear_audio_cache", provider="DummyTTSProvider")

    assert [row.provider for row in SentenceAudio.objects.all()] == ["EdgeTTSProvider"]


@pytest.mark.django_db
def test_it_can_delete_one_voice_only() -> None:
    store("我去。", "EdgeTTSProvider", voice=VOICE)
    store("我去。", "EdgeTTSProvider", voice="zh-CN-YunxiNeural")

    call_command("clear_audio_cache", voice=VOICE)

    assert [row.voice for row in SentenceAudio.objects.all()] == ["zh-CN-YunxiNeural"]
