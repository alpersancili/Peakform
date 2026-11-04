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
    """`quantity` is stored as a multiplier of the food's defined serving,
    but for foods measured in grams, typing a multiplier is awkward -
    nobody thinks in "1.5x servings", they think in grams. For those
    foods this form instead shows/accepts the quantity field as grams
    and converts to/from the stored multiplier transparently.
    """

    meal_category = forms.ChoiceField(choices=MealCategory.choices)

    class Meta:
        model = MealEntry
        fields = ["meal_category", "quantity"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"min": 0.1, "step": 0.1}),
        }

    def __init__(self, *args, food=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.food = food or getattr(self.instance, "food", None)
        if self._is_gram_based(self.food):
            self.fields["quantity"].label = "Grams"
            self.fields["quantity"].widget.attrs.update({"min": 1, "step": 1})
            if self.instance.pk:
                self.initial["quantity"] = round(self.instance.quantity * self.food.serving_size)
        else:
            self.fields["quantity"].label = "Servings"

    @staticmethod
    def _is_gram_based(food):
        return bool(food and food.serving_unit.strip().lower() == "g")

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self._is_gram_based(self.food) and self.food.serving_size:
            # The field held grams, not a multiplier - convert to what
            # MealEntry.quantity actually stores.
            return quantity / self.food.serving_size
        return quantity


class WaterQuickAddForm(forms.Form):
    amount_ml = forms.IntegerField(min_value=1, max_value=5000)


class StepLogForm(forms.ModelForm):
    class Meta:
        model = StepLog
        fields = ["step_count"]
        widgets = {
            "step_count": forms.NumberInput(attrs={"min": 0, "max": 100000}),
        }
