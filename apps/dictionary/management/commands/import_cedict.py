"""Import the CC-CEDICT chinese-english dictionary.

    docker compose exec web python manage.py import_cedict data/cedict.txt.gz

Dump: https://www.mdbg.net/chinese/dictionary?page=cc-cedict
Licence: CC BY-SA 4.0 — attribution is required and lives in the footer and README.
"""

from apps.dictionary.parsers.cedict import parse_file

from ._import_base import BaseImportCommand


class Command(BaseImportCommand):
    help = "Import a CC-CEDICT dump (chinese-english)."

    source = "cc-cedict"
    language = "en"
    parser = staticmethod(parse_file)
