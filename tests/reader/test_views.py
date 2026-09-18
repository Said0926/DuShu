"""Tests for the reader page and the tooltip endpoint."""

import json
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.dictionary.parsers import ParsedEntry
from apps.dictionary.services import import_entries
from apps.translation.exceptions import TranslationError

pytestmark = pytest.mark.django_db

DUMMY = "apps.translation.providers.dummy.DummyProvider"


@pytest.fixture
def dictionary() -> None:
    import_entries(
        [
            ParsedEntry("银行", "銀行", "yín háng", ["банк"]),
            ParsedEntry("猫", "貓", "māo", ["кот, кошка"]),
            ParsedEntry("狗", "狗", "gǒu", ["собака"]),
        ],
        language="ru",
        source="test",
    )


class TestReaderView:
    @pytest.fixture(autouse=True)
    def _dummy_provider(self, settings: pytest.FixtureRequest) -> None:
        settings.TRANSLATION_PROVIDER = DUMMY

    def test_get_sends_users_to_the_form(self, client: Client) -> None:
        response = client.get(reverse("reader:read"))

        assert response.status_code == 302
        assert response.url == reverse("core:home")

    def test_post_renders_the_text(self, client: Client) -> None:
        response = client.post(reverse("reader:read"), {"text": "我打算去银行。", "lang": "ru"})

        assert response.status_code == 200
        assert "reader/reader.html" in [template.name for template in response.templates]

    def test_words_carry_data_attributes(self, client: Client) -> None:
        """The tooltip and the future "add to my dictionary" button rely on them."""
        response = client.post(reverse("reader:read"), {"text": "银行", "lang": "ru"})
        html = response.content.decode()

        assert 'data-word="银行"' in html
        assert 'data-pinyin="yín háng"' in html

    def test_tone_classes_are_on_the_hanzi(self, client: Client) -> None:
        response = client.post(reverse("reader:read"), {"text": "你好", "lang": "ru"})
        html = response.content.decode()

        assert '<span class="tone-3">你</span>' in html

    def test_punctuation_is_outside_the_word(self, client: Client) -> None:
        response = client.post(reverse("reader:read"), {"text": "你好。", "lang": "ru"})
        html = response.content.decode()

        assert '<span class="punct">。</span>' in html

    def test_every_sentence_gets_a_translation(self, client: Client) -> None:
        response = client.post(reverse("reader:read"), {"text": "第一句。第二句。", "lang": "ru"})

        assert len(response.context["rows"]) == 2
        assert all(translation for _, translation in response.context["rows"])

    def test_empty_text_returns_to_the_form(self, client: Client) -> None:
        response = client.post(reverse("reader:read"), {"text": "", "lang": "ru"})

        assert response.status_code == 302

    def test_too_long_text_is_rejected_with_a_message(self, client: Client) -> None:
        with override_settings(MAX_TEXT_LENGTH=10):
            response = client.post(
                reverse("reader:read"), {"text": "一" * 11, "lang": "ru"}, follow=True
            )

        messages = [str(message) for message in response.context["messages"]]
        assert any("Слишком длинный текст" in message for message in messages)

    def test_unknown_language_falls_back_to_the_default(self, client: Client) -> None:
        """A broken hidden field should not break the page."""
        response = client.post(reverse("reader:read"), {"text": "你好。", "lang": "klingon"})

        assert response.context["language"] == "ru"

    def test_translation_failure_still_renders_the_text(self, client: Client) -> None:
        """Pinyin, tones and tooltips are most of the value; they must survive."""
        with patch(
            "apps.reader.views.translate_sentences",
            side_effect=TranslationError("service down"),
        ):
            response = client.post(reverse("reader:read"), {"text": "你好。", "lang": "ru"})

        assert response.status_code == 200
        assert response.context["warning"]
        assert 'data-word="你好"' in response.content.decode()


class TestLookupView:
    def test_finds_a_word(self, client: Client, dictionary: None) -> None:
        response = client.get(reverse("reader:lookup"), {"word": "银行", "lang": "ru"})
        payload = json.loads(response.content)

        assert response.status_code == 200
        assert payload["error"] is None
        assert payload["data"]["found"] is True
        assert payload["data"]["entries"][0]["definitions"] == ["банк"]

    def test_falls_back_to_characters(self, client: Client, dictionary: None) -> None:
        response = client.get(reverse("reader:lookup"), {"word": "猫狗", "lang": "ru"})
        payload = json.loads(response.content)

        assert payload["data"]["found"] is False
        assert [item["character"] for item in payload["data"]["characters"]] == ["猫", "狗"]

    def test_unknown_word_returns_an_empty_result(self, client: Client, dictionary: None) -> None:
        response = client.get(reverse("reader:lookup"), {"word": "龘", "lang": "ru"})
        payload = json.loads(response.content)

        assert response.status_code == 200
        assert payload["data"]["found"] is False
        assert payload["data"]["characters"] == []

    def test_missing_word_is_a_bad_request(self, client: Client) -> None:
        response = client.get(reverse("reader:lookup"), {"lang": "ru"})

        assert response.status_code == 400
        assert json.loads(response.content)["error"] == "missing_word"

    def test_unknown_language_is_a_bad_request(self, client: Client) -> None:
        response = client.get(reverse("reader:lookup"), {"word": "猫", "lang": "klingon"})

        assert response.status_code == 400
        assert json.loads(response.content)["error"] == "unknown_language"

    def test_response_shape_is_consistent(self, client: Client, dictionary: None) -> None:
        """Every endpoint answers with the same {data, error, message} envelope."""
        response = client.get(reverse("reader:lookup"), {"word": "猫", "lang": "ru"})

        assert set(json.loads(response.content)) == {"data", "error", "message"}
