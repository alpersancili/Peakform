from django import forms

from .models import MAX_IMAGE_SIZE_BYTES, Comment, Post, Report


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["post_type", "body", "image"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 3, "placeholder": "Share something with the community..."}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and image.size > MAX_IMAGE_SIZE_BYTES:
            raise forms.ValidationError("Images must be 5MB or smaller.")
        return image


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 2, "placeholder": "Add a comment..."}),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional details (max 300 characters)"}),
        }
