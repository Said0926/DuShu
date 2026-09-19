"""Tests for collections, moving texts between them and reading progress."""

import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.library.exceptions import (
    CollectionLimitError,
    InvalidStatusError,
    InvalidTitleError,
    SystemCollectionError,
)
from apps.library.models import Collection, ReadingProgress, SavedText
from apps.library.services import (
    create_collection,
    delete_collection,
    library_groups,
    move_text,
    rename_collection,
    save_text,
    set_status,
)

TEXT = "今天天气很好，我打算去公园走走。"


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user(email="other@example.com", password="pw-123456789")


@pytest.fixture
def hsk1(db: None) -> Collection:
    """The shared HSK 1 collection, created by the data migration."""
    return Collection.objects.get(owner=None, hsk_level=1)


# --- общие подборки ---


@pytest.mark.django_db
def test_the_five_hsk_levels_exist_for_everyone(user: User, other_user: User) -> None:
    """They are reference data created by a migration, not per-user copies."""
    assert Collection.objects.filter(owner=None).count() == 5

    for person in (user, other_user):
        titles = [group.title for group in library_groups(person)]
        assert titles[:5] == ["HSK 1", "HSK 2", "HSK 3", "HSK 4", "HSK 5"]


@pytest.mark.django_db
def test_a_shared_collection_cannot_be_renamed(user: User, hsk1: Collection) -> None:
    """One person renaming "HSK 1" would take the level away from every reader."""
    with pytest.raises(SystemCollectionError):
        rename_collection(user, hsk1.pk, "моё")

    assert Collection.objects.get(pk=hsk1.pk).title == "HSK 1"


@pytest.mark.django_db
def test_a_shared_collection_cannot_be_deleted(user: User, hsk1: Collection) -> None:
    with pytest.raises(SystemCollectionError):
        delete_collection(user, hsk1.pk)

    assert Collection.objects.filter(pk=hsk1.pk).exists()


# --- свои подборки ---


@pytest.mark.django_db
def test_creating_and_renaming_a_collection(user: User) -> None:
    collection = create_collection(user, "  Новости  ")

    assert collection.title == "Новости"

    rename_collection(user, collection.pk, "Газеты")

    assert Collection.objects.get(pk=collection.pk).title == "Газеты"


@pytest.mark.django_db
def test_two_collections_cannot_share_a_name(user: User) -> None:
    create_collection(user, "Новости")

    with pytest.raises(InvalidTitleError):
        create_collection(user, "Новости")


@pytest.mark.django_db
def test_two_people_can_use_the_same_name(user: User, other_user: User) -> None:
    create_collection(user, "Новости")
    create_collection(other_user, "Новости")

    assert Collection.objects.filter(title="Новости").count() == 2


