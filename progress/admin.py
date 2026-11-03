from django.contrib import admin

from .models import ProgressEntry


@admin.register(ProgressEntry)
class ProgressEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "weight_kg")
    list_filter = ("date",)
    search_fields = ("user__username",)
