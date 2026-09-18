"""Exceptions raised by the dictionary app."""


class UnknownLanguageError(ValueError):
    """The language code is not listed in ``settings.TRANSLATION_LANGUAGES``.

    Catches typos early. Without it a wrong code would quietly return no results
    and look like a missing word rather than a bug.
    """
