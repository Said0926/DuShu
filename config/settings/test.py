"""Settings for the test suite."""

from .base import *  # noqa: F403

DEBUG = False

# MD5 вместо PBKDF2: хэширование пароля — самая дорогая операция в тестах с юзерами.
# Для тестов криптостойкость не нужна, а прогон ускоряется заметно.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Письма складываются в django.core.mail.outbox, наружу ничего не уходит.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

ALLOWED_HOSTS = ["testserver", "localhost"]

# Заглушка вместо реального провайдера. Без этого любой тест, который дёргает
# перевод и забыл подменить настройку, сделает платный запрос к DeepL ключом
# из .env разработчика.
TRANSLATION_PROVIDER = "apps.translation.providers.dummy.DummyProvider"
DEEPL_API_KEY = "test-key-not-used:fx"

# То же и для озвучки. Здесь причина не в деньгах — edge-tts бесплатен, — а в
# том, что тест, случайно дошедший до настоящего провайдера, стал бы зависеть от
# сети и от чужого сервиса: он начал бы падать по причинам, не связанным с кодом.
TTS_PROVIDER = "apps.tts.providers.dummy.DummyTTSProvider"
