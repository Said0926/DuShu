"""Admin for the library.

This is how the shared HSK levels get their texts: a catalog text is a
``SavedText`` with no owner, put into a collection that also has no owner.
Nothing in the site lets anyone create one, and that is on purpose — shared
content is edited by whoever runs the project, not by its readers.
"""

from django.contrib import admin

from .models import Collection, ReadingProgress, SavedText


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "hsk_level", "position", "text_count")
    list_filter = ("hsk_level",)
    search_fields = ("title",)

    @admin.display(description="текстов")
    def text_count(self, collection: Collection) -> int:
        return collection.texts.count()


@admin.register(SavedText)
class SavedTextAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "collection", "created_at")
    list_filter = ("collection",)
    search_fields = ("title", "content")
    # Заголовок и отпечаток считаются при сохранении в сервисе, но каталожные
    # тексты заводятся здесь, поэтому оба поля нужно видеть и править руками.
    readonly_fields = ("created_at",)


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "text", "status", "updated_at")
    list_filter = ("status",)
