from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegistrationForm
from .models import UserProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to Peakform! Let's set up your profile.")
            return redirect("accounts:onboarding")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def onboarding(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.onboarding_completed:
        return redirect("nutrition:dashboard")

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.onboarding_completed = True
            profile.save()
            messages.success(request, "Your profile is set up.")
            return redirect("nutrition:dashboard")
    else:
        form = ProfileForm(instance=profile)

    return render(request, "accounts/onboarding.html", {"form": form})


@login_required
def profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "accounts/profile.html", {"profile": user_profile})


@login_required
def profile_edit(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=user_profile)

    return render(request, "accounts/profile_edit.html", {"form": form})
