"""Forms shared by the features that take a submitted text.

Both "Чтение" and "Shadowing" are opened by posting a text, and both can be
opened from the library — which hands them the title and the reading status in
hidden fields. That contract, and the length limit, are the same for both, so
they live here rather than being written twice. ``core`` is where the shared
frame lives; a form in ``reader`` imported by ``shadowing`` would make one
feature depend on another.
"""

from django import forms
from django.conf import settings


class TextSubmissionForm(forms.Form):
    """A text submitted for reading or for shadowing."""

    text = forms.CharField(
        strip=True,
        error_messages={"required": "Вставьте китайский текст."},
    )

    # Язык перевода нужен обеим страницам: «Чтение» печатает перевод под каждым
    # предложением, «Shadowing» — под текущим. Приезжает скрытым полем отовсюду,
    # где текст отправляют: с главной, из «Чтения» и из библиотеки.
    lang = forms.CharField(required=False)

    # Заголовок и признак «текст уже в библиотеке» приходят скрытыми полями,
    # когда текст открывают из библиотеки. Все они только для показа: подделать
    # их можно, но ничего, кроме собственной надписи на кнопке, это не изменит.
    title = forms.CharField(required=False, max_length=120)
    saved = forms.BooleanField(required=False)
    saved_id = forms.IntegerField(required=False)
    status = forms.CharField(required=False, max_length=20)

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

    def clean_text(self) -> str:
        """Reject text longer than the limit, in the user's language."""
        text: str = self.cleaned_data["text"]

        if len(text) > settings.MAX_TEXT_LENGTH:
            raise forms.ValidationError(
                f"Слишком длинный текст: {len(text)} символов, максимум {settings.MAX_TEXT_LENGTH}."
            )

        return text
