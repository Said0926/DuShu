"""Create the shared HSK collections.

Reference data, so a data migration rather than lazy creation: these five rows
are the same for everybody and exist before anyone signs up.

The levels are written out here instead of being read from ``models.HSK_LEVELS``
on purpose. A migration has to keep meaning what it meant the day it was
written; if it followed a constant, changing that constant would silently
rewrite history. Adding HSK 6 is therefore one more small migration like this.
"""

from django.db import migrations

LEVELS = (1, 2, 3, 4, 5)


def create_collections(apps, schema_editor) -> None:
    Collection = apps.get_model("library", "Collection")

    for level in LEVELS:
        Collection.objects.get_or_create(
            owner=None,
            hsk_level=level,
            defaults={"title": f"HSK {level}", "position": level},
        )


def remove_collections(apps, schema_editor) -> None:
    # Только те, что создала эта миграция. Тексты внутри не пострадают:
    # у связи стоит SET_NULL, они просто окажутся «Без подборки».
    Collection = apps.get_model("library", "Collection")
    Collection.objects.filter(owner=None, hsk_level__in=LEVELS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0002_collections_and_progress"),
    ]

    operations = [
        migrations.RunPython(create_collections, remove_collections),
    ]
