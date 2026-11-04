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
    path("records/", views.personal_records, name="personal_records"),
    path("exercises/", views.exercise_library, name="exercise_library"),
    path("exercises/<slug:slug>/", views.exercise_detail, name="exercise_detail"),
    path("programs/", views.program_list, name="program_list"),
    path("programs/<slug:slug>/<str:difficulty>/", views.program_detail, name="program_detail"),
    path("programs/<slug:slug>/<str:difficulty>/start/", views.program_start, name="program_start"),
    path("recovery/", views.recovery_note_add, name="recovery_note_add"),
]
