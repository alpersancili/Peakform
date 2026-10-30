from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.db import models

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


class PostType(models.TextChoices):
    MEAL_RECIPE = "meal_recipe", "Meal or recipe"
    NUTRITION_TIP = "nutrition_tip", "Nutrition tip"
    WORKOUT_PROGRAM = "workout_program", "Workout program"
    TRAINING_PHOTO = "training_photo", "Training photo"
    SKILL_ACHIEVEMENT = "skill_achievement", "Skill achievement"
    PROGRESS = "progress", "Progress update"
    QUESTION = "question", "Question or discussion"
    GENERAL = "general", "General"


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    post_type = models.CharField(max_length=20, choices=PostType.choices, default=PostType.GENERAL)
    body = models.TextField(max_length=2000)
    image = models.FileField(
        upload_to="community_posts/%Y/%m/",
        blank=True,
        validators=[FileExtensionValidator(ALLOWED_IMAGE_EXTENSIONS)],
    )
    is_removed = models.BooleanField(default=False, help_text="Hidden by moderation; content is kept for records.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author}: {self.body[:40]}"

    @property
    def is_edited(self):
        return (self.updated_at - self.created_at).total_seconds() > 5

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def comment_count(self):
        return self.comments.filter(is_removed=False).count()


class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="post_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self):
        return f"{self.user} likes {self.post_id}"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField(max_length=1000)
    is_removed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} on post {self.post_id}: {self.body[:40]}"


class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_links")
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("follower", "following")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")), name="community_follow_no_self_follow"
            )
        ]

    def __str__(self):
        return f"{self.follower} -> {self.following}"


class ReportReason(models.TextChoices):
    SPAM = "spam", "Spam"
    HARASSMENT = "harassment", "Harassment or abuse"
    MISLEADING = "misleading", "Misleading content"
    INAPPROPRIATE_IMAGE = "inappropriate_image", "Inappropriate image"
    OTHER = "other", "Other"


class ReportStatus(models.TextChoices):
    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    DISMISSED = "dismissed", "Dismissed"


class Report(models.Model):
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="filed_reports")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=30, choices=ReportReason.choices)
    details = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=ReportStatus.choices, default=ReportStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_reason_display()} report by {self.reporter}"
