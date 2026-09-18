"""Tests for the dictionary import commands."""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.dictionary.models import DictionaryEntry

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_import_cedict_loads_entries() -> None:
    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())

    assert DictionaryEntry.objects.filter(source="cc-cedict", language="en").exists()
    assert DictionaryEntry.objects.get(simplified="银行", language="en").pinyin == "yín háng"


def test_import_cedict_merges_spelling_variants() -> None:
    """The command has to apply merging, or 俊 lands as "old variant of 俊"."""
    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())

    entry = DictionaryEntry.objects.get(simplified="俊", pinyin="jùn")
    assert entry.definitions[0] == "smart"


def test_import_bkrs_loads_entries() -> None:
    call_command("import_bkrs", FIXTURES / "bkrs_sample.txt", stdout=StringIO())

    entry = DictionaryEntry.objects.get(simplified="银行", language="ru")
    assert entry.definitions == ["банк"]
    assert entry.source == "bkrs"


def test_both_dictionaries_live_side_by_side() -> None:
    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())
    call_command("import_bkrs", FIXTURES / "bkrs_sample.txt", stdout=StringIO())

    assert DictionaryEntry.objects.filter(simplified="银行").count() == 2


def test_running_the_import_twice_is_safe() -> None:
    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())
    before = DictionaryEntry.objects.count()

    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())

    assert DictionaryEntry.objects.count() == before


def test_replace_clears_only_its_own_source() -> None:
    """Re-importing a newer english dump must not wipe the russian one."""
    call_command("import_cedict", FIXTURES / "cedict_sample.txt", stdout=StringIO())
    call_command("import_bkrs", FIXTURES / "bkrs_sample.txt", stdout=StringIO())
    russian_before = DictionaryEntry.objects.filter(source="bkrs").count()

    call_command("import_cedict", FIXTURES / "cedict_sample.txt", "--replace", stdout=StringIO())

    assert DictionaryEntry.objects.filter(source="bkrs").count() == russian_before


def test_missing_file_reports_a_readable_error() -> None:
    with pytest.raises(CommandError, match="File not found"):
        call_command("import_cedict", FIXTURES / "does_not_exist.txt", stdout=StringIO())
