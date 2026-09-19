from django.apps import AppConfig


class ShadowingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shadowing"
    label = "shadowing"
