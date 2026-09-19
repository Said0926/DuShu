"""Rate limits for the views that cost something.

Both the decorator that enforces a limit and the counter that shows it in the
header read it from here. If the two disagreed on group, key or rate, the header
would display a number unrelated to the limit actually applied — and nothing
would report the mismatch.
"""

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil

from django.conf import settings
from django.http import HttpRequest
from django_ratelimit.core import get_usage

# Кто считается одним пользователем. "user_or_ip" — это id для авторизованного
# и адрес для гостя. За обратным прокси адрес нужно будет брать из доверенного
# заголовка, иначе все посетители окажутся одним IP прокси.
RATE_KEY = "user_or_ip"

# Группа — пространство имён счётчика. Разные группы считаются независимо,
# поэтому подсказки из словаря не расходуют лимит на обработку текста.
TEXT_GROUP = "reader:text"
LOOKUP_GROUP = "reader:lookup"
AUDIO_GROUP = "shadowing:audio"


@dataclass(frozen=True)
class LimitState:
    """How much of a limit is left right now."""

    limit: int
    used: int
    seconds_left: int

    @property
    def exceeded(self) -> bool:
        """Whether this request went past the limit.

        Strictly greater, not equal: the request that brings the count up to the
        limit is the last allowed one, not the first refused one.
        """
        return self.used > self.limit

    @property
    def remaining(self) -> int:
        """Requests still allowed. Never negative: below zero says nothing extra."""
        return max(self.limit - self.used, 0)

    @property
    def minutes_left(self) -> int:
        """Whole minutes until the window resets, at least one.

        Rounded up and floored at one, because "через 0 минут" reads like a bug
        even when it is technically true.
        """
        return max(1, ceil(self.seconds_left / 60))


def text_rate(group: str, request: HttpRequest) -> str:
    """How many texts this visitor may process per hour.

    A callable rather than a constant because guests and signed-in users get
    different numbers. Two decorators with two rates would not work: the
    counters are independent, so one visitor would have to exhaust both.
    """
    if request.user.is_authenticated:
        return settings.RATELIMIT_TEXT_USER
    return settings.RATELIMIT_TEXT_GUEST


def audio_rate(group: str, request: HttpRequest) -> str:
    """How many texts this visitor may have spoken per hour."""
    if request.user.is_authenticated:
        return settings.RATELIMIT_AUDIO_USER
    return settings.RATELIMIT_AUDIO_GUEST


def lookup_rate(group: str, request: HttpRequest) -> str:
    """How many dictionary tooltips this visitor may ask for."""
    if request.user.is_authenticated:
        return settings.RATELIMIT_LOOKUP_USER
    return settings.RATELIMIT_LOOKUP_GUEST


# Ставка — это функция, а не строка: у гостя и у авторизованного числа разные.
RateFunction = Callable[[str, HttpRequest], str]


def _usage(
    request: HttpRequest,
    group: str,
    rate: RateFunction,
    *,
    increment: bool,
) -> LimitState | None:
    """Read one counter, optionally spending it.

    Group, key and rate always travel together: a counter read with a different
    rate than it was written with would show a number unrelated to the limit in
    force, and nothing would report the mismatch.
    """
    usage = get_usage(request, group=group, key=RATE_KEY, rate=rate, increment=increment)

    if usage is None:
        return None

    return LimitState(limit=usage["limit"], used=usage["count"], seconds_left=usage["time_left"])


def consume_text_limit(request: HttpRequest) -> LimitState | None:
    """Count one paid text processing against the limit.

    Called from the view rather than from a decorator, because only the view
    knows whether this request will actually cost anything: a text whose
    translations are already cached is free to re-read, and counting it would
    make the library useless — thirty reopenings an hour and nothing more.

    The trade-off is that a free re-read is not counted at all, so repeatedly
    reopening a cached text costs CPU without limit. That is deliberate: this
    limit guards the translation budget, and a real deployment bounds raw
    request rate at the proxy.

    Args:
        request: The current request.

    Returns:
        The state after counting, or ``None`` if rate limiting is switched off.
    """
    return _usage(request, TEXT_GROUP, text_rate, increment=True)


def text_limit_state(request: HttpRequest) -> LimitState | None:
    """Read the text limit without spending it.

    ``increment=False`` is what makes this safe to call while rendering a page:
    showing the counter must not consume the thing it counts.

    Args:
        request: The current request.

    Returns:
        The current state, or ``None`` if rate limiting is switched off.
    """
    return _usage(request, TEXT_GROUP, text_rate, increment=False)


def consume_audio_limit(request: HttpRequest) -> LimitState | None:
    """Count one text being spoken against the limit.

    Called from the view for the same reason the text limit is: only the view
    knows whether this request costs anything. A text whose audio is fully
    cached reaches no service at all, and counting it would make the library
    useless.

    Unlike the text limit, this one guards no money — the speech provider is
    free. It guards our standing with an endpoint nobody promised us, and the
    processor time synthesis costs.

    Args:
        request: The current request.

    Returns:
        The state after counting, or ``None`` if rate limiting is switched off.
    """
    return _usage(request, AUDIO_GROUP, audio_rate, increment=True)


def user_audio_limit() -> int:
    """The per-hour speech limit a signed-in user gets, as a plain number."""
    count, _, _ = settings.RATELIMIT_AUDIO_USER.partition("/")
    return int(count)


def user_text_limit() -> int:
    """The per-hour text limit a signed-in user gets, as a plain number.

    Used by the page a guest sees when their own limit runs out, to name the
    number registration would give them.
    """
    count, _, _ = settings.RATELIMIT_TEXT_USER.partition("/")
    return int(count)
