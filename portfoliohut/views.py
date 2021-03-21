from django.shortcuts import render, redirect
from django.urls import reverse

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from .forms import LoginForm, RegisterForm


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse('global-stream'))
    else:
        return redirect(reverse('login'))


def login_action(request):
    if request.method == "GET":
        return render(request, "portfoliohut/login.html", {"login_form": LoginForm()})

    login_form = LoginForm(request.POST)

    # Validates the form.
    if not login_form.is_valid():
        return render(request, 'portfoliohut/login.html', {"login_form": login_form})

    new_user = authenticate(username=login_form.cleaned_data['username'],
                            password=login_form.cleaned_data['password'])
    login(request, new_user)

    return redirect(reverse('index'))


@login_required
def logout_action(request):
    logout(request)
    return redirect(reverse('login'))


def register_action(request):
    if request.method == "GET":
        return render(request, "portfoliohut/register.html", {"register_form": RegisterForm()})

    context = {}

    register_form = RegisterForm(request.POST)
    context['register_form'] = register_form

    if not register_form.is_valid():
        return render(request, 'portfoliohut/register.html', context)

    # Create user since the form is valid.
    new_user = User.objects.create_user(username=register_form.cleaned_data['username'],
                                        password=register_form.cleaned_data['password'],
                                        email=register_form.cleaned_data['email'],
                                        first_name=register_form.cleaned_data['first_name'],
                                        last_name=register_form.cleaned_data['last_name'])
    new_user.save()

    new_user = authenticate(username=register_form.cleaned_data['username'],
                            password=register_form.cleaned_data['password'])

    login(request, new_user)
    return redirect(reverse('index'))


@login_required
def global_stream(request):
    return render(request, "portfoliohut/stream.html", {"page_name": "Global Stream"})


@login_required
def follower_stream(request):
    return render(request, "portfoliohut/stream.html", {"page_name": "Follower Stream"})


@login_required
def profile(request):
    if request.method == 'GET' and request.GET.get("user") is not None:
        return render(request, "portfoliohut/profile.html", {"self_user": False})
    else:
        return render(request, "portfoliohut/profile.html", {"self_user": True})
