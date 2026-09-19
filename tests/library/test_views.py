"""Tests for the library pages and the save endpoint."""

import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.library.models import SavedText
from apps.library.services import save_text

TEXT = "今天天气很好，我打算去公园走走。"


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user(email="other@example.com", password="pw-123456789")


def _save(client: Client, content: str = TEXT):
    return client.post(
        reverse("library:save"),
        json.dumps({"content": content}),
        content_type="application/json",
    )


# --- сохранение ---


@pytest.mark.django_db
def test_saving_answers_with_the_title(client: Client, user: User) -> None:
    client.force_login(user)

    response = _save(client)

    assert response.status_code == 200
    assert response.json()["data"] == {"title": TEXT, "created": True}


@pytest.mark.django_db
def test_saving_twice_reports_that_it_was_already_there(client: Client, user: User) -> None:
    client.force_login(user)
    _save(client)

    response = _save(client)

    assert response.json()["data"]["created"] is False
    assert SavedText.objects.count() == 1


@pytest.mark.django_db
def test_a_guest_cannot_save(client: Client) -> None:
    response = _save(client)

    assert response.status_code == 403
    assert response.json()["error"] == "not_authenticated"


@pytest.mark.django_db
def test_saving_an_empty_text_is_refused(client: Client, user: User) -> None:
    client.force_login(user)

    response = _save(client, "  ")

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_text"


# --- список ---


@pytest.mark.django_db
def test_the_library_needs_a_login(client: Client) -> None:
    response = client.get(reverse("library:list"))

    assert response.status_code == 302
    assert reverse("account_login") in response.url


@pytest.mark.django_db
def test_the_list_shows_your_texts_and_not_other_peoples(
    client: Client, user: User, other_user: User
) -> None:
    save_text(user, TEXT)
    save_text(other_user, "这是别人的文章。")
    client.force_login(user)

    html = client.get(reverse("library:list")).content.decode()

    assert TEXT in html
    assert "这是别人的文章。" not in html


# --- переименование и удаление ---


@pytest.mark.django_db
def test_renaming_from_the_page(client: Client, user: User) -> None:
    text, _ = save_text(user, TEXT)
    client.force_login(user)

    client.post(reverse("library:rename", args=[text.pk]), {"title": "Прогулка"})

    assert SavedText.objects.get(pk=text.pk).title == "Прогулка"


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["rename", "delete"])
def test_touching_someone_elses_text_is_a_404(
    client: Client, user: User, other_user: User, action: str
) -> None:
    """404 and not 403: 403 would confirm the text exists and belongs to someone."""
    text, _ = save_text(user, TEXT)
    client.force_login(other_user)

    response = client.post(reverse(f"library:{action}", args=[text.pk]), {"title": "x"})

    assert response.status_code == 404
    assert SavedText.objects.filter(pk=text.pk).exists()


@pytest.mark.django_db
def test_deleting_asks_first(client: Client, user: User) -> None:
    """A GET only shows the confirmation; nothing is removed until a POST."""
    text, _ = save_text(user, TEXT)
    client.force_login(user)

    response = client.get(reverse("library:delete", args=[text.pk]))

    assert response.status_code == 200
    assert SavedText.objects.filter(pk=text.pk).exists()


@pytest.mark.django_db
def test_deleting_removes_the_text(client: Client, user: User) -> None:
    text, _ = save_text(user, TEXT)
    client.force_login(user)

    response = client.post(reverse("library:delete", args=[text.pk]))

    assert response.status_code == 302
    assert not SavedText.objects.filter(pk=text.pk).exists()


# --- связь со страницей «Чтение» ---


@pytest.mark.django_db
def test_the_reader_offers_a_guest_to_sign_in_instead_of_saving(client: Client) -> None:
    html = client.post(reverse("reader:read"), {"text": TEXT, "lang": "ru"}).content.decode()

    assert "Войдите, чтобы сохранить" in html
    assert reverse("library:save") not in html


@pytest.mark.django_db
def test_the_reader_shows_the_save_button_to_a_user(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.post(reverse("reader:read"), {"text": TEXT, "lang": "ru"}).content.decode()

    assert reverse("library:save") in html
    assert "Сохранить в библиотеку" in html


@pytest.mark.django_db
def test_opening_a_saved_text_shows_its_title_and_no_save_button(
    client: Client, user: User
) -> None:
    """The library posts the title and a "saved" flag as hidden fields.

    That is how the reader opens a saved text while knowing nothing about the
    library app — the two features stay independent of each other.
    """
    client.force_login(user)

    html = client.post(
        reverse("reader:read"),
        {"text": TEXT, "lang": "ru", "title": "Прогулка", "saved": "1"},
    ).content.decode()

    assert "Прогулка" in html
    assert "В библиотеке" in html
    assert "Сохранить в библиотеку" not in html
