from django.conf import settings
from django.db import models


class Sex(models.TextChoices):
    FEMALE = "female", "Female"
    MALE = "male", "Male"
    UNSPECIFIED = "unspecified", "Prefer not to say"


class UnitsPreference(models.TextChoices):
    METRIC = "metric", "Metric (cm, kg)"
    IMPERIAL = "imperial", "Imperial (ft/in, lb)"


class ActivityLevel(models.TextChoices):
    SEDENTARY = "sedentary", "Sedentary (little or no exercise)"
    LIGHT = "light", "Lightly active (1-3 days/week)"
    MODERATE = "moderate", "Moderately active (3-5 days/week)"
    ACTIVE = "active", "Active (6-7 days/week)"
    VERY_ACTIVE = "very_active", "Very active (physical job or 2x/day training)"


class ExperienceLevel(models.TextChoices):
    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"


class PrimaryGoal(models.TextChoices):
    FAT_LOSS = "fat_loss", "Fat loss"
    MUSCLE_GAIN = "muscle_gain", "Muscle gain"
    STRENGTH = "strength", "Strength"
    ENDURANCE = "endurance", "Endurance"
    SKILLS = "skills", "Calisthenics skills"
    FLEXIBILITY = "flexibility", "Mobility and flexibility"
    GENERAL_FITNESS = "general_fitness", "General fitness"


class Equipment(models.TextChoices):
    NONE = "none", "No equipment (bodyweight only)"
    PULL_UP_BAR = "pull_up_bar", "Pull-up bar"
    RINGS = "rings", "Gymnastic rings"
    PARALLETTES = "parallettes", "Parallettes"
    DIP_BARS = "dip_bars", "Dip bars"
    RESISTANCE_BANDS = "resistance_bands", "Resistance bands"
    FULL_GYM = "full_gym", "Full gym access"


class DietaryPreference(models.TextChoices):
    NONE = "none", "No restrictions"
    VEGETARIAN = "vegetarian", "Vegetarian"
    VEGAN = "vegan", "Vegan"
    PESCATARIAN = "pescatarian", "Pescatarian"
    HALAL = "halal", "Halal"
    KOSHER = "kosher", "Kosher"
    GLUTEN_FREE = "gluten_free", "Gluten-free"
    DAIRY_FREE = "dairy_free", "Dairy-free"
    NUT_ALLERGY = "nut_allergy", "Nut allergy"


class UserProfile(models.Model):
    """Fitness profile, preferences, and goals for a registered user.

    Body measurements are stored canonically in metric units regardless of
    the user's display preference, so downstream calculations (BMI, BMR,
    TDEE) never need to guess which unit a stored value is in.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )

    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=20, choices=Sex.choices, default=Sex.UNSPECIFIED)
    height_cm = models.FloatField(null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    preferred_units = models.CharField(
        max_length=10, choices=UnitsPreference.choices, default=UnitsPreference.METRIC
    )

    activity_level = models.CharField(
        max_length=20, choices=ActivityLevel.choices, default=ActivityLevel.MODERATE
    )
    experience_level = models.CharField(
        max_length=20, choices=ExperienceLevel.choices, default=ExperienceLevel.BEGINNER
    )
    primary_goal = models.CharField(
        max_length=20, choices=PrimaryGoal.choices, default=PrimaryGoal.GENERAL_FITNESS
    )

    training_days_per_week = models.PositiveSmallIntegerField(default=3)
    session_duration_minutes = models.PositiveSmallIntegerField(default=45)
    equipment = models.JSONField(default=list, blank=True)
    dietary_preferences = models.JSONField(default=list, blank=True)

    country = models.CharField(max_length=100, blank=True)

    onboarding_completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        from datetime import date

        today = date.today()
        years = today.year - self.date_of_birth.year
        had_birthday = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return years if had_birthday else years - 1
