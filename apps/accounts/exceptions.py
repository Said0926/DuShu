"""Exceptions raised by the accounts app."""


class UnknownSettingError(ValueError):
    """No such setting exists.

    Means the browser sent a name the server does not know — a bug in our own
    JavaScript, or someone poking the endpoint by hand. Either way the answer
    is the same: refuse, do not guess.
    """


class InvalidSettingValueError(ValueError):
    """The setting exists, but the value is not one it accepts."""
