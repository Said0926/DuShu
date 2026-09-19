"""Thin wrappers over the allauth forms.

They exist to fix two cosmetic things the defaults get wrong for this project:
allauth's placeholders, which repeat the labels our templates already render,
and Django's password help text, which is a four-item list of validator
messages taller than the form it belongs to.
"""

from typing import Any

from allauth.account import forms as allauth_forms

# Django собирает подсказку к паролю из всех валидаторов сразу — получается
# четыре предложения списком, которые на карточке входа занимают больше места,
# чем сама форма. Здесь коротко о том же: полный текст всё равно покажется
# ошибкой, если правило нарушено.
PASSWORD_HELP_TEXT = "Минимум 8 символов, не только цифры и не слишком простой."


class FieldPolishMixin:
    """Tidies up the fields allauth builds.

    Two things: allauth fills every placeholder with the field's own label
    (its templates render fields unlabeled, ours do not), and Django's password
    help text is a four-item list that dwarfs the form.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # self.fields появляется в __init__ базовой формы, поэтому правим после super().
        for name, field in self.fields.items():  # type: ignore[attr-defined]
            field.widget.attrs.pop("placeholder", None)

            # password1 — это поле нового пароля во всех формах allauth: и при
            # регистрации, и при смене, и при восстановлении по ссылке.
            if name == "password1":
                field.help_text = PASSWORD_HELP_TEXT


class LoginForm(FieldPolishMixin, allauth_forms.LoginForm):
    """Sign-in form."""


class SignupForm(FieldPolishMixin, allauth_forms.SignupForm):
    """Registration form."""


class ResetPasswordForm(FieldPolishMixin, allauth_forms.ResetPasswordForm):
    """ "Send me a reset link" form."""


class ResetPasswordKeyForm(FieldPolishMixin, allauth_forms.ResetPasswordKeyForm):
    """New password, entered after following the link from the email."""


class ChangePasswordForm(FieldPolishMixin, allauth_forms.ChangePasswordForm):
    """Password change for a signed-in user."""


class SetPasswordForm(FieldPolishMixin, allauth_forms.SetPasswordForm):
    """First password for an account that has none — a Google-only account, later on."""
