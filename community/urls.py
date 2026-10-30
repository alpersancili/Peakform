from django.urls import path

from . import views

app_name = "community"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("following/", views.following_feed, name="following_feed"),
    path("posts/<int:post_id>/", views.post_detail, name="post_detail"),
    path("posts/<int:post_id>/edit/", views.post_edit, name="post_edit"),
    path("posts/<int:post_id>/delete/", views.post_delete, name="post_delete"),
    path("posts/<int:post_id>/like/", views.post_like_toggle, name="post_like_toggle"),
    path("comments/<int:comment_id>/delete/", views.comment_delete, name="comment_delete"),
    path("report/<str:kind>/<int:object_id>/", views.report_create, name="report_create"),
    path("u/<str:username>/", views.profile, name="profile"),
    path("u/<str:username>/follow/", views.follow_toggle, name="follow_toggle"),
]
