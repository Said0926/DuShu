"""Tests for the shadowing page."""

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.tts.exceptions import TTSError

pytestmark = pytest.mark.django_db


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

    def test_the_reader_limit_is_counted_separately(self, client: Client) -> None:
        """Two groups, two counters: listening must not eat the reading limit."""
        for number in range(6):
            self._submit(client, number)

        assert (
            client.post(reverse("reader:read"), {"text": "你好。", "lang": "ru"}).status_code == 200
        )
