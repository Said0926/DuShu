"""Tests for the library services."""

import pytest

from apps.accounts.models import User
from apps.chinese.exceptions import TextTooLongError
from apps.library.exceptions import EmptyTextError, InvalidTitleError
from apps.library.models import SavedText
from apps.library.services import (
    delete_text,
    get_owned_text,
    rename_text,
    save_text,
    visible_texts,
)

TEXT = "今天天气很好，我打算去公园走走。"


@pytest.fixture
def other_user(db: None) -> User:
    """Somebody else, for checking that texts do not leak between accounts."""
    return User.objects.create_user(email="other@example.com", password="pw-123456789")


@pytest.mark.django_db
def test_saving_creates_a_text_with_a_title(user: User) -> None:
    text, created = save_text(user, TEXT)

    assert created is True
    assert text.owner == user
    assert text.title == TEXT


@pytest.mark.django_db
def test_saving_the_same_text_twice_creates_one_entry(user: User) -> None:
    """Otherwise re-reading a text and pressing save again would litter the list."""
    save_text(user, TEXT)
    _, created = save_text(user, TEXT)

    assert created is False
    assert SavedText.objects.filter(owner=user).count() == 1


@pytest.mark.django_db
def test_the_same_text_can_be_saved_by_two_people(user: User, other_user: User) -> None:
    """The uniqueness is per owner: two people reading one article is normal."""
    save_text(user, TEXT)
    _, created = save_text(other_user, TEXT)

    assert created is True
    assert SavedText.objects.count() == 2


@pytest.mark.django_db
def test_saving_an_empty_text_is_refused(user: User) -> None:
    with pytest.raises(EmptyTextError):
        save_text(user, "   \n ")


@pytest.mark.django_db
def test_saving_an_overlong_text_is_refused(user: User, settings: pytest.FixtureRequest) -> None:
    settings.MAX_TEXT_LENGTH = 10

    with pytest.raises(TextTooLongError):
        save_text(user, "中" * 11)


@pytest.mark.django_db
def test_list_shows_only_your_own_texts(user: User, other_user: User) -> None:
    save_text(user, TEXT)
    save_text(other_user, "再见。")

    assert [text.owner for text in visible_texts(user)] == [user]


@pytest.mark.django_db
def test_getting_someone_elses_text_fails(user: User, other_user: User) -> None:
    """Ownership is enforced in the service, so no view can forget to check it."""
    text, _ = save_text(user, TEXT)

    with pytest.raises(SavedText.DoesNotExist):
        get_owned_text(other_user, text.pk)


@pytest.mark.django_db
def test_renaming_changes_the_title(user: User) -> None:
    text, _ = save_text(user, TEXT)

    rename_text(user, text.pk, "  Прогулка  ")

    assert SavedText.objects.get(pk=text.pk).title == "Прогулка"


@pytest.mark.django_db
def test_renaming_to_nothing_is_refused(user: User) -> None:
    text, _ = save_text(user, TEXT)

    with pytest.raises(InvalidTitleError):
        rename_text(user, text.pk, "   ")


@pytest.mark.django_db
def test_renaming_someone_elses_text_fails(user: User, other_user: User) -> None:
    text, _ = save_text(user, TEXT)

    with pytest.raises(SavedText.DoesNotExist):
        rename_text(other_user, text.pk, "чужое")


@pytest.mark.django_db
def test_deleting_removes_the_text(user: User) -> None:
    text, _ = save_text(user, TEXT)

    delete_text(user, text.pk)

    assert SavedText.objects.count() == 0


@pytest.mark.django_db
def test_deleting_someone_elses_text_fails(user: User, other_user: User) -> None:
    text, _ = save_text(user, TEXT)

    with pytest.raises(SavedText.DoesNotExist):
        delete_text(other_user, text.pk)

    assert SavedText.objects.count() == 1
