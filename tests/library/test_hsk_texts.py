"""Tests for the shared HSK catalog and the command that loads it.

Two different things are checked here. One is the file in the repository: it is
content, and content can be wrong in ways the code cannot. The other is the
loading itself, which has to be safe to run again — otherwise fixing a typo in
one text would mean rebuilding the whole catalog.
"""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.library.catalog import MAX_CATALOG_TITLE_LENGTH, read_catalog
from apps.library.exceptions import CatalogError
from apps.library.models import HSK_LEVELS, Collection, ReadingProgress, SavedText

pytestmark = pytest.mark.django_db

# Реальные тексты для проверок загрузки не нужны: она работает с любым китайским.
FIRST = {"level": 1, "title": "我的一天", "text": "我叫小明。我今天很忙。"}
SECOND = {"level": 2, "title": "学校", "text": "我们的学校很大。老师很好。"}


def write_catalog(directory: Path, entries: list[dict]) -> Path:
    """Write a catalog file into a temporary directory and return its path."""
    path = directory / "hsk_texts.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def load(path: Path, *args: str) -> None:
    """Run the command against a given file."""
    call_command("load_hsk_texts", "--file", str(path), *args)


# --- файл в репозитории ---


def test_the_shipped_catalog_is_readable() -> None:
    """Whatever is in the repository must at least parse and validate."""
    read_catalog()


def test_every_level_in_the_catalog_holds_ten_texts() -> None:
    """Ten per level is the promise the library page is built around.

    Written as "every level present" rather than "all five levels" on purpose:
    the catalog is filled one level at a time, and this has to be a useful test
    while that is going on.
    """
    counts: dict[int, int] = {}
    for entry in read_catalog():
        counts[entry.level] = counts.get(entry.level, 0) + 1

    assert all(count == 10 for count in counts.values()), counts


# --- чтение и проверка файла ---


def test_a_missing_file_is_reported_plainly(tmp_path: Path) -> None:
    with pytest.raises(CatalogError, match="not found"):
        read_catalog(tmp_path / "nothing.json")


def test_broken_json_is_reported_plainly(tmp_path: Path) -> None:
    path = tmp_path / "hsk_texts.json"
    path.write_text("[{", encoding="utf-8")

    with pytest.raises(CatalogError, match="not valid JSON"):
        read_catalog(path)


def test_the_catalog_must_be_a_list(tmp_path: Path) -> None:
    path = tmp_path / "hsk_texts.json"
    path.write_text('{"level": 1}', encoding="utf-8")

    with pytest.raises(CatalogError, match="list of texts"):
        read_catalog(path)


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"level": 1, "title": "我"}, "missing text"),
        ({"level": 9, "title": "我", "text": "我去。"}, "unknown HSK level"),
        ({"level": 1, "title": "   ", "text": "我去。"}, "title is empty"),
        ({"level": 1, "title": "我" * 60, "text": "我去。"}, "the column holds"),
        ({"level": 1, "title": "我", "text": "   "}, "text is empty"),
        ({"level": 1, "title": "我", "text": "我\n去。"}, "line break"),
    ],
)
def test_a_text_that_could_not_be_shown_is_refused(
    tmp_path: Path, entry: dict, message: str
) -> None:
    """Everything is checked before a single row is written.

    A half-loaded catalog would be worse than a refused one: nothing says which
    half made it.
    """
    path = write_catalog(tmp_path, [entry])

    with pytest.raises(CatalogError, match=message):
        read_catalog(path)


def test_a_text_longer_than_the_limit_is_refused(tmp_path: Path) -> None:
    """The same limit the input form enforces — a catalog text is opened the same way."""
    path = write_catalog(
        tmp_path,
        [{"level": 1, "title": "长", "text": "我" * (settings.MAX_TEXT_LENGTH + 1)}],
    )

    with pytest.raises(CatalogError, match="the limit is"):
        read_catalog(path)


def test_the_same_text_twice_is_refused(tmp_path: Path) -> None:
    """The database would refuse it too, but halfway through and less clearly."""
    path = write_catalog(tmp_path, [FIRST, {**FIRST, "title": "другое название"}])

    with pytest.raises(CatalogError, match="repeats the text"):
        read_catalog(path)


