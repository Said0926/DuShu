"""Texts a user has saved to read again."""

import hashlib

from django.conf import settings
from django.db import models
from django.db.models import Q

# Насколько длинным может быть автоматический заголовок. Китайский текст
# плотный: 40 символов — это обычно целое предложение, узнать текст легко.
TITLE_LENGTH = 40

# Длина названия подборки, которое пользователь придумывает сам.
COLLECTION_TITLE_LENGTH = 60

# Уровни HSK, под которые заводятся общие подборки. Список, а не «пять штук»
# в коде: в новом стандарте HSK 3.0 уровней девять, в старом шесть, и добавить
# следующий должно быть одной строкой плюс маленькой миграцией данных.
HSK_LEVELS = (1, 2, 3, 4, 5)

# Предел на свои подборки. Не ради экономии места, а чтобы список не превращался
# в свалку, по которой невозможно найти нужное.
MAX_COLLECTIONS_PER_USER = 50


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


class Collection(models.Model):
    """A folder of texts.

    Two kinds share one table, told apart by the owner:

    - a shared HSK level has no owner and is visible to everyone;
    - a personal collection belongs to one user.

    One table rather than two because everything else about them is the same:
    they hold texts, they are listed together, and nothing downstream cares
    which kind a text came from.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=COLLECTION_TITLE_LENGTH)

    # Заполнен только у общих подборок HSK. По нему же их и узнают: уровень
    # есть — значит подборка системная и переименованию не подлежит.
    hsk_level = models.PositiveSmallIntegerField(null=True, blank=True)

    # Уровни HSK занимают позиции 1…9, пользовательские идут после них.
    position = models.PositiveSmallIntegerField(default=100)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "title"],
                name="unique_collection_title_per_owner",
            ),
            # Частичное ограничение: ровно одна общая подборка на уровень.
            # Обычного UniqueConstraint по owner + title тут мало — в SQL два
            # NULL считаются разными значениями, и общие подборки под него
            # не попадают вовсе.
            models.UniqueConstraint(
                fields=["hsk_level"],
                condition=Q(owner__isnull=True),
                name="unique_hsk_collection",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_system(self) -> bool:
        """Whether this is a shared collection nobody may rename or delete."""
        return self.owner_id is None


class SavedText(models.Model):
    """One text in a user's library.

    The text is stored as it was pasted, not as it was processed: processing is
    cheap and deterministic, while translations are already cached separately by
    sentence. Reopening therefore costs nothing.
    """

    # Пустой владелец — каталожный текст: он лежит в общей подборке HSK
    # и виден всем. У сохранённого пользователем владелец есть всегда.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_texts",
        null=True,
        blank=True,
    )

    # SET_NULL, а не CASCADE: удаление подборки не должно уносить с собой
    # тексты. Они просто оказываются «Без подборки».
    collection = models.ForeignKey(
        Collection,
        on_delete=models.SET_NULL,
        related_name="texts",
        null=True,
        blank=True,
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
            # То же самое для каталожных текстов: у них владельца нет, а два
            # NULL в SQL не равны друг другу, поэтому ограничение выше их
            # не ловит и один текст можно было бы завести в каталог дважды.
            models.UniqueConstraint(
                fields=["content_hash"],
                condition=Q(owner__isnull=True),
                name="unique_catalog_text",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class ReadingProgress(models.Model):
    """How far one user got with one text.

    Separate from the text because a catalog text is one row for everyone: a
    status field on it would be one status for everyone too.

    A missing row means "not started". Statuses are only written once somebody
    changes one, which keeps the table proportional to activity rather than to
    the number of texts times the number of users.
    """

    class Status(models.TextChoices):
        # choices здесь уместны, в отличие от языка перевода: новый статус —
        # это всё равно изменение кода, потому что его надо где-то показать
        # и как-то обработать.
        NEW = "new", "Не прочтён"
        READING = "reading", "Читается"
        DONE = "done", "Прочитан"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_progress",
    )
    text = models.ForeignKey(
        SavedText,
        on_delete=models.CASCADE,
        related_name="progress",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "text"],
                name="unique_progress_per_text",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.text.title}: {self.get_status_display()}"