@pytest.mark.django_db
def test_there_is_a_limit_on_collections(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Not to save space — to keep the list findable."""
    monkeypatch.setattr("apps.library.services.MAX_COLLECTIONS_PER_USER", 2)

    create_collection(user, "Раз")
    create_collection(user, "Два")

    with pytest.raises(CollectionLimitError):
        create_collection(user, "Три")


@pytest.mark.django_db
def test_deleting_a_collection_keeps_its_texts(user: User) -> None:
    """Losing a month of reading as a side effect of tidying folders would be cruel."""
    collection = create_collection(user, "Новости")
    text, _ = save_text(user, TEXT)
    move_text(user, text.pk, collection.pk)

    delete_collection(user, collection.pk)

    text.refresh_from_db()
    assert SavedText.objects.filter(pk=text.pk).exists()
    assert text.collection_id is None


@pytest.mark.django_db
def test_you_cannot_touch_someone_elses_collection(user: User, other_user: User) -> None:
    collection = create_collection(user, "Новости")

    with pytest.raises(Collection.DoesNotExist):
        rename_collection(other_user, collection.pk, "чужое")


# --- перемещение ---


@pytest.mark.django_db
def test_a_personal_text_can_go_into_a_shared_level(user: User, hsk1: Collection) -> None:
    """The collection is shared, the text inside it is not.

    This is how a reader files their own texts by level: only they see their
    text in HSK 1, because the text still belongs to them.
    """
    text, _ = save_text(user, TEXT)

    move_text(user, text.pk, hsk1.pk)

    text.refresh_from_db()
    assert text.collection_id == hsk1.pk
    assert text.owner_id == user.pk


@pytest.mark.django_db
def test_someone_elses_text_is_not_visible_in_a_shared_level(
    user: User, other_user: User, hsk1: Collection
) -> None:
    text, _ = save_text(user, TEXT)
    move_text(user, text.pk, hsk1.pk)

    groups = {group.title: group for group in library_groups(other_user)}

    assert groups["HSK 1"].total == 0


@pytest.mark.django_db
def test_moving_a_text_out_of_a_collection(user: User) -> None:
    collection = create_collection(user, "Новости")
    text, _ = save_text(user, TEXT)
    move_text(user, text.pk, collection.pk)

    move_text(user, text.pk, None)

    text.refresh_from_db()
    assert text.collection_id is None


@pytest.mark.django_db
def test_you_cannot_move_someone_elses_text(user: User, other_user: User) -> None:
    text, _ = save_text(user, TEXT)

    with pytest.raises(SavedText.DoesNotExist):
        move_text(other_user, text.pk, None)


# --- статусы ---


@pytest.mark.django_db
def test_a_text_starts_unread_without_a_row(user: User) -> None:
    """The missing row is the "not started" state, which keeps the table small."""
    save_text(user, TEXT)

    groups = {group.title: group for group in library_groups(user)}

    assert ReadingProgress.objects.count() == 0
    assert groups["Без подборки"].rows[0].status == ReadingProgress.Status.NEW


@pytest.mark.django_db
def test_setting_and_changing_a_status(user: User) -> None:
    text, _ = save_text(user, TEXT)

    set_status(user, text.pk, ReadingProgress.Status.READING)
    set_status(user, text.pk, ReadingProgress.Status.DONE)

    assert ReadingProgress.objects.count() == 1
    assert ReadingProgress.objects.get().status == ReadingProgress.Status.DONE


@pytest.mark.django_db
def test_an_unknown_status_is_refused(user: User) -> None:
    text, _ = save_text(user, TEXT)

    with pytest.raises(InvalidStatusError):
        set_status(user, text.pk, "почти")


@pytest.mark.django_db
def test_two_people_have_their_own_progress_on_one_text(user: User, other_user: User) -> None:
    """The reason progress is a separate model: a shared text is one row for all."""
    text, _ = save_text(user, TEXT)
    SavedText.objects.filter(pk=text.pk).update(owner=None)

    set_status(user, text.pk, ReadingProgress.Status.DONE)
    set_status(other_user, text.pk, ReadingProgress.Status.READING)

    assert ReadingProgress.objects.count() == 2


@pytest.mark.django_db
def test_the_done_count_is_shown_per_collection(user: User) -> None:
    collection = create_collection(user, "Новости")
    first, _ = save_text(user, TEXT)
    second, _ = save_text(user, "她喜欢喝茶。")
    move_text(user, first.pk, collection.pk)
    move_text(user, second.pk, collection.pk)
    set_status(user, first.pk, ReadingProgress.Status.DONE)

    groups = {group.title: group for group in library_groups(user)}

    assert groups["Новости"].total == 2
    assert groups["Новости"].done == 1


# --- endpoints ---


@pytest.mark.django_db
def test_status_endpoint_saves(client: Client, user: User) -> None:
    text, _ = save_text(user, TEXT)
    client.force_login(user)

    response = client.post(
        reverse("library:status", args=[text.pk]),
        json.dumps({"status": "done"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert ReadingProgress.objects.get().status == ReadingProgress.Status.DONE


@pytest.mark.django_db
def test_status_endpoint_refuses_a_guest(client: Client, user: User) -> None:
    text, _ = save_text(user, TEXT)

    response = client.post(
        reverse("library:status", args=[text.pk]),
        json.dumps({"status": "done"}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_status_endpoint_hides_other_peoples_texts(
    client: Client, user: User, other_user: User
) -> None:
    text, _ = save_text(user, TEXT)
    client.force_login(other_user)

    response = client.post(
        reverse("library:status", args=[text.pk]),
        json.dumps({"status": "done"}),
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_move_endpoint_accepts_an_empty_choice(client: Client, user: User) -> None:
    """The empty option in the select means "no collection", not a bad request."""
    collection = create_collection(user, "Новости")
    text, _ = save_text(user, TEXT)
    move_text(user, text.pk, collection.pk)
    client.force_login(user)

    client.post(reverse("library:move", args=[text.pk]), {"collection": ""})

    text.refresh_from_db()
    assert text.collection_id is None


@pytest.mark.django_db
def test_the_page_shows_levels_and_a_creation_form(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.get(reverse("library:list")).content.decode()

    assert "HSK 1" in html
    assert "HSK 5" in html
    assert reverse("library:collection-create") in html


@pytest.mark.django_db
def test_the_reader_shows_the_status_control_for_a_library_text(client: Client, user: User) -> None:
    """The library posts the id and the status as hidden fields.

    That is what lets the reader render the same control while importing
    nothing from the library app — the labels arrive through a context
    processor, the endpoint through a URL name.
    """
    text, _ = save_text(user, TEXT)
    client.force_login(user)

    html = client.post(
        reverse("reader:read"),
        {
            "text": TEXT,
            "lang": "ru",
            "title": text.title,
            "saved": "1",
            "saved_id": str(text.pk),
            "status": "reading",
        },
    ).content.decode()

    assert reverse("library:status", args=[text.pk]) in html
    assert "Читается" in html


@pytest.mark.django_db
def test_the_reader_has_no_status_control_for_an_unsaved_text(client: Client, user: User) -> None:
    client.force_login(user)

    html = client.post(reverse("reader:read"), {"text": TEXT, "lang": "ru"}).content.decode()

    assert "status-control" not in html
