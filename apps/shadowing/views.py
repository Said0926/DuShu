"""Views for the shadowing page.

Thin on purpose: parse the request, call services from ``chinese`` and ``tts``,
render. The one thing that does belong here is the limit, for the same reason it
does in the reader — only the view knows whether this request will reach the
provider at all.
"""

import logging
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.chinese.exceptions import TextTooLongError
from apps.chinese.services import process_text
from apps.chinese.types import ProcessedText
from apps.core.limits import consume_audio_limit, user_audio_limit
from apps.tts.exceptions import TTSError
from apps.tts.services import has_cached_audio

from .forms import ShadowingForm
from .services import SpokenSentence, speak_text

logger = logging.getLogger(__name__)


def _speak_or_warn(processed: ProcessedText) -> tuple[list[SpokenSentence], str]:
    """Speak a text, degrading to no audio on failure.

    The speech endpoint is unofficial and occasionally unavailable. When it is,
    the page still shows the text with pinyin and tone colours, which is most of
    the value — it just cannot play it.

    Args:
        processed: The processed text.

    Returns:
        A pair of (sentences, warning). The warning is empty on success, and the
        sentence list is empty when it is not.
    """
    try:
        return speak_text(processed), ""
    except TTSError as error:
        logger.error("Speech failed for %s sentences: %s", len(processed.sentences), error)
        return [], "Озвучка сейчас недоступна. Попробуйте обновить страницу через минуту."


class ShadowingView(View):
    """Renders a submitted text for shadowing."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Show the empty state with the input form.

        Its own URL and its own entry point, so following "Shadowing" in the
        navigation lands somewhere that makes sense.
        """
        context: dict[str, Any] = {
            "sentences": [],
            "max_text_length": settings.MAX_TEXT_LENGTH,
            "translation_languages": settings.TRANSLATION_LANGUAGES,
            "active_nav": "shadowing",
        }
        return render(request, "shadowing/shadowing.html", context)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ShadowingForm(request.POST)

        if not form.is_valid():
            # Ошибки формы показываем на главной, рядом с полем ввода.
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("core:home")

        text: str = form.cleaned_data["text"]

        try:
            processed = process_text(text)
        except TextTooLongError:
            # Форма проверяет ту же границу, так что сюда попасть трудно.
            logger.warning("Text passed form validation but exceeded the processing limit")
            return redirect("core:home")

        sentences = [sentence.text for sentence in processed.sentences]

        # Лимит тратим только на платную работу. Текст, уже озвученный целиком,
        # никуда не ходит, и перечитывать его можно сколько угодно — иначе
        # библиотека была бы бесполезной.
        if not has_cached_audio(sentences):
            limit = consume_audio_limit(request)

            if limit is not None and limit.exceeded:
                context = {"limit": limit, "user_limit": user_audio_limit()}
                return render(request, "core/rate_limited.html", context, status=429)

        spoken, warning = _speak_or_warn(processed)

        context: dict[str, Any] = {
            "sentences": spoken,
            "source_text": text,
            "warning": warning,
            "active_nav": "shadowing",
            "translation_languages": settings.TRANSLATION_LANGUAGES,
            # Заголовок и статус приходят скрытыми полями из библиотеки — так эта
            # страница открывает сохранённый текст, ничего не зная про library.
            "text_title": form.cleaned_data["title"],
            "already_saved": form.cleaned_data["saved"],
            "saved_id": form.cleaned_data["saved_id"],
            "text_status": form.cleaned_data["status"],
        }
        return render(request, "shadowing/shadowing.html", context)
