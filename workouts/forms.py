from django import forms

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal

from .models import (
    CommunityRoutine,
    CommunityRoutineExercise,
    CommunityRoutineRating,
    CustomSkillGoal,
    ExerciseLog,
    RecoveryNote,
)


class PlanGenerateForm(forms.Form):
    goal = forms.ChoiceField(choices=PrimaryGoal.choices)
    experience_level = forms.ChoiceField(choices=ExperienceLevel.choices)
    training_days_per_week = forms.IntegerField(min_value=1, max_value=7)
    session_duration_minutes = forms.IntegerField(min_value=15, max_value=180)
    equipment = forms.MultipleChoiceField(choices=Equipment.choices, widget=forms.CheckboxSelectMultiple, required=False)

    def clean_equipment(self):
        # "No equipment" is exclusive - if it's checked alongside anything
        # else (the client-side JS normally prevents this, but a request
        # could bypass it), treat it as authoritative and drop the rest.
        equipment = self.cleaned_data.get("equipment") or []
        if Equipment.NONE in equipment and len(equipment) > 1:
            return [Equipment.NONE]
        return equipment


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


class CustomSkillGoalForm(forms.ModelForm):
    steps = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "One step per line, in order..."}),
        help_text="One step per line, in the order you'll tackle them.",
    )

    class Meta:
        model = CustomSkillGoal
        fields = ["title"]
        widgets = {"title": forms.TextInput(attrs={"placeholder": "e.g. Touch my toes"})}

    def clean_steps(self):
        lines = [line.strip() for line in self.cleaned_data["steps"].splitlines()]
        steps = [line for line in lines if line]
        if not steps:
            raise forms.ValidationError("Add at least one step.")
        return steps


class CommunityRoutineForm(forms.ModelForm):
    goal = forms.ChoiceField(choices=[("", "Any goal")] + list(PrimaryGoal.choices), required=False)
    equipment = forms.MultipleChoiceField(
        choices=Equipment.choices, widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = CommunityRoutine
        fields = ["name", "level", "goal", "equipment", "instructions", "safety_notes"]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 4, "placeholder": "Ordering, tempo, rest between exercises..."}),
            "safety_notes": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Injury risks, who should avoid this, form cues to watch (optional)"}
            ),
        }


class CommunityRoutineExerciseForm(forms.ModelForm):
    class Meta:
        model = CommunityRoutineExercise
        fields = ["exercise", "target_sets", "target_reps", "target_hold_seconds"]
        widgets = {
            "target_sets": forms.NumberInput(attrs={"min": 1}),
            "target_reps": forms.NumberInput(attrs={"min": 1}),
            "target_hold_seconds": forms.NumberInput(attrs={"min": 1}),
        }


class CommunityRoutineRatingForm(forms.ModelForm):
    class Meta:
        model = CommunityRoutineRating
        fields = ["stars"]
        widgets = {"stars": forms.Select(choices=[(i, f"{i} star{'s' if i != 1 else ''}") for i in range(1, 6)])}
