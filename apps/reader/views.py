"""Views for the reader page.

Both views are deliberately thin: they parse the request, call services from
``chinese``, ``translation`` and ``dictionary``, and render. No business logic
lives here.
"""

import logging
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.chinese.exceptions import TextTooLongError
from apps.chinese.services import process_text
from apps.chinese.types import ProcessedText
from apps.core.limits import (
    LOOKUP_GROUP,
    RATE_KEY,
    TEXT_GROUP,
    lookup_rate,
    text_limit_state,
    text_rate,
    user_text_limit,
)
from apps.dictionary.exceptions import UnknownLanguageError
from apps.dictionary.services import lookup_with_fallback
from apps.translation.exceptions import TranslationError
from apps.translation.services import translate_sentences

from .forms import ReaderForm

logger = logging.getLogger(__name__)

# Предел длины слова в подсказке. Самые длинные словарные статьи — несколько
# иероглифов, так что ограничение щедрое. Нужно оно потому, что при промахе
# по слову сервис разворачивает его в запрос по каждому иероглифу, а endpoint
# открыт без авторизации и пока без ограничения частоты запросов.
MAX_LOOKUP_WORD_LENGTH = 32


def _translate_or_warn(processed: ProcessedText, language: str) -> tuple[list[str], str]:
    """Translate every sentence, degrading to no translation on failure.

    A dead translation service must not take the page with it: pinyin, tones and
    dictionary tooltips still work, and those are most of the value.

    Args:
        processed: The processed text.
        language: Target language code.

    Returns:
        A pair of (translations, warning). The warning is empty on success, and
        the translations list is empty when it is not.
    """
    sentences = [sentence.text for sentence in processed.sentences]

    try:
        return translate_sentences(sentences, language), ""
    except TranslationError as error:
        logger.error("Translation failed for %s sentences: %s", len(sentences), error)
        return [], "Перевод сейчас недоступен. Текст, пиньинь и подсказки работают."


# Лимит навешен на сам метод post, поэтому GET на страницу его не расходует.
# method при этом не ограничиваем намеренно: этот параметр попадает в ключ
# счётчика, и с method="POST" шапка не смогла бы прочитать тот же счётчик
# с обычной GET-страницы — показывала бы пустоту вместо остатка.
@method_decorator(
    ratelimit(group=TEXT_GROUP, key=RATE_KEY, rate=text_rate, block=False),
    name="post",
)
class ReaderView(View):
    """Renders a submitted text for reading."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Show the empty state with the input form.

        The page has its own URL and its own entry point, so following "Чтение"
        in the navigation lands somewhere that makes sense instead of bouncing
        back to the landing page.
        """
        context: dict[str, Any] = {
            "rows": [],
            "max_text_length": settings.MAX_TEXT_LENGTH,
            "translation_languages": settings.TRANSLATION_LANGUAGES,
            "active_nav": "reader",
        }
        return render(request, "reader/reader.html", context)

    def post(self, request: HttpRequest) -> HttpResponse:
        # block=False у декоратора: он только ставит флаг, а решение принимаем
        # здесь. При block=True Django вернул бы голую 403 — ни объяснения,
        # ни предложения зарегистрироваться, ни правильного статуса.
        if getattr(request, "limited", False):
            context = {
                "limit": text_limit_state(request),
                "user_limit": user_text_limit(),
            }
            return render(request, "core/rate_limited.html", context, status=429)

        form = ReaderForm(request.POST)

        if not form.is_valid():
            # Ошибки формы показываем на главной, рядом с полем ввода.
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("core:home")

        text: str = form.cleaned_data["text"]
        language: str = form.cleaned_data["lang"]

        try:
            processed = process_text(text)
        except TextTooLongError:
            # Форма проверяет ту же границу, так что сюда попасть трудно.
            # Оставлено на случай, если лимит поменяют в одном месте из двух.
            logger.warning("Text passed form validation but exceeded the processing limit")
            return redirect("core:home")

        translations, warning = _translate_or_warn(processed, language)

        # Сшиваем предложения с переводами здесь, а не в шаблоне: шаблон должен
        # только выводить готовые данные.
        rows = [
            (sentence, translations[index] if index < len(translations) else "")
            for index, sentence in enumerate(processed.sentences)
        ]

        context: dict[str, Any] = {
            "rows": rows,
            "source_text": text,
            "language": language,
            "translation_languages": settings.TRANSLATION_LANGUAGES,
            "warning": warning,
            "active_nav": "reader",
        }
        return render(request, "reader/reader.html", context)


@method_decorator(
    ratelimit(group=LOOKUP_GROUP, key=RATE_KEY, rate=lookup_rate, block=False),
    name="get",
)
class LookupView(View):
    """Returns dictionary data for one word, for the hover tooltip.

    Answers from the local database only — no external API, so a tooltip costs
    nothing and appears instantly.
    """

    def get(self, request: HttpRequest) -> JsonResponse:
        if getattr(request, "limited", False):
            # Здесь отвечаем JSON, а не страницей: ответ читает fetch из tooltip.js.
            return JsonResponse(
                {"data": None, "error": "rate_limited", "message": "Слишком много запросов."},
                status=429,
            )

        word = request.GET.get("word", "").strip()
        language = request.GET.get("lang", settings.DEFAULT_TRANSLATION_LANGUAGE)

        if not word:
            return JsonResponse(
                {"data": None, "error": "missing_word", "message": "Не передано слово."},
                status=400,
            )

        if len(word) > MAX_LOOKUP_WORD_LENGTH:
            return JsonResponse(
                {"data": None, "error": "word_too_long", "message": "Слишком длинное слово."},
                status=400,
            )

        try:
            result = lookup_with_fallback(word, language)
        except UnknownLanguageError:
            return JsonResponse(
                {"data": None, "error": "unknown_language", "message": "Неизвестный язык."},
                status=400,
            )

        data = {
            "word": result.word,
            "found": result.found,
            "entries": [
                {"pinyin": entry.pinyin, "definitions": entry.definitions}
                for entry in result.entries
            ],
            "characters": [
                {
                    "character": character.character,
                    "entries": [
                        {"pinyin": entry.pinyin, "definitions": entry.definitions}
                        for entry in character.entries
                    ],
                }
                for character in result.characters
            ],
        }

        return JsonResponse({"data": data, "error": None, "message": ""})
