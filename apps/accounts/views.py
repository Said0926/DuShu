"""Views for the accounts app."""

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .exceptions import InvalidSettingValueError, UnknownSettingError
from .services import update_user_setting


class ProfileView(LoginRequiredMixin, TemplateView):
    """The signed-in user's own account page.

    ``LoginRequiredMixin`` sends anonymous visitors to ``settings.LOGIN_URL`` and
    brings them back here afterwards, so the check is not repeated by hand. The
    template reads everything it needs from ``user``, which the auth context
    processor already provides.
    """

    template_name = "accounts/profile.html"


def _error(message: str, code: str, status: int) -> JsonResponse:
    """Build an error answer in the project's response shape."""
    return JsonResponse({"data": None, "error": code, "message": message}, status=status)


class SettingsUpdateView(View):
    """Saves one reading setting for the signed-in user.

    Deliberately not ``LoginRequiredMixin``: that redirects to the login page,
    and ``fetch`` would receive a 302 followed by a page of HTML instead of an
    answer it can read. An endpoint that answers in JSON should also refuse in
    JSON.
    """

    def post(self, request: HttpRequest) -> JsonResponse:
        if not request.user.is_authenticated:
            return _error("Нужно войти в аккаунт.", "not_authenticated", 403)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return _error("Тело запроса — не JSON.", "invalid_json", 400)

        if not isinstance(payload, dict):
            return _error("Ожидался объект с полями name и value.", "invalid_payload", 400)

        try:
            update_user_setting(request.user, payload.get("name"), payload.get("value"))
        except (UnknownSettingError, InvalidSettingValueError) as error:
            return _error(str(error), "invalid_setting", 400)

        return JsonResponse({"data": None, "error": None, "message": ""})
