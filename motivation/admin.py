from django.contrib import admin

from .models import Badge, Challenge, CompletedChallenge, UserBadge, XPEvent


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "criteria_type", "threshold")
    list_filter = ("criteria_type",)


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "earned_at")
    list_filter = ("badge",)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("name", "criteria_type", "target", "xp_reward")
    list_filter = ("criteria_type",)


@admin.register(CompletedChallenge)
class CompletedChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "challenge", "week_start", "xp_awarded")
    list_filter = ("challenge", "week_start")


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "reason", "created_at")
    list_filter = ("reason",)
    search_fields = ("user__username", "reason")
