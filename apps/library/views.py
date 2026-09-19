"""Views for the library.

All of them are thin: parse the request, call a service, answer. Visibility and
ownership are checked inside the services, which take the user and filter by
them, so a view cannot reach past those rules by forgetting a check.
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

from .exceptions import (
    CollectionLimitError,
    EmptyTextError,
    InvalidStatusError,
    InvalidTitleError,
    SystemCollectionError,
)
from .models import Collection, SavedText
from .services import (
    create_collection,
    delete_collection,
    delete_text,
    get_owned_collection,
    get_owned_text,
    library_groups,
    move_text,
    rename_collection,
    rename_text,
    save_text,
    set_status,
    visible_collections,
)


def _error(message: str, code: str, status: int) -> JsonResponse:
    """Build an error answer in the project's response shape."""
    return JsonResponse({"data": None, "error": code, "message": message}, status=status)


def _not_found(error: Exception) -> Http404:
    """Turn a missing row into a 404.

    Never a 403: that would confirm the row exists and belongs to somebody else.
    """
    return Http404("Не найдено.")


class LibraryView(LoginRequiredMixin, TemplateView):
    """The library page: collections with their texts."""

    template_name = "library/list.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["groups"] = library_groups(self.request.user)
        # Для селекта «переместить в…» на каждой карточке.
        context["collections"] = visible_collections(self.request.user)
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


class SetStatusView(View):
    """Records how far the reader got with a text.

    JSON, because the same control is used in two places — on a card in the
    library and in the reader's header — and neither should reload the page to
    move a switch.
    """

    def post(self, request: HttpRequest, pk: int) -> JsonResponse:
        if not request.user.is_authenticated:
            return _error("Нужно войти в аккаунт.", "not_authenticated", 403)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return _error("Тело запроса — не JSON.", "invalid_json", 400)

        if not isinstance(payload, dict):
            return _error("Ожидался объект с полем status.", "invalid_payload", 400)

        try:
            progress = set_status(request.user, pk, payload.get("status", ""))
        except SavedText.DoesNotExist:
            return _error("Текст не найден.", "not_found", 404)
        except InvalidStatusError as error:
            return _error(str(error), "invalid_status", 400)

        return JsonResponse({"data": {"status": progress.status}, "error": None, "message": ""})


class RenameTextView(LoginRequiredMixin, View):
    """Gives a saved text a new title."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            rename_text(request.user, pk, request.POST.get("title", ""))
        except SavedText.DoesNotExist as error:
            raise _not_found(error) from error
        except InvalidTitleError as error:
            messages.error(request, str(error))

        return redirect("library:list")


class MoveTextView(LoginRequiredMixin, View):
    """Puts a text into a collection, or takes it out of one."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        raw = request.POST.get("collection", "")
        # Пустое значение в селекте — это «Без подборки», а не ошибка.
        collection_pk = int(raw) if raw.isdigit() else None

        try:
            move_text(request.user, pk, collection_pk)
        except (SavedText.DoesNotExist, Collection.DoesNotExist) as error:
            raise _not_found(error) from error

        return redirect("library:list")


class DeleteTextView(LoginRequiredMixin, View):
    """Deletes a saved text after asking.

    The confirmation is a page rather than a browser dialog, so it works with
    JavaScript switched off and can be styled like the rest of the site.
    """

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            text = get_owned_text(request.user, pk)
        except SavedText.DoesNotExist as error:
            raise _not_found(error) from error

        return render(request, "library/confirm_delete.html", {"text": text})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            delete_text(request.user, pk)
        except SavedText.DoesNotExist as error:
            raise _not_found(error) from error

        messages.success(request, "Текст удалён.")
        return redirect("library:list")


class CreateCollectionView(LoginRequiredMixin, View):
    """Creates a personal collection."""

    def post(self, request: HttpRequest) -> HttpResponse:
        try:
            create_collection(request.user, request.POST.get("title", ""))
        except (InvalidTitleError, CollectionLimitError) as error:
            messages.error(request, str(error))

        return redirect("library:list")


class RenameCollectionView(LoginRequiredMixin, View):
    """Renames a personal collection."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            rename_collection(request.user, pk, request.POST.get("title", ""))
        except Collection.DoesNotExist as error:
            raise _not_found(error) from error
        except (InvalidTitleError, SystemCollectionError) as error:
            messages.error(request, str(error))

        return redirect("library:list")


class DeleteCollectionView(LoginRequiredMixin, View):
    """Deletes a personal collection, asking first.

    The confirmation says plainly that the texts survive: deleting a folder is
    only safe to do quickly if you know it will not take a month of reading
    with it.
    """

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            collection = get_owned_collection(request.user, pk)
        except Collection.DoesNotExist as error:
            raise _not_found(error) from error
        except SystemCollectionError as error:
            messages.error(request, str(error))
            return redirect("library:list")

        return render(request, "library/confirm_delete_collection.html", {"collection": collection})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        try:
            delete_collection(request.user, pk)
        except Collection.DoesNotExist as error:
            raise _not_found(error) from error
        except SystemCollectionError as error:
            messages.error(request, str(error))
            return redirect("library:list")

        messages.success(request, "Подборка удалена, тексты из неё остались.")
        return redirect("library:list")
