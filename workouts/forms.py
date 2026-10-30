from django import forms

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal

from .models import ExerciseLog, RecoveryNote


class PlanGenerateForm(forms.Form):
    goal = forms.ChoiceField(choices=PrimaryGoal.choices)
    experience_level = forms.ChoiceField(choices=ExperienceLevel.choices)
    training_days_per_week = forms.IntegerField(min_value=1, max_value=7)
    session_duration_minutes = forms.IntegerField(min_value=15, max_value=180)
    equipment = forms.MultipleChoiceField(choices=Equipment.choices, widget=forms.CheckboxSelectMultiple, required=False)


class SetLogForm(forms.ModelForm):
    class Meta:
        model = ExerciseLog
        fields = ["reps", "hold_seconds", "rest_taken_seconds", "effort_rpe"]
        widgets = {
            "reps": forms.NumberInput(attrs={"min": 0}),
            "hold_seconds": forms.NumberInput(attrs={"min": 0}),
            "rest_taken_seconds": forms.NumberInput(attrs={"min": 0}),
            "effort_rpe": forms.NumberInput(attrs={"min": 1, "max": 10}),
        }


class RecoveryNoteForm(forms.ModelForm):
    class Meta:
        model = RecoveryNote
        fields = ["sleep_quality", "soreness", "fatigue", "notes"]
        widgets = {
            "sleep_quality": forms.Select(choices=[("", "—")] + [(i, i) for i in range(1, 6)]),
            "soreness": forms.Select(choices=[("", "—")] + [(i, i) for i in range(1, 6)]),
            "fatigue": forms.Select(choices=[("", "—")] + [(i, i) for i in range(1, 6)]),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
