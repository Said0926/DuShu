"""Business logic of the library app.

Two rules are enforced here rather than in the views, so that a view cannot
reach past them by forgetting a check:

- **visibility** — a user sees their own rows plus the shared ones, which are
  the rows with no owner;
- **ownership** — only the owner may change a row, and shared rows may not be
  changed by anyone through the site.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.chinese.exceptions import TextTooLongError

from .exceptions import (
    CollectionLimitError,
    EmptyTextError,
    InvalidStatusError,
    InvalidTitleError,
    SystemCollectionError,
)
from .models import (
    COLLECTION_TITLE_LENGTH,
    MAX_COLLECTIONS_PER_USER,
    TITLE_LENGTH,
    Collection,
    ReadingProgress,
    SavedText,
    content_hash,
    make_title,
)

NO_COLLECTION_TITLE = "Без подборки"


# --- тексты ---


def visible_texts(user: User) -> QuerySet[SavedText]:
    """Return the texts this user may read: their own and the shared ones."""
    return SavedText.objects.filter(Q(owner=user) | Q(owner__isnull=True))


def get_visible_text(user: User, pk: int) -> SavedText:
    """Return one text this user may read.

    Raises:
        SavedText.DoesNotExist: If there is no such text they may see. Views turn
            this into a 404 rather than a 403: 403 would confirm the text exists.
    """
    return visible_texts(user).get(pk=pk)


def get_owned_text(owner: User, pk: int) -> SavedText:
    """Return one text this user may change.

    Shared catalog texts are deliberately excluded: they are the same row for
    everybody, so renaming or deleting one would change it for every reader.

    Raises:
        SavedText.DoesNotExist: If the user does not own such a text.
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

    Raises:
        SavedText.DoesNotExist: If the user does not own such a text.
        InvalidTitleError: If the title is blank or too long.
    """
    title = _clean_title(title, TITLE_LENGTH + 1)

    text = get_owned_text(owner, pk)
    text.title = title
    text.save(update_fields=["title"])
    return text


def delete_text(owner: User, pk: int) -> None:
    """Delete one of the owner's texts.

    Raises:
        SavedText.DoesNotExist: If the user does not own such a text.
    """
    get_owned_text(owner, pk).delete()


def move_text(owner: User, pk: int, collection_pk: int | None) -> SavedText:
    """Put one of the owner's texts into a collection, or take it out of one.

    The collection may be a shared HSK level. That is not a mistake: the
    collection is shared, but the text inside it still belongs to one person, so
    only they see it there. This is how a user files their own texts by level.

    Args:
        owner: Who is moving.
        pk: Which text.
        collection_pk: Target collection, or ``None`` for "no collection".

    Returns:
        The moved text.

    Raises:
        SavedText.DoesNotExist: If the user does not own such a text.
        Collection.DoesNotExist: If they cannot see such a collection.
    """
    text = get_owned_text(owner, pk)

    if collection_pk is None:
        text.collection = None
    else:
        text.collection = visible_collections(owner).get(pk=collection_pk)

    text.save(update_fields=["collection"])
    return text


# --- подборки ---


def visible_collections(user: User) -> QuerySet[Collection]:
    """Return the collections this user sees: the shared HSK ones and their own."""
    return Collection.objects.filter(Q(owner=user) | Q(owner__isnull=True))


def get_owned_collection(owner: User, pk: int) -> Collection:
    """Return a collection this user may change.

    Raises:
        Collection.DoesNotExist: If there is no such collection they can see.
        SystemCollectionError: If it is a shared one.
    """
    collection = visible_collections(owner).get(pk=pk)

    if collection.is_system:
        raise SystemCollectionError("Подборки HSK общие, их нельзя менять.")

    return collection


def create_collection(owner: User, title: str) -> Collection:
    """Create a personal collection.

    Raises:
        InvalidTitleError: If the title is blank, too long or already used.
        CollectionLimitError: If the user is at the limit.
    """
    title = _clean_title(title, COLLECTION_TITLE_LENGTH)

    if Collection.objects.filter(owner=owner).count() >= MAX_COLLECTIONS_PER_USER:
        raise CollectionLimitError(f"Больше {MAX_COLLECTIONS_PER_USER} подборок завести нельзя.")

    if Collection.objects.filter(owner=owner, title=title).exists():
        raise InvalidTitleError("Подборка с таким названием уже есть.")

    return Collection.objects.create(owner=owner, title=title)


def rename_collection(owner: User, pk: int, title: str) -> Collection:
    """Rename a personal collection.

    Raises:
        Collection.DoesNotExist: If the user has no such collection.
        SystemCollectionError: If it is a shared HSK one.
        InvalidTitleError: If the title is blank, too long or already used.
    """
    title = _clean_title(title, COLLECTION_TITLE_LENGTH)
    collection = get_owned_collection(owner, pk)

    if Collection.objects.filter(owner=owner, title=title).exclude(pk=pk).exists():
        raise InvalidTitleError("Подборка с таким названием уже есть.")

    collection.title = title
    collection.save(update_fields=["title"])
    return collection


def delete_collection(owner: User, pk: int) -> None:
    """Delete a personal collection.

    The texts inside survive and end up with no collection: losing a month of
    saved reading as a side effect of tidying up folders would be a nasty
    surprise. The database does this itself — the link is ``SET_NULL``.

    Raises:
        Collection.DoesNotExist: If the user has no such collection.
        SystemCollectionError: If it is a shared HSK one.
    """
    get_owned_collection(owner, pk).delete()


# --- прогресс чтения ---


def set_status(user: User, text_pk: int, status: str) -> ReadingProgress:
    """Record how far this user got with a text.

    Args:
        user: Whose progress.
        text_pk: Any text they can see, shared ones included.
        status: One of ``ReadingProgress.Status``.

    Returns:
        The saved progress row.

    Raises:
        SavedText.DoesNotExist: If they cannot see such a text.
        InvalidStatusError: If the status is not one of the known ones.
    """
    if status not in ReadingProgress.Status.values:
        raise InvalidStatusError(f"Неизвестный статус: «{status}».")

    text = get_visible_text(user, text_pk)

    progress, _ = ReadingProgress.objects.update_or_create(
        user=user,
        text=text,
        defaults={"status": status},
    )
    return progress


def statuses_for(user: User, texts: list[SavedText]) -> dict[int, str]:
    """Return {text id: status} for the given texts, in one query.

    Texts the user never touched are simply absent from the result: the missing
    row *is* the "not started" state, which is why the table stays proportional
    to what people did rather than to texts times users.
    """
    rows = ReadingProgress.objects.filter(user=user, text__in=texts).values_list(
        "text_id", "status"
    )
    return dict(rows)


# --- сборка страницы ---


@dataclass(frozen=True)
class TextRow:
    """One text in the library, with this user's status for it."""

    text: SavedText
    status: str

    @property
    def is_shared(self) -> bool:
        """Whether this is a catalog text, which the reader may not edit."""
        return self.text.owner_id is None


