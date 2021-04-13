"""Views and actions related to account management."""
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms import LoginForm, RegisterForm
from portfoliohut.models import Profile


def login_action(request):
    if request.method == "GET":
        return render(request, "portfoliohut/login.html", {"login_form": LoginForm()})

    login_form = LoginForm(request.POST)

    # Validates form
    if not login_form.is_valid():
        return render(request, "portfoliohut/login.html", {"login_form": login_form})

    new_user = authenticate(
        username=login_form.cleaned_data["username"],
        password=login_form.cleaned_data["password"],
    )
    login(request, new_user)

    return redirect(reverse("index"))


@login_required
def logout_action(request):
    logout(request)
    return redirect(reverse("login"))


def register_action(request):
    if request.method == "GET":
        return render(
            request, "portfoliohut/register.html", {"register_form": RegisterForm()}
        )

    context = {}

    register_form = RegisterForm(request.POST)
    context["register_form"] = register_form

    if not register_form.is_valid():
        return render(request, "portfoliohut/register.html", context)

    # Create user since the form is valid
    new_user = User.objects.create_user(
        username=register_form.cleaned_data["username"],
        password=register_form.cleaned_data["password"],
        email=register_form.cleaned_data["email"],
        first_name=register_form.cleaned_data["first_name"],
        last_name=register_form.cleaned_data["last_name"],
    )
    new_user.save()

    profile = Profile.objects.create(user=new_user)
    profile.save()

    new_user = authenticate(
        username=register_form.cleaned_data["username"],
        password=register_form.cleaned_data["password"],
    )

    login(request, new_user)
    return redirect(reverse("index"))
