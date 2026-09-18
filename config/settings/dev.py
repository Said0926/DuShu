"""Local development settings."""

from .base import *  # noqa: F403

DEBUG = True

# В разработке письма (подтверждение email, сброс пароля) печатаются в консоль,
# смотреть их можно через `docker compose logs -f web`.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Внутри Docker хост может быть любым, поэтому в разработке не ограничиваем.
ALLOWED_HOSTS = ["*"]
