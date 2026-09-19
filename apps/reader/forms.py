"""Forms for the reader page."""

from django import forms
from django.conf import settings


class ReaderForm(forms.Form):
    """The text a user submits for reading.

    Validation lives here rather than in the view: the view stays thin, and the
    same form can later be reused by the library when it reopens a saved text.
    """

    text = forms.CharField(
        strip=True,
        error_messages={"required": "Вставьте китайский текст."},
    )
    lang = forms.CharField(required=False)

    # Заголовок и признак «текст уже в библиотеке» приходят скрытыми полями,
    # когда текст открывают из библиотеки. Оба только для показа: подделать их
    # можно, но ничего, кроме собственной надписи на кнопке, это не изменит.
    title = forms.CharField(required=False, max_length=120)
    saved = forms.BooleanField(required=False)
    saved_id = forms.IntegerField(required=False)
    status = forms.CharField(required=False, max_length=20)

    def clean_text(self) -> str:
        """Reject text longer than the limit, in the user's language."""
        text: str = self.cleaned_data["text"]

        if len(text) > settings.MAX_TEXT_LENGTH:
            raise forms.ValidationError(
                f"Слишком длинный текст: {len(text)} символов, максимум {settings.MAX_TEXT_LENGTH}."
            )

        return text

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
