"""Exceptions raised by the tts app."""


class TTSError(Exception):
    """Speech could not be produced.

    Views catch this and render the text with pinyin but without audio plus a
    readable message. The speech service here is an unofficial one, so it will
    occasionally be unavailable — and that must cost the reader the audio, not
    the page.
    """
