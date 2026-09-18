from django.urls import path

from . import views

app_name = "reader"

urlpatterns = [
    path("", views.ReaderView.as_view(), name="read"),
    path("lookup/", views.LookupView.as_view(), name="lookup"),
]
