from django import forms

from .models import MAX_PHOTO_SIZE_BYTES, ProgressEntry, ProgressPhoto


class ProgressEntryForm(forms.ModelForm):
    class Meta:
        model = ProgressEntry
        fields = ["date", "weight_kg", "waist_cm", "chest_cm", "hips_cm", "arm_cm", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "weight_kg": forms.NumberInput(attrs={"min": 20, "max": 500, "step": 0.1}),
            "waist_cm": forms.NumberInput(attrs={"min": 30, "max": 300, "step": 0.1}),
            "chest_cm": forms.NumberInput(attrs={"min": 30, "max": 300, "step": 0.1}),
            "hips_cm": forms.NumberInput(attrs={"min": 30, "max": 300, "step": 0.1}),
            "arm_cm": forms.NumberInput(attrs={"min": 10, "max": 100, "step": 0.1}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note, e.g. how you felt"}),
        }
        labels = {
            "weight_kg": "Weight (kg)",
            "waist_cm": "Waist (cm, optional)",
            "chest_cm": "Chest (cm, optional)",
            "hips_cm": "Hips (cm, optional)",
            "arm_cm": "Arm (cm, optional)",
        }


class ProgressPhotoForm(forms.ModelForm):
    class Meta:
        model = ProgressPhoto
        fields = ["date", "image", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(attrs={"placeholder": "Optional note, e.g. lighting, pose"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > MAX_PHOTO_SIZE_BYTES:
            raise forms.ValidationError("Images must be 5MB or smaller.")
        return image
