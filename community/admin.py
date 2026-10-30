from django.contrib import admin

from .models import Comment, Follow, Like, Post, Report


@admin.action(description="Hide selected content (mark removed)")
def mark_removed(modeladmin, request, queryset):
    queryset.update(is_removed=True)


@admin.action(description="Restore selected content (unmark removed)")
def mark_restored(modeladmin, request, queryset):
    queryset.update(is_removed=False)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post_type", "is_removed", "created_at")
    list_filter = ("post_type", "is_removed")
    search_fields = ("body", "author__username")
    actions = [mark_removed, mark_restored]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "is_removed", "created_at")
    list_filter = ("is_removed",)
    search_fields = ("body", "author__username")
    actions = [mark_removed, mark_restored]


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "following", "created_at")


@admin.action(description="Mark selected reports resolved")
def mark_resolved(modeladmin, request, queryset):
    queryset.update(status="resolved")


@admin.action(description="Mark selected reports dismissed")
def mark_dismissed(modeladmin, request, queryset):
    queryset.update(status="dismissed")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "content_type", "object_id", "reason", "status", "created_at")
    list_filter = ("status", "reason", "content_type")
    actions = [mark_resolved, mark_dismissed]
