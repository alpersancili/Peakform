"""Deterministic nutrition calculations: BMI, BMR, TDEE, and daily targets.

These are estimates based on established formulas, not exact measurements
or medical advice. All assumptions are documented inline so they stay
auditable as the product evolves.
"""

from dataclasses import dataclass

from accounts.models import ActivityLevel, PrimaryGoal, Sex

# Mifflin-St Jeor activity multipliers (TDEE = BMR * multiplier).
ACTIVITY_MULTIPLIERS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}

# Calorie adjustment from maintenance (TDEE) per goal. Fat loss uses a
# moderate deficit (~0.45 kg/week); gain goals use a modest surplus to
# favor lean mass over fat gain.
GOAL_CALORIE_ADJUSTMENT = {
    PrimaryGoal.FAT_LOSS: -500,
    PrimaryGoal.MUSCLE_GAIN: 300,
    PrimaryGoal.STRENGTH: 200,
    PrimaryGoal.ENDURANCE: 200,
    PrimaryGoal.SKILLS: 0,
    PrimaryGoal.FLEXIBILITY: 0,
    PrimaryGoal.GENERAL_FITNESS: 0,
}

# Protein target in grams per kg of bodyweight, by goal.
GOAL_PROTEIN_G_PER_KG = {
    PrimaryGoal.FAT_LOSS: 2.2,
    PrimaryGoal.MUSCLE_GAIN: 2.0,
    PrimaryGoal.STRENGTH: 2.0,
    PrimaryGoal.ENDURANCE: 1.6,
    PrimaryGoal.SKILLS: 1.8,
    PrimaryGoal.FLEXIBILITY: 1.6,
    PrimaryGoal.GENERAL_FITNESS: 1.8,
}

# Share of daily calories from fat; the remainder (after protein and fat)
# is assigned to carbohydrates.
FAT_SHARE_OF_CALORIES = 0.25

# Floor to avoid recommending an unsafely low calorie target.
MINIMUM_SAFE_CALORIES = 1200


def calculate_bmi(weight_kg, height_cm):
    """Body Mass Index. A screening estimate, not a complete health measure."""
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 1)


def calculate_bmr(weight_kg, height_cm, age, sex):
    """Basal Metabolic Rate via the Mifflin-St Jeor equation.

    For users who prefer not to specify sex, we use the midpoint of the
    male/female offsets rather than guessing.
    """
    if not weight_kg or not height_cm or not age:
        return None

    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == Sex.MALE:
        return round(base + 5, 0)
    if sex == Sex.FEMALE:
        return round(base - 161, 0)
    return round(base - 78, 0)  # midpoint of +5 and -161


def calculate_tdee(bmr, activity_level):
    """Total Daily Energy Expenditure: BMR scaled by activity level."""
    if not bmr:
        return None
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, ACTIVITY_MULTIPLIERS[ActivityLevel.MODERATE])
    return round(bmr * multiplier, 0)


@dataclass
class MacroTargets:
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int


def calculate_daily_targets(weight_kg, height_cm, age, sex, activity_level, primary_goal, override_calories=None):
    """Full daily calorie and macro targets for a user profile.

    Returns None if there isn't enough profile data (weight/height/age) to
    calculate targets yet.
    """
    bmr = calculate_bmr(weight_kg, height_cm, age, sex)
    if bmr is None:
        return None

    tdee = calculate_tdee(bmr, activity_level)
    adjustment = GOAL_CALORIE_ADJUSTMENT.get(primary_goal, 0)
    calories = override_calories or max(MINIMUM_SAFE_CALORIES, tdee + adjustment)

    protein_per_kg = GOAL_PROTEIN_G_PER_KG.get(primary_goal, 1.8)
    protein_g = round(protein_per_kg * weight_kg)
    protein_calories = protein_g * 4

    fat_calories = calories * FAT_SHARE_OF_CALORIES
    fat_g = round(fat_calories / 9)

    carbs_calories = max(0, calories - protein_calories - fat_calories)
    carbs_g = round(carbs_calories / 4)

    return MacroTargets(calories=int(calories), protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g)