def test_the_title_limit_matches_the_column() -> None:
    """A title the file accepts must fit into the database."""
    assert MAX_CATALOG_TITLE_LENGTH == SavedText._meta.get_field("title").max_length


# --- загрузка ---


def test_texts_land_in_their_shared_collection_without_an_owner(tmp_path: Path) -> None:
    load(write_catalog(tmp_path, [FIRST, SECOND]))

    first = SavedText.objects.get(title="我的一天")
    assert first.owner is None
    assert first.collection == Collection.objects.get(owner__isnull=True, hsk_level=1)
    assert first.content == FIRST["text"]


def test_loading_twice_creates_nothing(tmp_path: Path) -> None:
    """The whole reason the fingerprint is the key."""
    path = write_catalog(tmp_path, [FIRST, SECOND])
    load(path)
    load(path)

    assert SavedText.objects.filter(owner__isnull=True).count() == 2


def test_a_renamed_text_gets_its_new_title(tmp_path: Path) -> None:
    """Titles are brought in line with the file on every load: it is cheap and it
    fixes a database that drifted away from it."""
    load(write_catalog(tmp_path, [FIRST]))
    load(write_catalog(tmp_path, [{**FIRST, "title": "新名字"}]))

    assert SavedText.objects.get(owner__isnull=True).title == "新名字"
    assert SavedText.objects.filter(owner__isnull=True).count() == 1


def test_one_level_can_be_loaded_alone(tmp_path: Path) -> None:
    """How the catalog is written: ten texts, checked, then the next level."""
    load(write_catalog(tmp_path, [FIRST, SECOND]), "--level", "1")

    assert [text.title for text in SavedText.objects.filter(owner__isnull=True)] == ["我的一天"]


def test_a_text_dropped_from_the_file_survives_without_prune(tmp_path: Path) -> None:
    """Deleting is never a side effect of loading."""
    load(write_catalog(tmp_path, [FIRST, SECOND]))
    load(write_catalog(tmp_path, [FIRST]))

    assert SavedText.objects.filter(owner__isnull=True).count() == 2


def test_prune_removes_what_the_file_no_longer_holds(tmp_path: Path) -> None:
    load(write_catalog(tmp_path, [FIRST, SECOND]))
    load(write_catalog(tmp_path, [FIRST]), "--prune")

    assert [text.title for text in SavedText.objects.filter(owner__isnull=True)] == ["我的一天"]


def test_prune_of_one_level_leaves_the_others_alone(tmp_path: Path) -> None:
    """Otherwise writing the catalog level by level would wipe the finished ones."""
    load(write_catalog(tmp_path, [FIRST, SECOND]))
    load(write_catalog(tmp_path, []), "--level", "1", "--prune")

    assert [text.title for text in SavedText.objects.filter(owner__isnull=True)] == ["学校"]


def test_a_pruned_text_takes_its_reading_progress_with_it(tmp_path: Path, user: User) -> None:
    """Documented rather than prevented: this is why --prune is a flag.

    A catalog text is one row for everybody, so deleting it cannot leave anyone's
    progress pointing at it.
    """
    load(write_catalog(tmp_path, [FIRST]))
    text = SavedText.objects.get(owner__isnull=True)
    ReadingProgress.objects.create(user=user, text=text, status=ReadingProgress.Status.DONE)

    load(write_catalog(tmp_path, []), "--prune")

    assert not ReadingProgress.objects.exists()


def test_a_missing_shared_collection_stops_the_load(tmp_path: Path) -> None:
    """It means the data migration has not been applied, not that data is bad."""
    Collection.objects.filter(owner__isnull=True, hsk_level__in=HSK_LEVELS).delete()

    with pytest.raises(CommandError, match="No shared collection"):
        load(write_catalog(tmp_path, [FIRST]))


def test_a_broken_file_stops_the_command(tmp_path: Path) -> None:
    """The command turns a catalog problem into a message, not a traceback."""
    with pytest.raises(CommandError, match="unknown HSK level"):
        load(write_catalog(tmp_path, [{"level": 9, "title": "我", "text": "我去。"}]))
