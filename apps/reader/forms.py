"""Forms for the reader page."""

from django import forms
from django.conf import settings

from apps.core.forms import TextSubmissionForm


class ReaderForm(TextSubmissionForm):
    """The text a user submits for reading.

    Adds the translation language to the shared submission form: the reader is
    the only page that translates, so shadowing has no use for this field.
    """

    lang = forms.CharField(required=False)

    def clean_lang(self) -> str:
        """Fall back to the default language instead of failing.

        The language arrives from a hidden field, so a bad value means a broken
        page rather than a user mistake. Showing the text in the default
        language beats showing an error.
        """
        language: str = self.cleaned_data.get("lang") or ""

        if language not in settings.TRANSLATION_LANGUAGES:
            return settings.DEFAULT_TRANSLATION_LANGUAGE

        return language
