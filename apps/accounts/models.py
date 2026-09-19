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


# Размер, который показывает переключатель, пока пользователь ничего не выбрал.
DEFAULT_FONT_SIZE = "md"

# Пауза после предложения: "auto" — полторы его длительности, "fixed" — две
# секунды независимо от длины (DESIGN.md §7).
PAUSE_MODES = ("auto", "fixed")
DEFAULT_PAUSE_MODE = "auto"

# Сколько раз повторить предложение перед переходом к следующему.
MIN_REPEATS = 1
MAX_REPEATS = 5
DEFAULT_REPEATS = 1


class UserSettings(models.Model):
    """Reading preferences of one user.

    A guest keeps the same values in ``localStorage``; signing in moves them
    here, so they follow the person between devices and browsers. A new setting
    is added as one more field with a default, which leaves existing rows
    working — that is the whole reason this is a table of columns rather than
    one JSON blob.

    The row is created on demand by ``services.get_user_settings``, not by a
    signal on user creation.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")

    show_pinyin = models.BooleanField(default=True)
    show_tones = models.BooleanField(default=True)
    show_translation = models.BooleanField(default=True)
    show_hints = models.BooleanField(default=True)

    # Пустая строка означает «размер не выбирали». Это не то же самое, что "md":
    # без явного выбора на узком экране действует уменьшенный кегль из
    # медиазапроса (.reader:not([data-size]) в reader.css), а записанное "md"
    # его бы перебило и текст на телефоне остался бы великоват.
    font_size = models.CharField(max_length=2, blank=True, default="")

    # Пустая строка означает «взять settings.DEFAULT_TRANSLATION_LANGUAGE».
    # Записать сюда сам язык по умолчанию нельзя: значение запеклось бы
    # в миграцию, и смена языка по умолчанию потребовала бы новой. choices нет
    # намеренно — по правилу проекта новый язык не должен стоить миграции.
    language = models.CharField(max_length=8, blank=True, default="")

    # --- настройки Shadowing ---

    # choices нет по той же причине, что у языка: список режимов проверяется
    # в сервисе, а не в схеме, и третий режим не должен стоить миграции.
    pause_mode = models.CharField(max_length=8, default=DEFAULT_PAUSE_MODE)
    repeats = models.PositiveSmallIntegerField(default=DEFAULT_REPEATS)

    class Meta:
        verbose_name = "настройки пользователя"
        verbose_name_plural = "настройки пользователей"

    def __str__(self) -> str:
        return f"Настройки {self.user.email}"
