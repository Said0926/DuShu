"""Thin wrappers over the allauth forms.

allauth fills every widget's ``placeholder`` with the field's own label, because
its default templates render fields without labels. This project renders labels,
so the placeholder would only repeat what is already on screen — one line of the
same text twice in every field.
"""

from typing import Any

from allauth.account import forms as allauth_forms


class NoPlaceholderMixin:
    """Drops the placeholder attribute from every field of the form."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # self.fields появляется в __init__ базовой формы, поэтому чистим после super().
        for field in self.fields.values():  # type: ignore[attr-defined]
            field.widget.attrs.pop("placeholder", None)


class LoginForm(NoPlaceholderMixin, allauth_forms.LoginForm):
    """Sign-in form."""


class SignupForm(NoPlaceholderMixin, allauth_forms.SignupForm):
    """Registration form."""


class ResetPasswordForm(NoPlaceholderMixin, allauth_forms.ResetPasswordForm):
    """ "Send me a reset link" form."""


class ResetPasswordKeyForm(NoPlaceholderMixin, allauth_forms.ResetPasswordKeyForm):
    """New password, entered after following the link from the email."""


class ChangePasswordForm(NoPlaceholderMixin, allauth_forms.ChangePasswordForm):
    """Password change for a signed-in user."""


class SetPasswordForm(NoPlaceholderMixin, allauth_forms.SetPasswordForm):
    """First password for an account that has none — a Google-only account, later on."""
