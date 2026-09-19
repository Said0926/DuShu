"""Business logic of the library app.

Every function takes the owner explicitly and filters by them. Ownership is
therefore enforced here, in one place, rather than in each view — a view that
forgets the check cannot reach someone else's text at all.
"""

from django.conf import settings
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.chinese.exceptions import TextTooLongError

from .exceptions import EmptyTextError, InvalidTitleError
from .models import TITLE_LENGTH, SavedText, content_hash, make_title


def list_texts(owner: User) -> QuerySet[SavedText]:
    """Return the owner's texts, newest first."""
    return SavedText.objects.filter(owner=owner)


def get_text(owner: User, pk: int) -> SavedText:
    """Return one text belonging to this owner.

    Args:
        owner: Who is asking.
        pk: Which text.

    Returns:
        The text.

    Raises:
        SavedText.DoesNotExist: If there is no such text *of this owner*. Views
            turn this into a 404 rather than a 403: 403 would confirm that the
            text exists and belongs to somebody else.
    """
    return SavedText.objects.get(pk=pk, owner=owner)


def save_text(owner: User, content: str) -> tuple[SavedText, bool]:
    """Save a text to the owner's library, or find the one already there.

    Args:
        owner: Who is saving.
        content: The text as it was pasted.

    Returns:
        A pair of (text, created). ``created`` is ``False`` when this exact text
        was already saved, which is what lets the button say so instead of
        quietly making a second copy.

    Raises:
        EmptyTextError: If the text is blank.
        TextTooLongError: If it is longer than ``settings.MAX_TEXT_LENGTH``.
    """
    content = content.strip()

    if not content:
        raise EmptyTextError("Нечего сохранять: текст пустой.")

    if len(content) > settings.MAX_TEXT_LENGTH:
        raise TextTooLongError(
            f"Слишком длинный текст: {len(content)} символов, максимум {settings.MAX_TEXT_LENGTH}."
        )

    # get_or_create по отпечатку, а не по самому тексту: сравнивать хэши дешевле,
    # и ровно по этой паре полей стоит ограничение уникальности в базе.
    return SavedText.objects.get_or_create(
        owner=owner,
        content_hash=content_hash(content),
        defaults={"content": content, "title": make_title(content)},
    )


def rename_text(owner: User, pk: int, title: str) -> SavedText:
    """Give a saved text a new title.

    Args:
        owner: Who is renaming.
        pk: Which text.
        title: The new title.

    Returns:
        The updated text.

    Raises:
        SavedText.DoesNotExist: If the owner has no such text.
        InvalidTitleError: If the title is blank or too long.
    """
    title = title.strip()

    if not title:
        raise InvalidTitleError("Название не может быть пустым.")

    if len(title) > TITLE_LENGTH + 1:
        raise InvalidTitleError(f"Название длиннее {TITLE_LENGTH + 1} символов.")

    text = get_text(owner, pk)
    text.title = title
    text.save(update_fields=["title"])
    return text


def delete_text(owner: User, pk: int) -> None:
    """Delete one of the owner's texts.

    Raises:
        SavedText.DoesNotExist: If the owner has no such text.
    """
    get_text(owner, pk).delete()
