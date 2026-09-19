from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.LibraryView.as_view(), name="list"),
    path("save/", views.SaveTextView.as_view(), name="save"),
    path("collections/create/", views.CreateCollectionView.as_view(), name="collection-create"),
    path(
        "collections/<int:pk>/rename/",
        views.RenameCollectionView.as_view(),
        name="collection-rename",
    ),
    path(
        "collections/<int:pk>/delete/",
        views.DeleteCollectionView.as_view(),
        name="collection-delete",
    ),
    path("<int:pk>/rename/", views.RenameTextView.as_view(), name="rename"),
    path("<int:pk>/move/", views.MoveTextView.as_view(), name="move"),
    path("<int:pk>/status/", views.SetStatusView.as_view(), name="status"),
    path("<int:pk>/delete/", views.DeleteTextView.as_view(), name="delete"),
]
