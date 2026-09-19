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

THIRD_PARTY_APPS = [
    # allauth — общая часть; account — вход по email и паролю;
    # socialaccount и google — вход через Google.
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.chinese",
    "apps.dictionary",
    "apps.translation",
    "apps.reader",
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
    # Требование allauth: должен стоять после AuthenticationMiddleware.
    # Он проверяет, что сессия не «переехала» на другого пользователя,
    # и обслуживает многошаговые потоки вроде подтверждения email.
    "allauth.account.middleware.AccountMiddleware",
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

AUTHENTICATION_BACKENDS = [
    # Первый нужен админке, второй — входу по email и (позже) через Google.
    # Django пробует их по очереди, пока один не вернёт пользователя.
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --- allauth ---

# django.contrib.sites намеренно не подключён. Он нужен allauth только чтобы
# построить абсолютный URL в письме, когда запроса под рукой нет; в обычном
# потоке домен берётся из request. Без sites на одну сущность меньше, и ссылки
# в письмах ведут на реальный хост, а не на example.com из фикстуры.

# Куда LoginRequiredMixin отправляет анонимного посетителя. Значение по умолчанию
# совпадает с этим адресом, но написать его явно дешевле, чем однажды искать,
# почему редирект уехал не туда.
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Вход и регистрация — по email. Имена настроек новые: ACCOUNT_AUTHENTICATION_METHOD
# и ACCOUNT_EMAIL_REQUIRED объявлены устаревшими в allauth 65.4 и 65.5.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]

# У нашей модели username нет вообще, и allauth нужно сказать об этом прямо:
# иначе он попытается его заполнить и упадёт.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# optional: письмо с подтверждением уходит, но войти можно сразу. При mandatory
# каждую новую учётку пришлось бы подтверждать ссылкой из логов контейнера —
# для разработки это лишнее трение. Значение меняется одной строкой.
ACCOUNT_EMAIL_VERIFICATION = "optional"

# Свои формы нужны ровно для одного: убрать placeholder'ы, которые allauth
# заполняет теми же словами, что и подписи полей. Его шаблоны рисуют поля
# без подписей, наши — с подписями, и текст двоился бы в каждом поле.
# --- вход через Google ---

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")

SOCIALACCOUNT_PROVIDERS: dict[str, dict] = {
    "google": {
        "SCOPE": ["profile", "email"],
        # online: refresh token не запрашиваем. Он нужен, чтобы ходить в API
        # Google от имени пользователя, а нам нужен только факт входа.
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# Ключи читаем из .env, а не из таблицы SocialApp в админке: секреты не уезжают
# в базу, и после пересоздания базы ничего не нужно заводить руками.
#
# Секцию APP добавляем только когда ключи заданы: именно по её наличию allauth
# считает провайдер настроенным. Без ключей он не попадёт в список провайдеров,
# и кнопка «Войти через Google» просто не отрисуется — вместо того чтобы вести
# на страницу с ошибкой.
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
        "client_id": GOOGLE_CLIENT_ID,
        "secret": GOOGLE_CLIENT_SECRET,
        "key": "",
    }

# Аккаунт, созданный через Google, письмо с подтверждением не получает:
# Google адрес уже проверил.
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"

# Что происходит, если человек сначала зарегистрировался по email и паролю,
# а потом нажал «Войти через Google» с тем же адресом. По умолчанию allauth
# упирается в «этот email занят» и предлагает тупик. С этими двумя настройками
# он вместо этого пускает в существующий аккаунт и привязывает к нему Google.
#
# По умолчанию оба выключены намеренно: провайдер, который врёт про
# подтверждённость адреса, вошёл бы в любой чужой аккаунт. Включать их можно
# только для провайдеров, которым доверяешь полностью. Google такой; если
# появится второй провайдер, это решение нужно пересмотреть.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

ACCOUNT_FORMS = {
    "login": "apps.accounts.forms.LoginForm",
    "signup": "apps.accounts.forms.SignupForm",
    "reset_password": "apps.accounts.forms.ResetPasswordForm",
    "reset_password_from_key": "apps.accounts.forms.ResetPasswordKeyForm",
    "change_password": "apps.accounts.forms.ChangePasswordForm",
    "set_password": "apps.accounts.forms.SetPasswordForm",
}

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

# Провайдер перевода задаётся путём к классу: подменить его можно настройкой,
# не трогая ни сервисы, ни views. DummyProvider возвращает исходный текст и
# позволяет работать без ключа и без обращений к платному API.
TRANSLATION_PROVIDER = env(
    "TRANSLATION_PROVIDER",
    default="apps.translation.providers.deepl.DeepLProvider",
)
DEEPL_API_KEY = env("DEEPL_API_KEY", default="")

# Сколько предложений отправлять в одном запросе к провайдеру.
# У DeepL предел — 50 текстов на запрос.
TRANSLATION_BATCH_SIZE = 50

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
