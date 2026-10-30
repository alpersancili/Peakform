from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("", views.plan_overview, name="plan_overview"),
    path("plan/generate/", views.plan_generate, name="plan_generate"),
    path("sessions/start/<int:day_id>/", views.session_start, name="session_start"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("sessions/<int:session_id>/log/<int:exercise_id>/", views.log_set, name="log_set"),
    path("sessions/<int:session_id>/complete/", views.session_complete, name="session_complete"),
    path("sessions/history/", views.session_history, name="session_history"),
    path("recovery/", views.recovery_note_add, name="recovery_note_add"),
]
