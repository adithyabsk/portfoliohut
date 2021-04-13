from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms import ProfileForm
from portfoliohut.models import Profile


@login_required
def profile(request, id_num):
    context = {}

    profile_exists = Profile.objects.filter(id=id_num)
    if not profile_exists:
        return redirect("index")

    context["profile"] = Profile.objects.get(id=id_num)
    # Once these two are a single endpoint the bio bug will be fixed.
    return render(request, "portfoliohut/profile.html", context)


@login_required
def update_profile(request):
    context = {}

    if request.method == "GET":
        return redirect(reverse("profile", args=[request.user.id]))

    if request.method == "POST":
        profile = Profile.objects.get(user=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if not profile_form.is_valid():
            context["profile_form"] = profile_form
            context["profile"] = profile
            context["message"] = "Form not valid"
            return render(request, "portfoliohut/profile.html", context)

        profile.bio = profile_form.cleaned_data["bio"]
        profile.profile_type = profile_form.cleaned_data["profile_type"]
        profile_form.save()

        context["profile_form"] = profile_form
        context["profile"] = profile

        return render(request, "portfoliohut/profile.html", context)  # NEED TO FIX THIS
