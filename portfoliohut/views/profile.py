import math

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import DecimalField, ExpressionWrapper, F
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms import ProfileForm
from portfoliohut.models import EquityInfo, FinancialActionType, PortfolioItem, Profile


@login_required
def logged_in_user_profile(request):
    return redirect(reverse("profile", args=[request.user.username]))


@login_required
def profile_returns(request, username):
    user = User.objects.filter(username=username)
    if not user.exists():
        return HttpResponse("")
    user = user[0]
    returns = user.profile.get_most_recent_return()
    if math.isnan(returns):
        return HttpResponse("<h5 class='font-weight-bold mb-0 d-block'>No Return %<h5>")
    return HttpResponse(
        "<h5 class='font-weight-bold mb-0 d-block'>{returns}%<h5>".format(
            returns=round(returns, 3),
        )
    )


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
    get_all_stocks = (
        PortfolioItem.objects.filter(profile=profile, type=FinancialActionType.EQUITY)
        .values("ticker")
        .annotate(
            total_price=ExpressionWrapper(
                F("quantity") * F("price"), output_field=DecimalField()
            )
        )
        .order_by("-total_price")[:5]
    )

    stocks_urls = []
    if get_all_stocks:
        for i in get_all_stocks:
            stocks_urls.append((EquityInfo.objects.get_ticker(i["ticker"])).logo_url)

    context["top_stocks"] = stocks_urls
    context["returns"] = profile.get_most_recent_return()
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


@login_required
def friend(request, username):
    context = {}

    # Cannot friend yourself
    if username == request.user.username:
        return redirect(reverse, "index")

    # Make sure user exists
    other_user_exists = User.objects.filter(username=username)
    if not other_user_exists:
        return redirect(reverse("index"))

    # Save users' profiles
    user_id = User.objects.get(username=username)
    other_user = Profile.objects.get(user_id=user_id)
    logged_in_user = Profile.objects.get(user=request.user)
    context["profile"] = other_user

    # Handle GET request
    if request.method == "GET":

        # See if friend request already exists
        request_already_exists = other_user.friend_requests.filter(
            user_id=logged_in_user.user_id
        )
        if not request_already_exists:
            already_friends = other_user.friends.filter(user_id=logged_in_user.user_id)

            # Send friend request
            if not already_friends:
                other_user.friend_requests.add(logged_in_user)

            # Unfriend
            else:
                other_user.friends.remove(logged_in_user)
                logged_in_user.friends.remove(other_user)

            logged_in_user.save()
            other_user.save()

        return redirect(reverse("profile", args=[username]))


@login_required
def respond_to_friend_request(request, username, action):
    context = {}

    # Cannot friend yourself
    if username == request.user.username:
        return redirect(reverse, "index")

    # Make sure user exists
    other_user_exists = User.objects.filter(username=username)
    if not other_user_exists:
        return redirect(reverse("index"))

    # Save user's profile
    user_id = User.objects.get(username=username)
    other_user = Profile.objects.get(user_id=user_id)
    logged_in_user = Profile.objects.get(user=request.user)
    context["profile"] = other_user

    friend_request_exists = logged_in_user.friend_requests.filter(
        user_id=other_user.user_id
    )
    if not friend_request_exists:
        return redirect(reverse("profile", args=[username]))

    # Handle GET request
    if request.method == "GET":
        # Accept friend request
        if action == "accept":
            logged_in_user.friend_requests.remove(other_user)
            logged_in_user.friends.add(other_user)
            other_user.friends.add(logged_in_user)

        # Decline friend request
        elif action == "decline":
            logged_in_user.friend_requests.remove(other_user)

        logged_in_user.save()
        other_user.save()

        return redirect(reverse("profile", args=[username]))
