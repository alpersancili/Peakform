from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "primary_goal",
        "experience_level",
        "activity_level",
        "onboarding_completed",
        "updated_at",
    )
    list_filter = ("primary_goal", "experience_level", "activity_level", "onboarding_completed")
    search_fields = ("user__username", "user__email")
