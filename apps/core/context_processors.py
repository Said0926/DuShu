"""Context processors of the core app."""

from django.http import HttpRequest

from .limits import LimitState, text_limit_state


def quota(request: HttpRequest) -> dict[str, LimitState | None]:
    """Put the remaining text allowance into the header.

    Reads the counter with ``increment=False``. That is not an optimisation but
    the whole condition for doing this here at all: this runs on every page
    render, so a counting read would spend a visitor's entire hourly limit on
    browsing.

    Returns:
        ``{"quota": state}``, with ``None`` when rate limiting is switched off —
        the header then shows nothing rather than a made-up number.
    """
    return {"quota": text_limit_state(request)}
