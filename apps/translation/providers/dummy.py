"""A provider that does not translate anything."""

from .base import TranslationProvider


class DummyProvider(TranslationProvider):
    """Returns the input unchanged.

    Used in tests and for local work without an API key. It keeps the page and
    the caching layer fully exercised while costing nothing and needing no
    network — a failing test then points at our code, not at someone's service.
    """

    def translate(self, sentences: list[str], target_lang: str) -> list[str]:
        return list(sentences)
