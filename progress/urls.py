from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("<int:entry_id>/delete/", views.entry_delete, name="entry_delete"),
    path("photos/", views.photo_gallery, name="photos"),
    path("photos/<int:photo_id>/delete/", views.photo_delete, name="photo_delete"),
]
