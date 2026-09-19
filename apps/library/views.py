"""Views for the library.

All of them are thin: parse the request, call a service, answer. Ownership is
checked inside the services, which take the owner and filter by them, so a view
cannot reach somebody else's text even by forgetting to check.
"""

import json
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from apps.chinese.exceptions import TextTooLongError

from .exceptions import EmptyTextError, InvalidTitleError
from .models import SavedText
from .services import delete_text, get_text, list_texts, rename_text, save_text


def _error(message: str, code: str, status: int) -> JsonResponse:
    """Build an error answer in the project's response shape."""
    return JsonResponse({"data": None, "error": code, "message": message}, status=status)


class LibraryView(LoginRequiredMixin, TemplateView):
    """The list of texts the signed-in user saved."""

    template_name = "library/list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["texts"] = list_texts(self.request.user)
        context["active_nav"] = "library"
        return context


class SaveTextView(View):
    """Saves the text currently open in the reader.

    Answers in JSON because the reader calls it with ``fetch``. A normal form
    POST would reload the reading page, which means processing the text again —
    the reader would charge a limit for the act of saving, and the reading
    position in a long text would be lost.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_authenticated:
            return _error("Нужно войти в аккаунт.", "not_authenticated", 403)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return _error("Тело запроса — не JSON.", "invalid_json", 400)

        if not isinstance(payload, dict):
            return _error("Ожидался объект с полем content.", "invalid_payload", 400)

        try:
            text, created = save_text(request.user, payload.get("content", ""))
        except (EmptyTextError, TextTooLongError) as error:
            return _error(str(error), "invalid_text", 400)

        return JsonResponse(
            {
                "data": {"title": text.title, "created": created},
                "error": None,
                "message": "Сохранено." if created else "Этот текст уже в библиотеке.",
            }
        )


class RenameTextView(LoginRequiredMixin, View):
    """Gives a saved text a new title."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            rename_text(request.user, pk, request.POST.get("title", ""))
        except SavedText.DoesNotExist as error:
            # 404, а не 403: 403 подтвердил бы, что такой текст существует
            # и принадлежит кому-то другому.
            raise Http404("Текст не найден.") from error
        except InvalidTitleError as error:
            messages.error(request, str(error))

        return redirect("library:list")


class DeleteTextView(LoginRequiredMixin, View):
    """Deletes a saved text after asking.

    The confirmation is a page rather than a browser dialog, so it works with
    JavaScript switched off and can be styled like the rest of the site.
    """

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            text = get_text(request.user, pk)
        except SavedText.DoesNotExist as error:
            raise Http404("Текст не найден.") from error

        return render(request, "library/confirm_delete.html", {"text": text})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            delete_text(request.user, pk)
        except SavedText.DoesNotExist as error:
            raise Http404("Текст не найден.") from error

        messages.success(request, "Текст удалён.")
        return redirect("library:list")
