from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import DietaryPreference, Equipment, UnitsPreference, UserProfile

CM_PER_INCH = 2.54
KG_PER_LB = 0.45359237


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    """Collects onboarding/fitness-profile fields.

    Height and weight are always entered in the user's preferred units and
    converted to canonical metric (height_cm/weight_kg) on save, so the
    stored data stays unit-independent for calculations.
    """

    height_ft = forms.IntegerField(
        label="Height (feet)", required=False, min_value=1, max_value=8
    )
    height_in = forms.FloatField(
        label="Height (inches)", required=False, min_value=0, max_value=11.9
    )
    height_cm_input = forms.FloatField(
        label="Height (cm)", required=False, min_value=50, max_value=272
    )
    weight_lb = forms.FloatField(
        label="Weight (lb)", required=False, min_value=44, max_value=1100
    )
    weight_kg_input = forms.FloatField(
        label="Weight (kg)", required=False, min_value=20, max_value=500
    )

    equipment = forms.MultipleChoiceField(
        choices=Equipment.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    dietary_preferences = forms.MultipleChoiceField(
        choices=DietaryPreference.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = UserProfile
        fields = [
            "date_of_birth",
            "sex",
            "preferred_units",
            "activity_level",
            "experience_level",
            "primary_goal",
            "training_days_per_week",
            "session_duration_minutes",
            "equipment",
            "dietary_preferences",
            "country",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "sex": forms.Select,
            "preferred_units": forms.Select(attrs={"id": "id_preferred_units"}),
            "training_days_per_week": forms.NumberInput(attrs={"min": 1, "max": 7}),
            "session_duration_minutes": forms.NumberInput(attrs={"min": 10, "max": 180}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance and instance.pk:
            self.fields["equipment"].initial = instance.equipment
            self.fields["dietary_preferences"].initial = instance.dietary_preferences
            if instance.height_cm:
                self.fields["height_cm_input"].initial = round(instance.height_cm, 1)
                total_in = instance.height_cm / CM_PER_INCH
                self.fields["height_ft"].initial = int(total_in // 12)
                self.fields["height_in"].initial = round(total_in % 12, 1)
            if instance.weight_kg:
                self.fields["weight_kg_input"].initial = round(instance.weight_kg, 1)
                self.fields["weight_lb"].initial = round(instance.weight_kg / KG_PER_LB, 1)

    def clean(self):
        cleaned = super().clean()
        units = cleaned.get("preferred_units")

        if units == UnitsPreference.IMPERIAL:
            ft, inch = cleaned.get("height_ft"), cleaned.get("height_in")
            lb = cleaned.get("weight_lb")
            if ft is None:
                self.add_error("height_ft", "Enter your height.")
            if lb is None:
                self.add_error("weight_lb", "Enter your weight.")
            if ft is not None:
                total_inches = ft * 12 + (inch or 0)
                cleaned["height_cm"] = total_inches * CM_PER_INCH
            if lb is not None:
                cleaned["weight_kg"] = lb * KG_PER_LB
        else:
            cm, kg = cleaned.get("height_cm_input"), cleaned.get("weight_kg_input")
            if cm is None:
                self.add_error("height_cm_input", "Enter your height.")
            if kg is None:
                self.add_error("weight_kg_input", "Enter your weight.")
            cleaned["height_cm"] = cm
            cleaned["weight_kg"] = kg

        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.height_cm = self.cleaned_data.get("height_cm")
        profile.weight_kg = self.cleaned_data.get("weight_kg")
        profile.equipment = self.cleaned_data.get("equipment", [])
        profile.dietary_preferences = self.cleaned_data.get("dietary_preferences", [])
        if commit:
            profile.save()
        return profile
