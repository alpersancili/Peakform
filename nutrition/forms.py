from django import forms

from .models import Food, MealCategory, MealEntry, StepLog


class FoodSearchForm(forms.Form):
    q = forms.CharField(label="Search foods", required=False, max_length=150)


class CustomFoodForm(forms.ModelForm):
    class Meta:
        model = Food
        fields = ["name", "brand", "serving_size", "serving_unit", "calories", "protein_g", "carbs_g", "fat_g"]
        widgets = {
            "serving_unit": forms.TextInput(attrs={"placeholder": "g, ml, piece..."}),
        }


class MealEntryForm(forms.ModelForm):
    meal_category = forms.ChoiceField(choices=MealCategory.choices)

    class Meta:
        model = MealEntry
        fields = ["meal_category", "quantity"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"min": 0.1, "step": 0.1}),
        }


class WaterQuickAddForm(forms.Form):
    amount_ml = forms.IntegerField(min_value=1, max_value=5000)


class StepLogForm(forms.ModelForm):
    class Meta:
        model = StepLog
        fields = ["step_count"]
        widgets = {
            "step_count": forms.NumberInput(attrs={"min": 0, "max": 100000}),
        }
