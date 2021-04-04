from django.shortcuts import render, redirect
from django.urls import reverse

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from portfoliohut.forms import LoginForm, RegisterForm, ProfileForm
from portfoliohut.models import Profile


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse('global-competition'))
    else:
        return redirect(reverse('login'))


def login_action(request):
    if request.method == "GET":
        return render(request, "portfoliohut/login.html", {"login_form": LoginForm()})

    login_form = LoginForm(request.POST)

    # Validates form
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

    # Create user since the form is valid
    new_user = User.objects.create_user(username=register_form.cleaned_data['username'],
                                        password=register_form.cleaned_data['password'],
                                        email=register_form.cleaned_data['email'],
                                        first_name=register_form.cleaned_data['first_name'],
                                        last_name=register_form.cleaned_data['last_name'])
    new_user.save()

    profile = Profile.objects.create(user=new_user)
    profile.save()

    new_user = authenticate(username=register_form.cleaned_data['username'],
                            password=register_form.cleaned_data['password'])

    login(request, new_user)
    return redirect(reverse('index'))


@login_required
def global_competition(request):
    context = {}
    profiles = Profile.objects.all()
    context['profiles'] = profiles
    context['page_name'] = 'Global Competition'
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {}
    context['page_name'] = 'Friends Competition'
    return render(request, "portfoliohut/stream.html", context)


@login_required
def profile_page(request, id_num):
    context = {}
    
    profile_exists = Profile.objects.filter(id=id_num)
    if not profile_exists:
        return redirect('index')
    
    context['profile'] = Profile.objects.get(id=id_num)
    return render(request, "portfoliohut/profile.html", context)


@login_required
def update_profile(request):
    context = {}

    if request.method == 'GET':
        return redirect('profile-page', id_num=request.user.id)
    
    profile = Profile.objects.get(user=request.user)
    
    if request.method == 'POST':
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        print(profile_form)
        
        if not profile_form.is_valid():
            print("Form is not valid")
            context['profile_form'] = profile_form
            context['profile'] = profile
            context['message'] = "Form not valid"
            return render(request, 'portfoliohut/profile.html', context) # NEED TO FIX THIS
    
        #profile.profile_picture = profile_form.cleaned_data['profile_picture']
        #profile.content_type = profile_form.cleaned_data['profile_picture'].content_type
        profile.bio = profile_form.cleaned_data['bio']
        profile.save()
        
        context['profile_form'] = profile_form
        context['profile'] = profile
        
        return render(request, 'portfoliohut/profile.html', context) # NEED TO FIX THIS
