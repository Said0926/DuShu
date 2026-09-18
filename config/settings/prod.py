"""Production settings.

Проект пока не деплоится; модуль существует, чтобы разделение окружений было
заложено с самого начала и продовые настройки не приходилось вспоминать потом.
"""

from .base import *  # noqa: F403

DEBUG = False

# --- security ---

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000  # один год
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# За реверс-прокси Django узнаёт об исходном https только из этого заголовка.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- static files ---

# Хэш в имени файла позволяет кэшировать статику навсегда: при изменении
# содержимого меняется имя, и браузер скачивает новую версию.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}
