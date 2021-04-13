from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.models import Profile


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse("global-competition"))
    else:
        return redirect(reverse("login"))


@login_required
def global_competition(request):
    context = {}
    profiles = Profile.objects.all()
    context["profiles"] = profiles
    context["page_name"] = "Global Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {"page_name": "Friends Competition"}
    return render(request, "portfoliohut/stream.html", context)
