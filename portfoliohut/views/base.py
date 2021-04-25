import math

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.graph import combine_data, multi_plot
from portfoliohut.models import Profile

NUM_LEADERS = 5


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse("global-competition"))
    else:
        return redirect(reverse("login"))


@login_required
def global_competition(request):
    context = {}
    public_profiles = Profile.objects.filter(profile_type="public")
    unsorted_public_profiles = public_profiles.all()
    annotated_public_profiles = []

    for profile in unsorted_public_profiles:
        profile.returns = profile.get_most_recent_return()
        annotated_public_profiles.append(profile)

    # Sort public profiles by their percent returns
    public_profiles = sorted(
        annotated_public_profiles,
        key=lambda prof: prof.returns
        if not math.isnan(prof.returns)
        else float("-inf"),
        reverse=True,
    )

    # Get top 5 leaders by percent returns
    rank = 0
    leaders = []
    for i in range(len(public_profiles)):
        if rank < NUM_LEADERS:
            if not math.isnan(public_profiles[i].returns):
                leaders.append(public_profiles[i])
        else:
            break
        rank += 1
    context["profiles"] = leaders

    # Logged in user is on the global leaderboard
    if request.user.profile in public_profiles:
        index = public_profiles.index(request.user.profile)
        context["logged_in_user_rank"] = index + 1
        returns = public_profiles[index].returns
        if not math.isnan(returns):
            context["logged_in_user_returns"] = returns

    context["page_name"] = "Global Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {}

    my_profile = Profile.objects.get(user=request.user)
    friends_profiles = Profile.objects.filter(friends__pk=request.user.profile.id)
    unsorted_friends_profiles = friends_profiles.all()
    annotated_profiles = []
    friends_series = []
    friends_names = []

    # Get friend's portfolio returns
    for profile in unsorted_friends_profiles:
        profile.returns = profile.get_most_recent_return()
        annotated_profiles.append(profile)
        friend_returns = profile.get_cumulative_returns()
        friends_series.append(friend_returns)
        friends_names.append(profile.user.first_name + " " + profile.user.last_name)

    # Get my portfolio returns
    my_profile.returns = my_profile.get_most_recent_return()
    annotated_profiles.append(my_profile)

    user_returns = my_profile.get_cumulative_returns()
    # TODO : Change me  ###
    index_returns = user_returns.multiply(10)
    merged_df = combine_data(friends_series, friends_names, user_returns, index_returns)
    graph = multi_plot(merged_df)
    context["graph"] = graph

    # Sort public profiles by their percent returns
    profiles = sorted(
        annotated_profiles,
        key=lambda prof: prof.returns
        if not math.isnan(prof.returns)
        else float("-inf"),
        reverse=True,
    )
    context["profiles"] = profiles

    context["page_name"] = "Friends Competition"
    return render(request, "portfoliohut/stream.html", context)


def landing_page(request):
    if request.method == "POST":
        if "register_button" in request.POST:
            return redirect(reverse("register"))

    return render(request, "portfoliohut/landing.html", {})
