from django.db import models


class SentenceTranslation(models.Model):
    """One sentence translated into one language.

    Translation is the only paid part of reading a text, so every result is kept.
    Reopening a saved text, switching a setting or sharing the same paragraph
    between texts then costs nothing.
    """

    source_hash = models.CharField(max_length=64, db_index=True)
    target_language = models.CharField(max_length=8)

    # Исходный текст храним рядом с хэшем: он нужен для отладки и для того,
    # чтобы понять содержимое кэша, не пересчитывая хэши.
    source_text = models.TextField()
    translated_text = models.TextField()

    # Каким провайдером получен перевод. Позволяет выборочно сбросить кэш,
    # если провайдер сменится или окажется плохого качества.
    provider = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_hash", "target_language"],
                name="unique_sentence_translation",
            ),
        ]
        indexes = [
            models.Index(fields=["source_hash", "target_language"], name="translation_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_text[:30]} -> {self.target_language}"
