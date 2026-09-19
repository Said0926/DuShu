"""Root URL configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # allauth приносит сразу весь набор: вход, регистрация, выход,
    # сброс пароля, подтверждение email.
    path("accounts/", include("allauth.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("reader/", include("apps.reader.urls")),
    path("shadowing/", include("apps.shadowing.urls")),
    path("library/", include("apps.library.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Кэш озвучки. В проде это работа nginx: он же отдаёт Range-запросы,
    # без которых не работает перемотка внутри предложения.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
