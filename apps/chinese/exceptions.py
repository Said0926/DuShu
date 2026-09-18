"""Exceptions raised by the text processing services."""


class TextTooLongError(ValueError):
    """The submitted text is longer than ``settings.MAX_TEXT_LENGTH``.

    Inherits from ``ValueError`` because that is what it is: a rejected input
    value. Views catch this specific class and turn it into a readable message
    instead of a 500 page.
    """
