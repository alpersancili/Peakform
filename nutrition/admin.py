from django.contrib import admin

from .models import Food, MealEntry, StepLog, WaterLog


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "serving_size", "serving_unit", "calories", "created_by")
    list_filter = ("created_by",)
    search_fields = ("name", "brand")


@admin.register(MealEntry)
class MealEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "food", "meal_category", "quantity", "calories", "logged_at")
    list_filter = ("meal_category",)
    search_fields = ("user__username", "food__name")


@admin.register(WaterLog)
class WaterLogAdmin(admin.ModelAdmin):
    list_display = ("user", "amount_ml", "logged_at")


@admin.register(StepLog)
class StepLogAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "step_count")
    list_filter = ("date",)
