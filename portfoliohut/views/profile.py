from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms import ProfileForm
from portfoliohut.models import Profile


@login_required
def logged_in_user_profile(request):
    return redirect(reverse("profile", args=[request.user.username]))


@login_required
def profile(request, username):
    context = {}

    # Make sure user exists
    user_exists = User.objects.filter(username=username)
    if not user_exists:
        return redirect("index")

    # Save user's profile
    user_id = User.objects.get(username=username)
    profile = Profile.objects.get(user_id=user_id)
    context["profile"] = profile

    # Handle GET request
    if request.method == "GET":
        if profile.user == request.user:
            context["profile_form"] = ProfileForm(instance=profile)
        return render(request, "portfoliohut/profile.html", context)

    # Handle POST request
    if request.method == "POST":
        if profile.user != request.user:
            context["error_msg"] = "Cannot update another user's profile"
            return render(request, "portfoliohut/profile.html", context)

        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        if not profile_form.is_valid():
            context["profile_form"] = profile_form
            context["error_msg"] = "Form not valid"
            return render(request, "portfoliohut/profile.html", context)

        # Save Profile Form
        profile.bio = profile_form.cleaned_data["bio"]
        profile.profile_type = profile_form.cleaned_data["profile_type"]
        profile_form.save()
        context["profile_form"] = profile_form

        return render(request, "portfoliohut/profile.html", context)
