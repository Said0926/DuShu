"""Settings shared by every environment.

Environment-specific modules (``dev``, ``prod``, ``test``) import everything from here
and override what differs.
"""

from pathlib import Path

import environ

# config/settings/base.py -> config/settings -> config -> <project root>
BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
)

# .env читаем, только если файл существует: в CI переменные приходят из окружения напрямую.
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# --- applications ---

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Сторонние пакеты (allauth, ratelimit) подключаются на этапе 6.
THIRD_PARTY_APPS: list[str] = []

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- database ---

# env.db() разбирает DATABASE_URL вида postgres://user:password@host:port/dbname.
DATABASES = {"default": env.db()}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- auth ---

# Кастомная модель пользователя задана до первой миграции: поменять её позже
# без пересоздания базы практически невозможно.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- i18n ---

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# --- static files ---

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- проектные настройки ---

# Максимальная длина текста, который пользователь отправляет на обработку.
# Это же число показывает счётчик символов на главной.
MAX_TEXT_LENGTH = 5000

# Языки перевода. Добавление нового языка = одна строка здесь; ни модели,
# ни миграции, ни логика сервисов при этом не меняются.
TRANSLATION_LANGUAGES = {
    "ru": "Русский",
    "en": "English",
}
DEFAULT_TRANSLATION_LANGUAGE = "ru"

# --- logging ---

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} — {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Логи наших приложений — отдельным логгером, чтобы ошибки внешних API
        # было видно среди служебных сообщений Django.
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
