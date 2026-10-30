from django.conf import settings
from django.db import models
from django.utils import timezone


class MealCategory(models.TextChoices):
    BREAKFAST = "breakfast", "Breakfast"
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"
    SNACK = "snack", "Snack"


class Food(models.Model):
    """A food item with nutrition values per one defined serving.

    `created_by` is null for the shared/curated catalog and set for foods
    a user adds themselves, which only they can see and log.
    """

    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True)
    serving_size = models.FloatField(default=100)
    serving_unit = models.CharField(max_length=20, default="g")

    calories = models.FloatField()
    protein_g = models.FloatField(default=0)
    carbs_g = models.FloatField(default=0)
    fat_g = models.FloatField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_foods",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.name} ({self.serving_size:g}{self.serving_unit})"


class MealEntry(models.Model):
    """A logged food diary entry.

    Nutrition values are snapshotted from the Food record at save time so a
    later edit to a Food's nutrition data does not silently rewrite a
    user's historical diary.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meal_entries")
    food = models.ForeignKey(Food, on_delete=models.PROTECT, related_name="meal_entries")
    meal_category = models.CharField(max_length=10, choices=MealCategory.choices)
    quantity = models.FloatField(default=1.0, help_text="Multiplier of the food's defined serving size.")

    calories = models.FloatField()
    protein_g = models.FloatField()
    carbs_g = models.FloatField()
    fat_g = models.FloatField()

    logged_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-logged_at"]
        verbose_name_plural = "meal entries"

    def __str__(self):
        return f"{self.user}: {self.food.name} ({self.meal_category})"

    def snapshot_from_food(self):
        self.calories = self.food.calories * self.quantity
        self.protein_g = self.food.protein_g * self.quantity
        self.carbs_g = self.food.carbs_g * self.quantity
        self.fat_g = self.food.fat_g * self.quantity

    def save(self, *args, **kwargs):
        self.snapshot_from_food()
        super().save(*args, **kwargs)


class WaterLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="water_logs")
    amount_ml = models.PositiveIntegerField()
    logged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-logged_at"]

    def __str__(self):
        return f"{self.user}: {self.amount_ml}ml"


class StepLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="step_logs")
    date = models.DateField(default=timezone.localdate)
    step_count = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("user", "date")

    def __str__(self):
        return f"{self.user}: {self.step_count} steps on {self.date}"
