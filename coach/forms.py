from django import forms

from .ai_client import MAX_MESSAGE_LENGTH


class CoachMessageForm(forms.Form):
    message = forms.CharField(
        max_length=MAX_MESSAGE_LENGTH,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ask your coach anything..."}),
    )
