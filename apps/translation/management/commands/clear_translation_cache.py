"""Drop cached translations.

    docker compose exec web python manage.py clear_translation_cache --provider DummyProvider

Needed whenever the cache holds results you no longer trust: translations made
by the dummy provider while there was no API key, or entries from a provider
whose quality turned out to be poor. Without this the cache would keep serving
them, since a cache hit never reaches the provider.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.translation.models import SentenceTranslation


class Command(BaseCommand):
    help = "Delete cached sentence translations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--provider",
            help="Only delete entries made by this provider, e.g. DummyProvider.",
        )
        parser.add_argument(
            "--language",
            help="Only delete entries for this language code.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = SentenceTranslation.objects.all()

        if options["provider"]:
            queryset = queryset.filter(provider=options["provider"])
        if options["language"]:
            queryset = queryset.filter(target_language=options["language"])

        deleted, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} cached translations."))
