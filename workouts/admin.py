from django.contrib import admin

from .models import (
    Exercise,
    ExerciseLog,
    RecoveryNote,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "movement_type", "difficulty_level")
    list_filter = ("category", "movement_type", "difficulty_level")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class WorkoutPlanDayInline(admin.TabularInline):
    model = WorkoutPlanDay
    extra = 0


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ("user", "goal", "experience_level", "training_days_per_week", "is_active", "created_at")
    list_filter = ("goal", "is_active")
    inlines = [WorkoutPlanDayInline]


@admin.register(WorkoutPlanExercise)
class WorkoutPlanExerciseAdmin(admin.ModelAdmin):
    list_display = ("plan_day", "exercise", "target_sets", "target_reps", "target_hold_seconds")


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "status", "plan_day")
    list_filter = ("status",)


@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = ("session", "exercise", "set_number", "reps", "hold_seconds", "effort_rpe")


@admin.register(RecoveryNote)
class RecoveryNoteAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "sleep_quality", "soreness", "fatigue")
