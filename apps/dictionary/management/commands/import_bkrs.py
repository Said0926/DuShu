"""Import the БКРС chinese-russian dictionary.

    docker compose exec web python manage.py import_bkrs data/dabkrs.gz

Dump: https://bkrs.info/p47 — use the daily build, it needs no password.
Licence: the owners allow free use for any purpose and ask that the site be
credited, which the footer and README do.
"""

from apps.dictionary.parsers.bkrs import parse_file

from ._import_base import BaseImportCommand


class Command(BaseImportCommand):
    help = "Import a БКРС dump (chinese-russian)."

    source = "bkrs"
    language = "ru"
    parser = staticmethod(parse_file)
