"""Load the shared HSK texts from the repository into the library.

    docker compose exec web python manage.py load_hsk_texts            # всё
    docker compose exec web python manage.py load_hsk_texts --level 1  # один уровень
    docker compose exec web python manage.py load_hsk_texts --prune    # + убрать лишнее

Safe to run again: a text is recognised by the fingerprint of its content, which
is also what the database makes unique among catalog texts. Editing a title in
the file and loading again fixes the title; editing the text makes a new one, so
that is what ``--prune`` is for.
"""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.library.catalog import CATALOG_PATH, load_catalog, read_catalog
from apps.library.exceptions import CatalogError
from apps.library.models import HSK_LEVELS


class Command(BaseCommand):
    help = "Load the shared HSK texts from the repository into the library."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--file",
            type=Path,
            default=CATALOG_PATH,
            help="Which catalog file to read. Defaults to the one in the repository.",
        )
        parser.add_argument(
            "--level",
            type=int,
            choices=HSK_LEVELS,
            help="Load one level only. Useful while the catalog is being written.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help=(
                "Also delete catalog texts of the loaded levels that the file no longer "
                "holds. Off by default: deleting one takes every reader's progress for "
                "it along."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path: Path = options["file"]
        level: int | None = options["level"]
        levels = {level} if level else set(HSK_LEVELS)

        try:
            texts = read_catalog(path)
            selected = [entry for entry in texts if entry.level in levels]
            report = load_catalog(selected, levels=levels, prune=options["prune"])
        except CatalogError as error:
            # Ошибка в файле или в базе, а не у пользователя: CommandError печатает
            # её понятной строкой вместо трейсбека.
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(selected)} texts: {report.created} new, "
                f"{report.updated} updated, {report.unchanged} unchanged."
            )
        )

        if report.pruned:
            self.stdout.write(f"Deleted {report.pruned} texts the file no longer holds.")
