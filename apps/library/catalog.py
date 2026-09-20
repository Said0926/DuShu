"""The shared HSK catalog: texts that belong to everybody.

A catalog text is a :class:`~apps.library.models.SavedText` with no owner, sitting
in a shared HSK collection. Nothing on the site creates one — shared content is
written by whoever runs the project, not by its readers — so these texts live in
a file in the repository and are loaded by ``manage.py load_hsk_texts``.

A file rather than a data migration, because a migration has to keep meaning what
it meant the day it was written: fixing a typo in a text would cost a new
migration every time, and fifty chinese texts inside one are unreadable besides.

The file is a list of objects, one per text::

    [{"level": 1, "title": "我的一天", "text": "我叫小明。我今天很忙。"}]

A flat list rather than a mapping keyed by level: adding HSK 6 should be new
entries, not a new shape.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from .exceptions import CatalogError
from .models import HSK_LEVELS, TITLE_LENGTH, Collection, SavedText, content_hash

# Файл лежит внутри app, а не в data/ в корне проекта: корневая data/ значится
# в .gitignore — там дампы словарей, которые качают руками, — а эти тексты
# обязаны ехать в репозитории.
CATALOG_PATH = Path(__file__).parent / "data" / "hsk_texts.json"

# Ровно столько, сколько держит колонка заголовка.
MAX_CATALOG_TITLE_LENGTH = TITLE_LENGTH + 1


@dataclass(frozen=True, slots=True)
class CatalogText:
    """One text as the file describes it.

    Attributes:
        level: Which shared HSK collection it belongs to.
        title: Shown on the card in the library. Written in chinese, within the
            vocabulary of its own level, because the card renders it with the
            chinese font — and because a HSK 1 title should be readable by
            somebody learning HSK 1.
        text: The text itself, on a single line.
    """

    level: int
    title: str
    text: str

    @property
    def fingerprint(self) -> str:
        """The hash that recognises this text in the database.

        The same one the model's ``unique_catalog_text`` constraint is built on,
        which is what makes loading the file twice safe.
        """
        return content_hash(self.text)


@dataclass(frozen=True, slots=True)
class LoadReport:
    """What one load did."""

    created: int
    updated: int
    unchanged: int
    pruned: int


def read_catalog(path: Path = CATALOG_PATH) -> list[CatalogText]:
    """Read and check the catalog file.

    Everything is validated here rather than on the way into the database, so a
    broken file is reported in full before a single row is written.

    Args:
        path: The file to read.

    Returns:
        Every text in the file, in the order it appears.

    Raises:
        CatalogError: If the file is missing, is not valid JSON, or holds a text
            that could not be shown correctly.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogError(f"Catalog file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise CatalogError(f"Catalog file {path} is not valid JSON: {error}") from error

    if not isinstance(raw, list):
        raise CatalogError(f"Catalog file {path} must hold a list of texts.")

    texts = [_as_catalog_text(item, number) for number, item in enumerate(raw, start=1)]
    _reject_duplicates(texts)
    return texts


def load_catalog(
    texts: list[CatalogText],
    *,
    levels: set[int],
    prune: bool = False,
) -> LoadReport:
    """Write the given texts into the shared collections.

    Args:
        texts: Texts to load. All of them must belong to ``levels``.
        levels: Which levels this load is responsible for. Pruning is confined to
            them, so ``--level 1 --prune`` cannot touch HSK 2.
        prune: Whether to delete catalog texts of those levels that the file no
            longer holds.

    Returns:
        How many texts were created, updated, left alone and deleted.

    Raises:
        CatalogError: If a shared collection is missing, or a text belongs to a
            level this load was not asked for.
    """
    collections = _shared_collections(levels)

    created = 0
    updated = 0
    unchanged = 0
    seen: set[str] = set()

    for entry in texts:
        if entry.level not in collections:
            raise CatalogError(
                f"Text «{entry.title}» is HSK {entry.level}, which this load does not cover."
            )

        collection = collections[entry.level]
        seen.add(entry.fingerprint)

        row, was_created = SavedText.objects.get_or_create(
            owner=None,
            content_hash=entry.fingerprint,
            defaults={
                "content": entry.text,
                "title": entry.title,
                "collection": collection,
            },
        )

        if was_created:
            created += 1
        elif row.title != entry.title or row.collection_id != collection.pk:
            # Заголовок и подборку приводим к файлу всегда: это дёшево и чинит
            # расхождение. Сам текст не трогаем — он и есть ключ записи.
            row.title = entry.title
            row.collection = collection
            row.save(update_fields=["title", "collection"])
            updated += 1
        else:
            unchanged += 1

    pruned = _prune(collections.values(), keep=seen) if prune else 0

    return LoadReport(created=created, updated=updated, unchanged=unchanged, pruned=pruned)


def _as_catalog_text(item: object, number: int) -> CatalogText:
    """Turn one entry of the file into a checked :class:`CatalogText`.

    Raises:
        CatalogError: If the entry is malformed. The message names the position
            in the file, because a chinese text is hard to find by eye.
    """
    if not isinstance(item, dict):
        raise CatalogError(f"Text #{number}: expected an object, got {type(item).__name__}.")

    missing = {"level", "title", "text"} - set(item)
    if missing:
        raise CatalogError(f"Text #{number}: missing {', '.join(sorted(missing))}.")

    level = item["level"]
    if level not in HSK_LEVELS:
        raise CatalogError(f"Text #{number}: unknown HSK level {level!r}.")

    title = str(item["title"]).strip()
    if not title:
        raise CatalogError(f"Text #{number}: the title is empty.")
    if len(title) > MAX_CATALOG_TITLE_LENGTH:
        raise CatalogError(
            f"Text #{number}: the title is {len(title)} characters, "
            f"and the column holds {MAX_CATALOG_TITLE_LENGTH}."
        )

    text = str(item["text"]).strip()
    if not text:
        raise CatalogError(f"Text #{number} («{title}»): the text is empty.")
    if len(text) > settings.MAX_TEXT_LENGTH:
        raise CatalogError(
            f"Text #{number} («{title}») is {len(text)} characters, "
            f"and the limit is {settings.MAX_TEXT_LENGTH}."
        )
    if "\n" in text:
        # Перенос строки здесь означал бы две разные вещи сразу: splitter считает
        # его границей предложения, а библиотека передаёт текст в «Чтение»
        # скрытым input, где переносу не место. Каталожный текст — один абзац.
        raise CatalogError(f"Text #{number} («{title}») contains a line break.")

    return CatalogText(level=level, title=title, text=text)


def _reject_duplicates(texts: list[CatalogText]) -> None:
    """Fail on two identical texts in one file.

    The database would reject the second one anyway — the fingerprint is unique
    among catalog texts — but it would do so halfway through a load, and the
    message would be about a constraint rather than about the file.

    Raises:
        CatalogError: If two texts have the same content.
    """
    by_fingerprint: dict[str, str] = {}

    for entry in texts:
        first = by_fingerprint.get(entry.fingerprint)
        if first is not None:
            raise CatalogError(f"«{entry.title}» repeats the text of «{first}».")
        by_fingerprint[entry.fingerprint] = entry.title


def _shared_collections(levels: set[int]) -> dict[int, Collection]:
    """Find the shared collection of every level being loaded.

    Raises:
        CatalogError: If one of them does not exist. That means the data
            migration that creates them has not been applied.
    """
    found = {
        collection.hsk_level: collection
        for collection in Collection.objects.filter(owner__isnull=True, hsk_level__in=levels)
    }

    missing = sorted(levels - set(found))
    if missing:
        levels_text = ", ".join(str(level) for level in missing)
        raise CatalogError(
            f"No shared collection for HSK {levels_text}. Apply the migrations first."
        )

    return found


def _prune(collections: Iterable[Collection], *, keep: set[str]) -> int:
    """Delete catalog texts of these collections that the file no longer holds.

    Only ever called behind an explicit ``--prune``: deleting a catalog text takes
    every reader's :class:`~apps.library.models.ReadingProgress` for it along,
    and that is not something a routine load should do quietly.

    Args:
        collections: The shared collections being synced.
        keep: Fingerprints the file still holds.

    Returns:
        How many texts were deleted.
    """
    doomed = SavedText.objects.filter(
        owner__isnull=True,
        collection__in=list(collections),
    ).exclude(content_hash__in=keep)

    deleted = doomed.count()
    doomed.delete()
    return deleted


def catalog_texts(levels: set[int] | None = None) -> list[SavedText]:
    """Return the shared texts, newest shelf last.

    Args:
        levels: Only these HSK levels, or ``None`` for all of them.

    Returns:
        Every catalog text, ordered by level and then by the order it was loaded
        in, which is the order of the file.
    """
    texts = SavedText.objects.filter(owner__isnull=True, collection__isnull=False)

    if levels is not None:
        texts = texts.filter(collection__hsk_level__in=levels)

    return list(texts.select_related("collection").order_by("collection__hsk_level", "pk"))
