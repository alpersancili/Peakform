from django.urls import path

from . import views

app_name = "coach"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("clear/", views.clear_conversation, name="clear_conversation"),
]
