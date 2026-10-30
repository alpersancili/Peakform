from django.urls import path

from . import views

app_name = "nutrition"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("foods/", views.food_search, name="food_search"),
    path("foods/custom/add/", views.custom_food_add, name="custom_food_add"),
    path("meals/add/<int:food_id>/", views.add_meal_entry, name="add_meal_entry"),
    path("meals/<int:entry_id>/edit/", views.meal_entry_edit, name="meal_entry_edit"),
    path("meals/<int:entry_id>/delete/", views.meal_entry_delete, name="meal_entry_delete"),
    path("water/add/", views.water_add, name="water_add"),
    path("water/<int:log_id>/delete/", views.water_delete, name="water_delete"),
    path("steps/set/", views.step_set, name="step_set"),
    path("ai/", views.ai_food_log, name="ai_food_log"),
    path("ai/review/", views.ai_food_log_review, name="ai_food_log_review"),
]
