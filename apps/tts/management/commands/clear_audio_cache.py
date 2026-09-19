"""Drop cached audio.

    docker compose exec web python manage.py clear_audio_cache --provider DummyTTSProvider

Needed whenever the cache holds audio you no longer want: silence produced by
the dummy provider while working without a network, or a voice you have moved
away from. Without this the cache would keep serving it, since a cache hit never
reaches the provider — and silence is a much more confusing thing to keep serving
than a stale translation.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.tts.models import SentenceAudio


class Command(BaseCommand):
    help = "Delete cached sentence audio, files included."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--provider",
            help="Only delete entries made by this provider, e.g. DummyTTSProvider.",
        )
        parser.add_argument(
            "--voice",
            help="Only delete entries spoken by this voice.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        queryset = SentenceAudio.objects.all()

        if options["provider"]:
            queryset = queryset.filter(provider=options["provider"])
        if options["voice"]:
            queryset = queryset.filter(voice=options["voice"])

        # Удаляем построчно, а не queryset.delete(): Django не трогает файлы при
        # удалении строк, и массовое удаление оставило бы media/ забитым
        # аудио, на которое уже ничто не ссылается.
        deleted = 0

        for row in queryset.iterator():
            row.audio.delete(save=False)
            row.delete()
            deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} cached audio files."))
