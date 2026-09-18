"""Tests for translation providers.

The DeepL provider is tested against mocks: tests must not depend on a paid
service being reachable, and a failing test should point at our code.
"""

from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings

from apps.translation.exceptions import TranslationError
from apps.translation.providers.deepl import FREE_API_URL, PAID_API_URL, DeepLProvider
from apps.translation.providers.dummy import DummyProvider


def _response(payload: dict, status: int = 200) -> Mock:
    """Build a fake requests response."""
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    return response


class TestDummyProvider:
    def test_returns_input_unchanged(self) -> None:
        provider = DummyProvider()

        assert provider.translate(["你好", "再见"], "ru") == ["你好", "再见"]

    def test_empty_input(self) -> None:
        assert DummyProvider().translate([], "ru") == []


class TestDeepLProvider:
    # autouse-фикстура вместо @override_settings на классе: pytest-класс
    # не наследует SimpleTestCase, и декоратор к нему неприменим.
    @pytest.fixture(autouse=True)
    def _api_key(self, settings: pytest.FixtureRequest) -> None:
        settings.DEEPL_API_KEY = "test-key:fx"

    def test_translates_a_batch(self) -> None:
        payload = {"translations": [{"text": "привет"}, {"text": "пока"}]}

        with patch(
            "apps.translation.providers.deepl.requests.post", return_value=_response(payload)
        ):
            result = DeepLProvider().translate(["你好", "再见"], "ru")

        assert result == ["привет", "пока"]

    def test_sends_every_sentence_and_the_language(self) -> None:
        payload = {"translations": [{"text": "привет"}]}

        with patch(
            "apps.translation.providers.deepl.requests.post", return_value=_response(payload)
        ) as post:
            DeepLProvider().translate(["你好"], "ru")

        sent = post.call_args.kwargs["data"]
        assert sent["text"] == ["你好"]
        assert sent["target_lang"] == "RU"
        assert sent["source_lang"] == "ZH"

    def test_english_is_sent_as_a_specific_variant(self) -> None:
        """Plain EN makes DeepL complain about ambiguity."""
        payload = {"translations": [{"text": "hello"}]}

        with patch(
            "apps.translation.providers.deepl.requests.post", return_value=_response(payload)
        ) as post:
            DeepLProvider().translate(["你好"], "en")

        assert post.call_args.kwargs["data"]["target_lang"] == "EN-US"

    def test_unknown_language_is_passed_through_uppercased(self) -> None:
        """Adding a language to settings should not require touching the provider."""
        payload = {"translations": [{"text": "hallo"}]}

        with patch(
            "apps.translation.providers.deepl.requests.post", return_value=_response(payload)
        ) as post:
            DeepLProvider().translate(["你好"], "de")

        assert post.call_args.kwargs["data"]["target_lang"] == "DE"

    def test_empty_input_makes_no_request(self) -> None:
        with patch("apps.translation.providers.deepl.requests.post") as post:
            assert DeepLProvider().translate([], "ru") == []

        post.assert_not_called()

    def test_free_key_uses_the_free_endpoint(self) -> None:
        assert DeepLProvider().api_url == FREE_API_URL

    @override_settings(DEEPL_API_KEY="paid-key-without-suffix")
    def test_paid_key_uses_the_paid_endpoint(self) -> None:
        assert DeepLProvider().api_url == PAID_API_URL

    @override_settings(DEEPL_API_KEY="")
    def test_missing_key_fails_with_a_readable_message(self) -> None:
        with pytest.raises(TranslationError, match="DEEPL_API_KEY"):
            DeepLProvider()

    def test_network_failure_becomes_a_translation_error(self) -> None:
        with patch(
            "apps.translation.providers.deepl.requests.post",
            side_effect=requests.ConnectionError("no route"),
        ):
            with pytest.raises(TranslationError):
                DeepLProvider().translate(["你好"], "ru")

    @pytest.mark.parametrize("status", [403, 429, 456, 500])
    def test_error_status_becomes_a_translation_error(self, status: int) -> None:
        with patch(
            "apps.translation.providers.deepl.requests.post",
            return_value=_response({}, status=status),
        ):
            with pytest.raises(TranslationError, match=str(status)):
                DeepLProvider().translate(["你好"], "ru")

    def test_unexpected_response_shape_is_caught(self) -> None:
        with patch(
            "apps.translation.providers.deepl.requests.post",
            return_value=_response({"unexpected": True}),
        ):
            with pytest.raises(TranslationError):
                DeepLProvider().translate(["你好"], "ru")

    def test_mismatched_count_is_rejected(self) -> None:
        """Silently accepting this would shift translations onto wrong sentences."""
        payload = {"translations": [{"text": "привет"}]}

        with patch(
            "apps.translation.providers.deepl.requests.post", return_value=_response(payload)
        ):
            with pytest.raises(TranslationError, match="mismatched"):
                DeepLProvider().translate(["你好", "再见"], "ru")

    def test_api_key_is_not_logged_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """A key leaking into logs is a key that has to be rotated."""
        with patch(
            "apps.translation.providers.deepl.requests.post",
            return_value=_response({}, status=403),
        ):
            with pytest.raises(TranslationError):
                DeepLProvider().translate(["你好"], "ru")

        assert "test-key" not in caplog.text
