"""Texts a user has saved to read again."""

import hashlib

from django.conf import settings
from django.db import models

# Насколько длинным может быть автоматический заголовок. Китайский текст
# плотный: 40 символов — это обычно целое предложение, узнать текст легко.
TITLE_LENGTH = 40


def content_hash(content: str) -> str:
    """Return the fingerprint used to recognise an already saved text.

    Hashing rather than comparing the text itself: a saved text can be thousands
    of characters, and a 64-character column indexes far better than an
    unbounded one.

    Whitespace around the text is stripped first, so the same text pasted twice
    with a stray newline still counts as the same text.
    """
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def make_title(content: str) -> str:
    """Build a readable title from the beginning of a text.

    Args:
        content: The whole text.

    Returns:
        The first line, cut to :data:`TITLE_LENGTH` with an ellipsis when it
        does not fit. Never empty for a non-empty text.
    """
    # Берём первую строку, а не первые N символов текста: если человек вставил
    # стихотворение, заголовок из двух склеенных строк читался бы как каша.
    first_line = content.strip().splitlines()[0].strip() if content.strip() else ""

    if len(first_line) <= TITLE_LENGTH:
        return first_line

    return f"{first_line[:TITLE_LENGTH].rstrip()}…"


class SavedText(models.Model):
    """One text in a user's library.

    The text is stored as it was pasted, not as it was processed: processing is
    cheap and deterministic, while translations are already cached separately by
    sentence. Reopening therefore costs nothing.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_texts",
    )

    title = models.CharField(max_length=TITLE_LENGTH + 1)
    content = models.TextField()

    # Отпечаток содержимого. По нему же работает ограничение уникальности:
    # сохранить один и тот же текст дважды нельзя.
    content_hash = models.CharField(max_length=64, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Свежие сверху: библиотека читается сверху вниз, и последний
        # сохранённый текст почти всегда тот, к которому вернутся.
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "content_hash"],
                name="unique_text_per_owner",
            ),
        ]

    def __str__(self) -> str:
        return self.title
