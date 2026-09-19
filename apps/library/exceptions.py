"""Exceptions raised by the library app."""


class EmptyTextError(ValueError):
    """There is nothing to save.

    Saving an empty text would produce a row with an empty title that cannot be
    opened or recognised in the list.
    """


class InvalidTitleError(ValueError):
    """The new title is empty or longer than the column allows."""


class SystemCollectionError(ValueError):
    """Somebody tried to rename or delete a shared HSK collection.

    They belong to everyone, so one person renaming "HSK 3" would take the
    meaning of the level away from every other reader.
    """


class CollectionLimitError(ValueError):
    """The user already has as many collections as they are allowed."""


class InvalidStatusError(ValueError):
    """No such reading status."""
