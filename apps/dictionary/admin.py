from django.contrib import admin

from .models import DictionaryEntry


@admin.register(DictionaryEntry)
class DictionaryEntryAdmin(admin.ModelAdmin):
    list_display = ("simplified", "pinyin", "language", "source")
    list_filter = ("language", "source")
    search_fields = ("simplified", "traditional")
    # Словарь большой: точный подсчёт строк на каждой странице списка
    # заставляет PostgreSQL сканировать всю таблицу.
    show_full_result_count = False
