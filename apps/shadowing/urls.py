"""URLs of the shadowing page."""

from django.urls import path

from . import views

app_name = "shadowing"

urlpatterns = [
    path("", views.ShadowingView.as_view(), name="listen"),
]
