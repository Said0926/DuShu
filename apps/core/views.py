from typing import Any

from django.conf import settings
from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Landing page: hero, the text input card and a short feature overview."""

    template_name = "core/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["max_text_length"] = settings.MAX_TEXT_LENGTH
        context["translation_languages"] = settings.TRANSLATION_LANGUAGES
        context["default_language"] = settings.DEFAULT_TRANSLATION_LANGUAGE
        return context


class ComingSoonView(TemplateView):
    """Placeholder for pages that later stages will implement.

    Keeps the navigation and the landing form pointing at real URLs instead of
    dead links while ``reader``, ``shadowing`` and ``library`` do not exist yet.
    """

    template_name = "core/coming_soon.html"
