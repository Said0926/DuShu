"""Exceptions raised by the translation app."""


class TranslationError(Exception):
    """A translation could not be produced.

    Views catch this and render the text without translations plus a readable
    message. Reading the chinese is still useful, so one failing service must
    not take the whole page down.
    """
