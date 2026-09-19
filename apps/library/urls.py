from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.LibraryView.as_view(), name="list"),
    path("save/", views.SaveTextView.as_view(), name="save"),
    path("<int:pk>/rename/", views.RenameTextView.as_view(), name="rename"),
    path("<int:pk>/delete/", views.DeleteTextView.as_view(), name="delete"),
]
