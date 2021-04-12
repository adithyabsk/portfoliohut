from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from portfoliohut.forms.forms import ProfileForm
from portfoliohut.models.models import Profile


@login_required
def profile_page(request, id_num):
    context = {}

    profile_exists = Profile.objects.filter(id=id_num)
    if not profile_exists:
        return redirect("index")

    context["profile"] = Profile.objects.get(id=id_num)
    return render(request, "portfoliohut/profile.html", context)


@login_required
def update_profile(request):
    context = {}

    if request.method == "GET":
        return redirect("profile-page", id_num=request.user.id)

    profile = Profile.objects.get(user=request.user)

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        print(profile_form)

        if not profile_form.is_valid():
            print("Form is not valid")
            context["profile_form"] = profile_form
            context["profile"] = profile
            context["message"] = "Form not valid"
            return render(
                request, "portfoliohut/profile.html", context
            )  # NEED TO FIX THIS

        # profile.profile_picture = profile_form.cleaned_data['profile_picture']
        # profile.content_type = profile_form.cleaned_data['profile_picture'].content_type
        profile.bio = profile_form.cleaned_data["bio"]
        profile.save()

        context["profile_form"] = profile_form
        context["profile"] = profile

        return render(request, "portfoliohut/profile.html", context)  # NEED TO FIX THIS
