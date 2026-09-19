from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from .models import User


class UserCreationForm(AdminUserCreationForm):
    """Form for adding a user from the admin.

    Django's version asks for a username, which this model does not have, so the
    field list is declared again.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin pages for the email-identified user."""

    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "first_name", "last_name")

    # Наборы полей переписаны целиком, а не поправлены: стандартные построены
    # вокруг username, и «вычесть» его из них нельзя.
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("first_name", "last_name")}),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
