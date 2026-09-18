"""Shared implementation for the dictionary import commands.

The leading underscore keeps Django from picking this module up as a command of
its own: only the concrete subclasses should be runnable.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.dictionary.exceptions import UnknownLanguageError
from apps.dictionary.models import DictionaryEntry
from apps.dictionary.parsers import ParsedEntry, merge_duplicates
from apps.dictionary.services import import_entries


class BaseImportCommand(BaseCommand):
    """Reads a dump with ``parser`` and writes it into the database.

    Subclasses only declare where the data comes from and what it is:

        class Command(BaseImportCommand):
            source = "cc-cedict"
            language = "en"
            parser = staticmethod(parse_file)
    """

    source: str
    language: str
    parser: Callable[[Path], Iterator[ParsedEntry]]

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "path",
            type=Path,
            help="Path to the dump. A .gz file is read without unpacking it first.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Delete this source's existing entries first. Use it when importing "
                "a newer dump: without it, updated entries are skipped as duplicates "
                "and outdated ones stay behind."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path: Path = options["path"]

        if not path.exists():
            raise CommandError(f"File not found: {path}")

        if options["replace"]:
            deleted, _ = DictionaryEntry.objects.filter(source=self.source).delete()
            self.stdout.write(f"Removed {deleted} existing entries from {self.source}.")

        self.stdout.write(f"Importing {self.source} ({self.language}) from {path}...")

        try:
            processed = import_entries(
                merge_duplicates(self.parser(path)),
                language=self.language,
                source=self.source,
            )
        except UnknownLanguageError as error:
            # Ошибка конфигурации, а не пользователя: CommandError печатает её
            # понятным сообщением вместо трейсбека.
            raise CommandError(str(error)) from error

        total = DictionaryEntry.objects.filter(source=self.source).count()
        self.stdout.write(
            self.style.SUCCESS(f"Processed {processed} entries. {self.source} now holds {total}.")
        )
