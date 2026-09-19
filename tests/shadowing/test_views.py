"""Tests for the shadowing page."""

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import update_user_setting
from apps.translation.exceptions import TranslationError
from apps.tts.exceptions import TTSError

pytestmark = pytest.mark.django_db

LISTEN = reverse("shadowing:listen")


class TestShadowingView:
    def test_get_shows_the_empty_state_with_the_form(self, client: Client) -> None:
        """Following "Shadowing" in the navigation has to land somewhere usable."""
        response = client.get(reverse("shadowing:listen"))

        assert response.status_code == 200
        assert response.context["sentences"] == []
        assert 'name="text"' in response.content.decode()

    def test_post_renders_every_sentence(self, client: Client) -> None:
        response = client.post(reverse("shadowing:listen"), {"text": "我去。你好。"})

        assert response.status_code == 200
        assert len(response.context["sentences"]) == 2
        assert "shadowing/shadowing.html" in [template.name for template in response.templates]

    def test_the_first_sentence_starts_out_current(self, client: Client) -> None:
        """The page opens ready to play, so one sentence and one row are marked."""
        html = client.post(reverse("shadowing:listen"), {"text": "我去。你好。"}).content.decode()

        assert html.count("is-current") == 2

    def test_words_carry_their_timings_as_data_attributes(self, client: Client) -> None:
        """This is how the player gets them: no JSON, no second request."""
        html = client.post(reverse("shadowing:listen"), {"text": "我去。"}).content.decode()

        assert "data-start=" in html
        assert "data-end=" in html

    def test_a_sentence_carries_its_audio_and_length(self, client: Client) -> None:
        html = client.post(reverse("shadowing:listen"), {"text": "我去。"}).content.decode()

        assert 'data-audio="/media/' in html
        assert "data-duration=" in html

    def test_punctuation_gets_no_timing(self, client: Client) -> None:
        html = client.post(reverse("shadowing:listen"), {"text": "我去。"}).content.decode()

        assert '<span class="punct">。</span>' in html

    def test_the_title_from_the_library_is_shown(self, client: Client) -> None:
        response = client.post(
            reverse("shadowing:listen"),
            {
                "text": "我去。",
                "title": "Про банк",
                "saved": "1",
                "saved_id": "7",
                "status": "reading",
            },
        )

        assert "Про банк" in response.content.decode()

    def test_an_empty_text_goes_back_to_the_landing_page(self, client: Client) -> None:
        response = client.post(reverse("shadowing:listen"), {"text": ""})

        assert response.status_code == 302
        assert response.url == reverse("core:home")

    def test_too_long_a_text_is_refused(self, client: Client, settings) -> None:
        settings.MAX_TEXT_LENGTH = 10

        response = client.post(reverse("shadowing:listen"), {"text": "我去。" * 20})

        assert response.status_code == 302

    def test_the_translation_is_shown_under_the_sentence(self, client: Client) -> None:
        response = client.post(LISTEN, {"text": "我去。", "lang": "ru"})

        assert response.context["sentences"][0].translation
        assert 'class="reader__translation"' in response.content.decode()

    def test_the_translation_switch_is_offered(self, client: Client) -> None:
        html = client.post(LISTEN, {"text": "我去。", "lang": "ru"}).content.decode()

        assert 'data-setting="translation"' in html

    def test_a_user_who_turned_translation_off_gets_it_hidden(
        self, client: Client, user: User
    ) -> None:
        """One setting for both pages: switching it off in the reader switches it off here."""
        update_user_setting(user, "translation", False)
        client.force_login(user)

        html = client.post(LISTEN, {"text": "我去。", "lang": "ru"}).content.decode()

        # Прячет класс на контейнере, а не отсутствие разметки: переключатель
        # должен возвращать перевод обратно без перезагрузки страницы.
        assert "translation-off" in html
        assert 'class="reader__translation"' in html

    def test_an_unknown_language_falls_back_to_the_default(self, client: Client) -> None:
        """A broken hidden field must not cost the reader the page."""
        response = client.post(LISTEN, {"text": "我去。", "lang": "kz"})

        assert response.status_code == 200
        assert response.context["language"] == "ru"

    def test_a_failing_translation_still_leaves_the_audio(self, client: Client) -> None:
        """Two services: one dying must not cost the other."""
        with patch(
            "apps.shadowing.views.translate_sentences",
            side_effect=TranslationError("down"),
        ):
            response = client.post(LISTEN, {"text": "我去。", "lang": "ru"})

        assert response.status_code == 200
        assert response.context["sentences"]
        assert response.context["sentences"][0].translation == ""
        assert "Перевод сейчас недоступен" in response.content.decode()

    def test_a_failing_provider_still_renders_the_page(self, client: Client) -> None:
        """A dead speech service must cost the audio, not the page."""
        with patch("apps.shadowing.services.get_sentence_audio", side_effect=TTSError("down")):
            response = client.post(reverse("shadowing:listen"), {"text": "我去。"})

        assert response.status_code == 200
        assert response.context["sentences"] == []
        assert "Озвучка сейчас недоступна" in response.content.decode()


