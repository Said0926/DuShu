from django.db import models


class SentenceAudio(models.Model):
    """One sentence spoken by one voice.

    Cached for the same reason translations are, plus one of its own: the speech
    service is unofficial and occasionally unavailable. Once a sentence is here
    it keeps working even when the service does not.

    The speed is deliberately not part of the key. Audio is always synthesized at
    normal speed and the player changes ``playbackRate``, so a reader switching
    between 0.5x and 1.5x waits for nothing and the cache stays single.
    """

    source_hash = models.CharField(max_length=64, db_index=True)

    # Голос — часть ключа: сменив его в настройках, мы не должны получить из
    # кэша прежнее звучание.
    voice = models.CharField(max_length=64)

    # Исходный текст рядом с хэшем: нужен для отладки и чтобы понять содержимое
    # кэша, не пересчитывая хэши.
    source_text = models.TextField()

    # max_length больше стандартных 100: в имя файла попадают 64 символа хэша,
    # имя голоса и каталог с датой. На умолчании Django молча обрезает имя и
    # дописывает случайный суффикс — файл перестаёт быть узнаваемым.
    audio = models.FileField(upload_to="tts/%Y/%m/", max_length=200)

    # Полная длительность файла, включая тишину в конце. Это не конец последнего
    # тайминга: речь замолкает раньше, чем заканчивается файл, и дорожка
    # прогресса должна показывать именно файл.
    duration_ms = models.PositiveIntegerField()

    # Караоке-разметка: список словарей вида
    # {"start": 0, "end": 2, "start_ms": 125, "end_ms": 500}, где start и end —
    # срез предложения. См. apps/tts/alignment.py.
    timings = models.JSONField(default=list)

    # Каким провайдером озвучено. Позволяет выборочно сбросить кэш: тишина от
    # DummyTTSProvider, оставшаяся с работы без сети, иначе будет проигрываться
    # вечно, потому что попадание в кэш до провайдера не доходит.
    provider = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_hash", "voice"],
                name="unique_sentence_audio",
            ),
        ]
        indexes = [
            models.Index(fields=["source_hash", "voice"], name="audio_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.source_text[:30]} ({self.voice})"
