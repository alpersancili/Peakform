from django.contrib import admin

from .models import ProgressEntry, ProgressPhoto


@admin.register(ProgressEntry)
class ProgressEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "weight_kg")
    list_filter = ("date",)
    search_fields = ("user__username",)


@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "created_at")
    list_filter = ("date",)
    search_fields = ("user__username",)
