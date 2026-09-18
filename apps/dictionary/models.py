from django.db import models


class DictionaryEntry(models.Model):
    """One word with its readings and definitions in one language.

    A word usually has several entries: one per language, sometimes several per
    language when the readings differ (行 as xíng and as háng are different
    entries, not one entry with two readings).

    This model is meant to be a stable reference point. The upcoming personal
    dictionary feature will point a ``UserWord`` at it with a foreign key, so its
    shape should not need to change when that lands.
    """

    simplified = models.CharField(max_length=128, db_index=True)
    traditional = models.CharField(max_length=128, blank=True)

    # Пиньинь с диакритикой: он и показывается в подсказке. Исходные форматы
    # словарей (yin2 hang2) приводятся к нему при импорте.
    pinyin = models.CharField(max_length=256, blank=True)

    # Обычный CharField без choices и без внешнего ключа: добавление нового языка
    # не должно требовать миграции. Допустимые значения живут в
    # settings.TRANSLATION_LANGUAGES и проверяются в сервисах и формах.
    language = models.CharField(max_length=8)

    # Из какого словаря пришла запись: cc-cedict, bkrs. Нужно и для атрибуции,
    # и чтобы можно было переимпортировать один источник, не трогая остальные.
    source = models.CharField(max_length=32)

    # Список значений. JSONField, потому что количество значений произвольное,
    # а отдельная таблица ради списка строк усложнила бы и модель, и выборку.
    definitions = models.JSONField(default=list)

    class Meta:
        constraints = [
            # Одно и то же слово с одним чтением из одного словаря не должно
            # задваиваться. Благодаря этому импорт можно запускать повторно.
            models.UniqueConstraint(
                fields=["simplified", "pinyin", "language", "source"],
                name="unique_dictionary_entry",
            ),
        ]
        indexes = [
            # Основной запрос подсказки: найти слово на выбранном языке.
            models.Index(fields=["simplified", "language"], name="dict_word_language_idx"),
        ]
        verbose_name_plural = "dictionary entries"

    def __str__(self) -> str:
        return f"{self.simplified} [{self.pinyin}] ({self.language})"
