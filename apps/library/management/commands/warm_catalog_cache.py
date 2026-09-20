"""Translate and speak every shared text ahead of the first reader.

    docker compose exec web python manage.py warm_catalog_cache
    docker compose exec web python manage.py warm_catalog_cache --level 1 --language ru

Everything paid for is cached in the database, and a cache hit never reaches a
provider. So warming the catalog once means the shared texts open instantly for
everybody and cost nobody their hourly limit — the counters are spent on work
sent to a provider, and after this there is none.

Worth knowing before running it: MEDIA_ROOT is not a named volume yet, so
recreating the container wipes the audio and the warming has to be repeated.
"""

import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from apps.chinese.services import process_text
from apps.library.catalog import catalog_texts
from apps.library.models import HSK_LEVELS, SavedText
from apps.translation.exceptions import TranslationError
from apps.translation.services import translate_sentences
from apps.tts.exceptions import TTSError
from apps.tts.services import get_sentence_audio

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Translate and speak the shared HSK texts so readers never wait for them."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--level",
            type=int,
            choices=HSK_LEVELS,
            help="Warm one level only.",
        )
        parser.add_argument(
            "--language",
            choices=sorted(settings.TRANSLATION_LANGUAGES),
            help="Warm one language only. Defaults to every language the site offers.",
        )
        parser.add_argument(
            "--skip-translation",
            action="store_true",
            help="Leave translations alone. They are the part that costs money.",
        )
        parser.add_argument(
            "--skip-audio",
            action="store_true",
            help="Leave audio alone. Synthesis is free but slow.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        level: int | None = options["level"]
        levels = {level} if level else None
        languages = [options["language"]] if options["language"] else list(
            settings.TRANSLATION_LANGUAGES
        )

        texts = catalog_texts(levels)
        if not texts:
            self.stdout.write("No catalog texts to warm. Run load_hsk_texts first.")
            return

        failures = 0

        for text in texts:
            sentences = [sentence.text for sentence in process_text(text.content).sentences]
            problems: list[str] = []

            if not options["skip_translation"]:
                problems += self._translate(sentences, languages)

            if not options["skip_audio"]:
                problems += self._speak(sentences)

            failures += len(problems)
            self._report(text, len(sentences), problems)

        self.stdout.write(
            self.style.SUCCESS(f"Warmed {len(texts)} texts.")
            if not failures
            else self.style.WARNING(f"Warmed {len(texts)} texts, {failures} steps failed.")
        )

    def _translate(self, sentences: list[str], languages: list[str]) -> list[str]:
        """Translate into every language, reporting what failed.

        Каждый язык отдельно и каждый текст отдельно: провайдер может отказать
        на одном и работать на остальных, и прогон из пятидесяти текстов не
        должен падать целиком из-за одного отказа.
        """
        problems = []

        for language in languages:
            try:
                translate_sentences(sentences, language)
            except TranslationError as error:
                logger.error("Translation into %s failed: %s", language, error)
                problems.append(f"перевод {language}")

        return problems

    def _speak(self, sentences: list[str]) -> list[str]:
        """Speak every sentence, reporting failure rather than raising.

        Эндпоинт неофициальный и временами отвечает 503 — по этой же причине всё
        и кэшируется. Пропущенный текст можно догреть повторным запуском.
        """
        try:
            get_sentence_audio(sentences)
        except TTSError as error:
            logger.error("Speech failed: %s", error)
            return ["озвучка"]

        return []

    def _report(self, text: SavedText, sentences: int, problems: list[str]) -> None:
        """Print one line per text, so a long run shows where it is."""
        level = text.collection.hsk_level if text.collection else "—"
        line = f"HSK {level}  {text.title}  ({sentences} предложений)"

        if problems:
            self.stdout.write(self.style.WARNING(f"{line} — не вышло: {', '.join(problems)}"))
        else:
            self.stdout.write(line)