class TestAudioLimit:
    """The limit guards the speech endpoint, and only for work that reaches it."""

    def _submit(self, client: Client, number: int) -> int:
        # Каждому тесту нужны разные тексты: повторный отвечается из кэша
        # и намеренно ничего не стоит.
        return client.post(
            reverse("shadowing:listen"), {"text": f"这是第{number}句话。"}
        ).status_code

    def test_a_guest_runs_out_after_the_configured_number(self, client: Client) -> None:
        codes = [self._submit(client, number) for number in range(6)]

        assert codes == [200, 200, 200, 200, 200, 429]

    def test_a_signed_in_user_gets_further(self, client: Client, user: User) -> None:
        client.force_login(user)

        codes = [self._submit(client, number) for number in range(6)]

        assert codes == [200] * 6

    def test_opening_the_page_does_not_spend_the_limit(self, client: Client) -> None:
        for _ in range(10):
            client.get(reverse("shadowing:listen"))

        assert self._submit(client, 99) == 200

    def test_relistening_to_a_cached_text_is_free(self, client: Client) -> None:
        """Otherwise the library would be capped at a few opens an hour."""
        assert self._submit(client, 1) == 200

        for _ in range(10):
            assert self._submit(client, 1) == 200

    def test_a_fresh_text_spends_the_reading_limit_too(self, client: Client) -> None:
        """Translation is the paid work, and it is paid for wherever it is asked for.

        Before this page translated, listening left the reading counter alone.
        It cannot any more: otherwise shadowing would be a way around every
        limit that guards the translation budget.
        """
        for number in range(5):
            assert self._submit(client, number) == 200

        refused = client.post(reverse("reader:read"), {"text": "全新的句子。", "lang": "ru"})

        assert refused.status_code == 429

    def test_a_text_already_translated_costs_only_the_speech_limit(self, client: Client) -> None:
        """The reader already paid for this translation; listening must not pay twice."""
        shared = "这是共享的句子。"
        first = client.post(reverse("reader:read"), {"text": shared, "lang": "ru"})
        assert first.status_code == 200

        # Дотрачиваем счётчик обработки текстов ровно до предела.
        for number in range(4):
            client.post(reverse("reader:read"), {"text": f"这是第{number}句话。", "lang": "ru"})

        response = client.post(LISTEN, {"text": shared, "lang": "ru"})

        assert response.status_code == 200
        assert response.context["sentences"][0].translation

        # И предел действительно был достигнут: следующий новый текст не пройдёт.
        another = client.post(reverse("reader:read"), {"text": "再来一句。", "lang": "ru"})
        assert another.status_code == 429

    def test_an_exhausted_translation_limit_does_not_close_the_page(self, client: Client) -> None:
        """Listening and repeating works without a translation — that is the point here."""
        for number in range(5):
            client.post(reverse("reader:read"), {"text": f"这是第{number}句话。", "lang": "ru"})

        response = client.post(LISTEN, {"text": "还没有翻译的句子。"})

        assert response.status_code == 200
        assert response.context["sentences"]
        assert response.context["sentences"][0].translation == ""
        assert any("Лимит" in warning for warning in response.context["warnings"])