@dataclass(frozen=True)
class Group:
    """One collapsible group on the library page."""

    collection: Collection | None
    title: str
    is_system: bool
    rows: list[TextRow]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def done(self) -> int:
        return sum(1 for row in self.rows if row.status == ReadingProgress.Status.DONE)


def library_groups(user: User) -> list[Group]:
    """Assemble the whole library page: collections in order, each with its texts.

    Built here rather than in the template or the view so that the template only
    prints what it is given. Everything is read in three queries regardless of
    how many collections there are.

    Returns:
        Shared HSK levels first, then the user's own collections, then the texts
        that are in no collection at all.
    """
    texts = list(visible_texts(user).select_related("collection"))
    statuses = statuses_for(user, texts)

    rows_by_collection: dict[int | None, list[TextRow]] = {}
    for text in texts:
        row = TextRow(text=text, status=statuses.get(text.pk, ReadingProgress.Status.NEW))
        rows_by_collection.setdefault(text.collection_id, []).append(row)

    groups = [
        Group(
            collection=collection,
            title=collection.title,
            is_system=collection.is_system,
            rows=rows_by_collection.get(collection.pk, []),
        )
        for collection in visible_collections(user)
    ]

    # «Без подборки» — не запись в базе, а место, куда попадает всё сохранённое,
    # пока его не разложили. Поэтому группа собирается здесь и идёт последней.
    groups.append(
        Group(
            collection=None,
            title=NO_COLLECTION_TITLE,
            is_system=False,
            rows=rows_by_collection.get(None, []),
        )
    )

    return groups


def _clean_title(title: str, max_length: int) -> str:
    """Strip and validate a title.

    Raises:
        InvalidTitleError: If it is blank or too long.
    """
    title = title.strip()

    if not title:
        raise InvalidTitleError("Название не может быть пустым.")

    if len(title) > max_length:
        raise InvalidTitleError(f"Название длиннее {max_length} символов.")

    return title
