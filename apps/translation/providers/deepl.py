"""DeepL implementation of the translation provider."""

import logging

import requests
from django.conf import settings

from apps.translation.exceptions import TranslationError

from .base import TranslationProvider

logger = logging.getLogger(__name__)

# Свободный тариф живёт на отдельном домене. Ключи платного тарифа
# заканчиваются не на ":fx", и для них адрес был бы api.deepl.com.
FREE_API_URL = "https://api-free.deepl.com/v2/translate"
PAID_API_URL = "https://api.deepl.com/v2/translate"

# Коды языков у DeepL свои: английский нужно уточнять до варианта, иначе
# сервис отвечает ошибкой о неоднозначности.
LANGUAGE_CODES = {
    "en": "EN-US",
    "ru": "RU",
}

REQUEST_TIMEOUT_SECONDS = 20


class DeepLProvider(TranslationProvider):
    """Translates through the DeepL API.

    Reads the key from ``settings.DEEPL_API_KEY``. The key is never logged: on
    failure only the status code and the sentence count are recorded.
    """

    def __init__(self) -> None:
        self.api_key: str = settings.DEEPL_API_KEY

        if not self.api_key:
            raise TranslationError(
                "DEEPL_API_KEY is empty. Set it in .env, or switch "
                "TRANSLATION_PROVIDER to the dummy provider."
            )

        # Ключи свободного тарифа оканчиваются на ":fx" — по этому признаку
        # DeepL сам предлагает выбирать адрес, отдельной настройки не нужно.
        self.api_url = FREE_API_URL if self.api_key.endswith(":fx") else PAID_API_URL

    def translate(self, sentences: list[str], target_lang: str) -> list[str]:
        """Translate a batch through the DeepL API.

        Args:
            sentences: Sentences to translate.
            target_lang: Project language code, mapped to DeepL's own.

        Returns:
            Translations in the same order as the input.

        Raises:
            TranslationError: On a network failure, a non-200 response, or a
                response whose length does not match the request.
        """
        if not sentences:
            return []

        # Неизвестный язык переводим как есть в верхнем регистре: у DeepL
        # большинство кодов совпадают, и добавление языка не требует правок здесь.
        deepl_language = LANGUAGE_CODES.get(target_lang, target_lang.upper())

        try:
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
                data={
                    "text": sentences,
                    "target_lang": deepl_language,
                    "source_lang": "ZH",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            logger.error("DeepL request failed for %s sentences: %s", len(sentences), error)
            raise TranslationError("Could not reach the translation service.") from error

        if response.status_code != requests.codes.ok:
            logger.error("DeepL returned %s for %s sentences", response.status_code, len(sentences))
            raise TranslationError(
                f"Translation service responded with status {response.status_code}."
            )

        try:
            payload = response.json()
            translations = [item["text"] for item in payload["translations"]]
        except (ValueError, KeyError, TypeError) as error:
            logger.error("Unexpected DeepL response shape: %s", error)
            raise TranslationError(
                "Translation service returned an unexpected response."
            ) from error

        # Проверяем длину явно: молчаливое расхождение сдвинуло бы переводы
        # относительно предложений, и страница показала бы чужой текст.
        if len(translations) != len(sentences):
            logger.error(
                "DeepL returned %s translations for %s sentences",
                len(translations),
                len(sentences),
            )
            raise TranslationError("Translation service returned a mismatched number of results.")

        return translations
