from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("", views.plan_overview, name="plan_overview"),
    path("plan/generate/", views.plan_generate, name="plan_generate"),
    path("sessions/start/<int:day_id>/", views.session_start, name="session_start"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("sessions/<int:session_id>/log/<int:exercise_id>/", views.log_set, name="log_set"),
    path(
        "sessions/<int:session_id>/exercises/<int:plan_exercise_id>/substitute/",
        views.substitute_exercise,
        name="substitute_exercise",
    ),
    path("sessions/<int:session_id>/complete/", views.session_complete, name="session_complete"),
    path("sessions/<int:session_id>/summary/", views.session_summary, name="session_summary"),
    path("sessions/history/", views.session_history, name="session_history"),
    path("records/", views.personal_records, name="personal_records"),
    path("exercises/", views.exercise_library, name="exercise_library"),
    path("exercises/<slug:slug>/", views.exercise_detail, name="exercise_detail"),
    path("programs/", views.program_list, name="program_list"),
    path("programs/<slug:slug>/<str:difficulty>/", views.program_detail, name="program_detail"),
    path("programs/<slug:slug>/<str:difficulty>/start/", views.program_start, name="program_start"),
    path("recovery/", views.recovery_note_add, name="recovery_note_add"),
    path("mobility/", views.mobility_library, name="mobility_library"),
    path("skills/", views.skill_tree_overview, name="skill_tree_overview"),
    path("skills/<int:exercise_id>/toggle/", views.skill_milestone_toggle, name="skill_milestone_toggle"),
    path("routines/", views.routine_list, name="routine_list"),
    path("routines/new/", views.routine_create, name="routine_create"),
    path("routines/<int:routine_id>/", views.routine_detail, name="routine_detail"),
    path("routines/<int:routine_id>/exercises/add/", views.routine_exercise_add, name="routine_exercise_add"),
    path(
        "routines/<int:routine_id>/exercises/<int:routine_exercise_id>/remove/",
        views.routine_exercise_remove,
        name="routine_exercise_remove",
    ),
    path("routines/<int:routine_id>/start/", views.routine_start, name="routine_start"),
    path("routines/<int:routine_id>/rate/", views.routine_rate, name="routine_rate"),
    path("routines/<int:routine_id>/report/", views.routine_report, name="routine_report"),
    path("routines/<int:routine_id>/delete/", views.routine_delete, name="routine_delete"),
]
