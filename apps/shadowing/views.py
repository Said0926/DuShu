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
from apps.core.limits import consume_audio_limit, consume_text_limit, user_audio_limit
from apps.translation.exceptions import TranslationError
from apps.translation.services import has_cached_translations, translate_sentences
from apps.tts.exceptions import TTSError
from apps.tts.services import has_cached_audio

from .forms import ShadowingForm
from .services import SpokenSentence, speak_text

logger = logging.getLogger(__name__)


def _translate_or_warn(
    processed: ProcessedText,
    language: str,
    *,
    allowed: bool,
) -> tuple[list[str], str]:
    """Translate every sentence, degrading to no translation on failure.

    Translation is a nicety on this page, not its point: what is being practised
    is listening and repeating. So neither a dead translation service nor an
    exhausted limit takes the page down — the audio still plays, the line under
    the sentence is simply missing.

    Args:
        processed: The processed text.
        language: Target language code.
        allowed: Whether the hourly limit still permits paid translation.

    Returns:
        A pair of (translations, warning). The warning is empty on success, and
        the translations list is empty when it is not.
    """
    if not allowed:
        return [], "Лимит обработки текстов исчерпан, поэтому перевод не показан. Звук работает."

    sentences = [sentence.text for sentence in processed.sentences]

    try:
        return translate_sentences(sentences, language), ""
    except TranslationError as error:
        logger.error("Translation failed for %s sentences: %s", len(sentences), error)
        return [], "Перевод сейчас недоступен. Текст, пиньинь и озвучка работают."


def _speak_or_warn(
    processed: ProcessedText,
    translations: list[str],
) -> tuple[list[SpokenSentence], str]:
    """Speak a text, degrading to no audio on failure.

    The speech endpoint is unofficial and occasionally unavailable. When it is,
    the page still shows the text with pinyin and tone colours, which is most of
    the value — it just cannot play it.

    Args:
        processed: The processed text.
        translations: One translation per sentence, possibly empty.

    Returns:
        A pair of (sentences, warning). The warning is empty on success, and the
        sentence list is empty when it is not.
    """
    try:
        return speak_text(processed, translations), ""
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
        language: str = form.cleaned_data["lang"]

        try:
            processed = process_text(text)
        except TextTooLongError:
            # Форма проверяет ту же границу, так что сюда попасть трудно.
            logger.warning("Text passed form validation but exceeded the processing limit")
            return redirect("core:home")

        sentences = [sentence.text for sentence in processed.sentences]

        # Лимиты тратим только на платную работу. Текст, уже озвученный и
        # переведённый, никуда не ходит, и открывать его можно сколько угодно —
        # иначе библиотека была бы бесполезной.
        #
        # Счётчика два, потому что это две разные работы у двух разных служб:
        # синтез бесплатен и стережёт чужой эндпоинт, перевод стоит денег.
        if not has_cached_audio(sentences):
            limit = consume_audio_limit(request)

            if limit is not None and limit.exceeded:
                context = {"limit": limit, "user_limit": user_audio_limit()}
                return render(request, "core/rate_limited.html", context, status=429)

        # А вот исчерпанный лимит перевода страницу не закрывает: слушать и
        # повторять можно и без перевода, ради этого сюда и приходят.
        may_translate = True

        if not has_cached_translations(sentences, language):
            text_limit = consume_text_limit(request)
            may_translate = text_limit is None or not text_limit.exceeded

        translations, translation_warning = _translate_or_warn(
            processed, language, allowed=may_translate
        )
        spoken, speech_warning = _speak_or_warn(processed, translations)

        context: dict[str, Any] = {
            "sentences": spoken,
            "source_text": text,
            "language": language,
            # Предупреждений может быть два сразу: службы независимы, и упасть
            # они могут порознь.
            "warnings": [warning for warning in (speech_warning, translation_warning) if warning],
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
