"""Business logic of the accounts app."""

from typing import Any

from django.conf import settings as django_settings

from .exceptions import InvalidSettingValueError, UnknownSettingError
from .models import (
    DEFAULT_PAUSE_MODE,
    DEFAULT_REPEATS,
    MAX_REPEATS,
    MIN_REPEATS,
    PAUSE_MODES,
    User,
    UserSettings,
)

# Имя настройки в браузере -> поле модели. Названия разные намеренно: в CSS и JS
# уже прижились короткие (классы pinyin-off, tones-off), а поле модели честнее
# называется show_pinyin. Эта таблица — единственное место, где они встречаются.
BOOLEAN_SETTINGS = {
    "pinyin": "show_pinyin",
    "tones": "show_tones",
    "translation": "show_translation",
    "hints": "show_hints",
}

# Совпадают с переменными --reader-sm / --reader-md / --reader-lg в tokens.css.
FONT_SIZES = ("sm", "md", "lg")

# Настройки Shadowing. Их значения — не булевы, поэтому в BOOLEAN_SETTINGS им
# места нет, но храниться и восстанавливаться они должны тем же механизмом.
SHADOWING_SETTINGS = {
    "pauseMode": "pause_mode",
    "repeats": "repeats",
}


def get_user_settings(user: User) -> UserSettings:
    """Return the user's settings row, creating it on first use.

    Created on demand rather than by a signal on user creation: a signal would
    miss accounts that already existed before this model did, and it is one more
    invisible thing happening on every save.

    Args:
        user: An authenticated user.

    Returns:
        The saved settings.
    """
    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    return user_settings


def as_client_dict(user_settings: UserSettings | None) -> dict[str, Any]:
    """Flatten settings into the names the browser and the templates use.

    Args:
        user_settings: A saved row, or ``None`` for a guest.

    Returns:
        Every setting with a value — defaults when there is no row. Templates
        can then render the state without asking whether anyone is signed in.
        ``fontSize`` may be an empty string, meaning the size was never chosen.
    """
    if user_settings is None:
        defaults: dict[str, Any] = dict.fromkeys(BOOLEAN_SETTINGS, True)
        defaults["fontSize"] = ""
        defaults["language"] = django_settings.DEFAULT_TRANSLATION_LANGUAGE
        defaults["pauseMode"] = DEFAULT_PAUSE_MODE
        defaults["repeats"] = DEFAULT_REPEATS
        return defaults

    data: dict[str, Any] = {
        name: getattr(user_settings, field) for name, field in BOOLEAN_SETTINGS.items()
    }
    data["fontSize"] = user_settings.font_size
    data["language"] = user_settings.language or django_settings.DEFAULT_TRANSLATION_LANGUAGE
    data.update({name: getattr(user_settings, field) for name, field in SHADOWING_SETTINGS.items()})
    return data


def off_classes(client_settings: dict[str, Any]) -> str:
    """Return the CSS classes that switch parts of the reader off.

    The classes are "off" ones because everything is on by default, which keeps
    the markup clean. Building the string here rather than in the template is
    what lets the template stay plain output.

    Args:
        client_settings: The result of :func:`as_client_dict`.

    Returns:
        Space-separated class names, empty when everything is on.
    """
    return " ".join(f"{name}-off" for name in BOOLEAN_SETTINGS if not client_settings[name])


def update_user_setting(user: User, name: str, value: Any) -> None:
    """Validate one setting and save it.

    Nothing outside this function decides what a valid setting is, so the
    endpoint cannot be talked into writing a value the reader cannot render.

    Args:
        user: Whose settings to change.
        name: The browser-side name, as in :data:`BOOLEAN_SETTINGS`.
        value: The new value.

    Raises:
        UnknownSettingError: If there is no such setting.
        InvalidSettingValueError: If the value is not one this setting accepts.
    """
    if name in BOOLEAN_SETTINGS:
        if not isinstance(value, bool):
            raise InvalidSettingValueError(f"Настройка «{name}» принимает только true или false.")
        field = BOOLEAN_SETTINGS[name]

    elif name == "fontSize":
        if value not in FONT_SIZES:
            raise InvalidSettingValueError(f"Неизвестный размер шрифта: «{value}».")
        field = "font_size"

    elif name == "language":
        if value not in django_settings.TRANSLATION_LANGUAGES:
            raise InvalidSettingValueError(f"Неизвестный язык перевода: «{value}».")
        field = "language"

    elif name == "pauseMode":
        if value not in PAUSE_MODES:
            raise InvalidSettingValueError(f"Неизвестный режим паузы: «{value}».")
        field = SHADOWING_SETTINGS[name]

    elif name == "repeats":
        # isinstance(True, int) — истина, поэтому булев отсекаем отдельно:
        # иначе true записалось бы как один повтор.
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidSettingValueError("Число повторов должно быть целым.")
        if not MIN_REPEATS <= value <= MAX_REPEATS:
            raise InvalidSettingValueError(
                f"Повторов должно быть от {MIN_REPEATS} до {MAX_REPEATS}."
            )
        field = SHADOWING_SETTINGS[name]

    else:
        raise UnknownSettingError(f"Неизвестная настройка: «{name}».")

    user_settings = get_user_settings(user)
    setattr(user_settings, field, value)
    user_settings.save(update_fields=[field])
