"""Settings for the test suite."""

from .base import *  # noqa: F403

DEBUG = False

# MD5 вместо PBKDF2: хэширование пароля — самая дорогая операция в тестах с юзерами.
# Для тестов криптостойкость не нужна, а прогон ускоряется заметно.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Письма складываются в django.core.mail.outbox, наружу ничего не уходит.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

ALLOWED_HOSTS = ["testserver", "localhost"]
