"""Tests for the reading settings: model, services and the save endpoint."""

import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.exceptions import InvalidSettingValueError, UnknownSettingError
from apps.accounts.models import User, UserSettings
from apps.accounts.services import (
    as_client_dict,
    get_user_settings,
    off_classes,
    update_user_setting,
)

# --- сервисы ---


@pytest.mark.django_db
def test_settings_row_is_created_on_first_use(user: User) -> None:
    """No signal creates it, so the first read has to."""
    assert UserSettings.objects.count() == 0

    get_user_settings(user)

    assert UserSettings.objects.count() == 1


@pytest.mark.django_db
def test_reading_settings_twice_does_not_create_a_second_row(user: User) -> None:
    get_user_settings(user)
    get_user_settings(user)

    assert UserSettings.objects.count() == 1


def test_guest_gets_every_setting_with_a_default() -> None:
    """Templates render the same way for everyone, so no value may be missing."""
    data = as_client_dict(None)

    assert data["pinyin"] is True
    assert data["tones"] is True
    assert data["translation"] is True
    assert data["hints"] is True
    assert data["language"] == "ru"
    # Пустая строка, а не "md": размер не выбирали, и на узком экране должен
    # действовать уменьшенный кегль из медиазапроса.
    assert data["fontSize"] == ""


@pytest.mark.django_db
def test_empty_language_falls_back_to_the_default(user: User) -> None:
    """The column stays empty so that changing the default needs no migration."""
    user_settings = get_user_settings(user)

    assert user_settings.language == ""
    assert as_client_dict(user_settings)["language"] == "ru"


def test_off_classes_lists_only_what_is_switched_off() -> None:
    data = as_client_dict(None)
    assert off_classes(data) == ""

    data["pinyin"] = False
    data["hints"] = False

    assert off_classes(data) == "pinyin-off hints-off"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "value", "field"),
    [
        ("pinyin", False, "show_pinyin"),
        ("tones", False, "show_tones"),
        ("translation", False, "show_translation"),
        ("hints", False, "show_hints"),
        ("fontSize", "lg", "font_size"),
        ("language", "en", "language"),
    ],
)
def test_update_saves_the_setting(user: User, name: str, value: object, field: str) -> None:
    update_user_setting(user, name, value)

    assert getattr(get_user_settings(user), field) == value


@pytest.mark.django_db
def test_update_rejects_an_unknown_setting(user: User) -> None:
    with pytest.raises(UnknownSettingError):
        update_user_setting(user, "favourite-colour", "red")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("pinyin", "yes"),  # строка вместо булева значения
        ("fontSize", "huge"),
        ("language", "kz"),  # нет в TRANSLATION_LANGUAGES
    ],
)
def test_update_rejects_a_value_the_reader_cannot_render(
    user: User, name: str, value: object
) -> None:
    with pytest.raises(InvalidSettingValueError):
        update_user_setting(user, name, value)


# --- endpoint ---


def _save(client: Client, name: str, value: object):
    return client.post(
        reverse("accounts:settings"),
        json.dumps({"name": name, "value": value}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_endpoint_saves_a_setting(client: Client, user: User) -> None:
    client.force_login(user)

    response = _save(client, "pinyin", False)

    assert response.status_code == 200
    assert get_user_settings(user).show_pinyin is False


@pytest.mark.django_db
def test_endpoint_refuses_a_guest_in_json(client: Client) -> None:
    """Not a redirect to the login page: fetch() cannot read a page of HTML."""
    response = _save(client, "pinyin", False)

    assert response.status_code == 403
    assert response.json()["error"] == "not_authenticated"


@pytest.mark.django_db
def test_endpoint_rejects_a_broken_body(client: Client, user: User) -> None:
    client.force_login(user)

    response = client.post(
        reverse("accounts:settings"), "not json at all", content_type="application/json"
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_json"


@pytest.mark.django_db
def test_endpoint_rejects_an_unknown_setting(client: Client, user: User) -> None:
    client.force_login(user)

    response = _save(client, "favourite-colour", "red")

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_setting"


# --- отрисовка на сервере ---


@pytest.mark.django_db
def test_reader_renders_the_saved_settings(client: Client, user: User) -> None:
    """The point of storing them server-side: the page arrives already correct.

    With localStorage alone the browser learns the values only after the HTML is
    painted, so the reader visibly jumps from defaults to the user's settings.
    """
    update_user_setting(user, "pinyin", False)
    update_user_setting(user, "fontSize", "lg")
    client.force_login(user)

    html = client.post(reverse("reader:read"), {"text": "你好。", "lang": "ru"}).content.decode()

    assert "pinyin-off" in html
    assert 'data-size="lg"' in html
    assert 'id="user-settings"' in html


@pytest.mark.django_db
def test_reader_for_a_guest_carries_no_server_settings(client: Client) -> None:
    html = client.post(reverse("reader:read"), {"text": "你好。", "lang": "ru"}).content.decode()

    assert "pinyin-off" not in html
    assert "data-size=" not in html
    assert 'id="user-settings"' not in html
