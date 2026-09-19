"""Exceptions raised by the library app."""


class EmptyTextError(ValueError):
    """There is nothing to save.

    Saving an empty text would produce a row with an empty title that cannot be
    opened or recognised in the list.
    """


class InvalidTitleError(ValueError):
    """The new title is empty or longer than the column allows."""
