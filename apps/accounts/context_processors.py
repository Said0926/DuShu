"""Context processors of the accounts app."""

from typing import Any

from django.http import HttpRequest

from .models import DEFAULT_FONT_SIZE
from .services import as_client_dict, get_user_settings, off_classes


def reading_settings(request: HttpRequest) -> dict[str, Any]:
    """Put the reading preferences into every template.

    Always returns a full set of values: the defaults for a guest, the saved
    ones for a signed-in user. Two things follow from that. Templates render
    the current state without asking who is looking, and a signed-in user never
    sees the page appear with defaults and then jump to their own settings —
    which is what a localStorage-only setup cannot avoid, because the browser
    only learns the values after the HTML has already been painted.
    """
    user = getattr(request, "user", None)
    on_server = bool(user is not None and user.is_authenticated)

    settings = as_client_dict(get_user_settings(user) if on_server else None)

    return {
        "reading_settings": settings,
        # Готовая строка классов для контейнера «Чтения» (и, позже, Shadowing).
        "reading_off_classes": off_classes(settings),
        # Какой сегмент подсвечен в переключателе размера. Отличается от
        # settings["fontSize"]: там пустая строка, пока размер не выбирали,
        # а показать в этом случае надо всё равно средний.
        "reading_font_size": settings["fontSize"] or DEFAULT_FONT_SIZE,
        # По этому флагу шаблон решает, отдавать ли настройки в JSON, а JS —
        # сохранять их на сервер или в localStorage.
        "settings_on_server": on_server,
    }
