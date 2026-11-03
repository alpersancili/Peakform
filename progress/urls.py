from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("<int:entry_id>/delete/", views.entry_delete, name="entry_delete"),
]
