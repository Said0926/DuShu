from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("soon/", views.ComingSoonView.as_view(), name="coming-soon"),
]
