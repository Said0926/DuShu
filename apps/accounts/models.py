"""The project user and its manager."""

from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Creates users identified by their email address.

    Django's own ``UserManager`` requires a username, so it cannot be reused
    once that field is gone.
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        """Create and save a regular user.

        Args:
            email: Login identifier, required.
            password: Raw password. ``None`` produces an unusable password,
                which is what a Google-only account gets.
            **extra_fields: Any other field of the model.

        Returns:
            The saved user.

        Raises:
            ValueError: If no email was given.
        """
        if not email:
            raise ValueError("A user needs an email address.")

        # normalize_email опускает регистр домена: Mail.RU и mail.ru — один и тот
        # же адрес, но uniqueness в базе об этом не знает и пропустил бы оба.
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: Any
    ) -> "User":
        """Create and save a superuser. This is what ``createsuperuser`` calls."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        # Флаги можно передать и явно, поэтому их проверяем, а не просто ставим:
        # суперпользователь без прав тихо не работал бы, и причину пришлось бы искать.
        if extra_fields["is_staff"] is not True:
            raise ValueError("A superuser needs is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser needs is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Project user, identified by email address.

    ``username`` is removed rather than left unused: a field nobody fills still
    has to be worked around in every form, fixture and admin page. Email is the
    identifier both login methods actually provide — the password form and,
    later, Google sign-in.

    A one-to-one ``UserSettings`` record holds the reader preferences; it is
    created on demand rather than by a signal.
    """

    username = None
    # Тот же msgid, что у поля в AbstractUser, поэтому русский перевод подхватится
    # из готового каталога Django, и в админке подпись останется человеческой.
    email = models.EmailField(_("email address"), unique=True)

    USERNAME_FIELD = "email"
    # Дополнительные вопросы createsuperuser. Пустой список: email и пароль
    # команда спрашивает сама, по USERNAME_FIELD.
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email
