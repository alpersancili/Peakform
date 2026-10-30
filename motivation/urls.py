from django.urls import path

from . import views

app_name = "motivation"

urlpatterns = [
    path("", views.badges_list, name="badges_list"),
]
