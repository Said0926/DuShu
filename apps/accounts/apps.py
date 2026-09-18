from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # name — путь импорта, label — короткое имя, под которым app известен Django
    # (в AUTH_USER_MODEL, в именах таблиц, в миграциях).
    name = "apps.accounts"
    label = "accounts"
