import math

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from portfoliohut.graph import _get_sp_index, combine_data, multi_plot
from portfoliohut.models import Profile
from portfoliohut.tables import ReturnsTable

NUM_LEADERS = 10


def _sort_profiles_by_percent_returns(annotated_profiles):
    profiles = sorted(
        annotated_profiles,
        key=lambda prof: prof.returns
        if not math.isnan(prof.returns)
        else float("-inf"),
        reverse=True,
    )
    return profiles


def _build_competition_table(profiles, page):
    competition_table = ReturnsTable(profiles)
    competition_table.paginate(page=page, per_page=NUM_LEADERS)
    return competition_table


def _annotate_profiles_with_returns(unsorted_profiles):
    annotated_profiles = []
    for profile in unsorted_profiles:
        profile.returns = profile.get_most_recent_return()
        annotated_profiles.append(profile)
    return annotated_profiles


@login_required
def global_competition(request):
    if request.method == "GET":
        context = {}
        context["page_name"] = "Global Competition"

        # Get all public profiles
        public_profiles = Profile.objects.filter(profile_type="public")
        unsorted_public_profiles = public_profiles.all()

        # Calculate percent returns for each public profile
        annotated_profiles = _annotate_profiles_with_returns(unsorted_public_profiles)

        # Sort public profiles by their percent returns
        profiles = _sort_profiles_by_percent_returns(annotated_profiles)

        # Create the competition table
        page = request.GET.get("page", 1)
        context["competition_table"] = _build_competition_table(profiles, page)

        return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    if request.method == "GET":
        context = {}
        context["page_name"] = "Friends Competition"

        # Get all public profiles
        my_profile = Profile.objects.get(user=request.user)
        friends_profiles = Profile.objects.filter(friends__pk=my_profile.id)
        unsorted_friends_profiles = friends_profiles.all()

        # Calculate percent returns for each friend
        no_friends_flag = len(unsorted_friends_profiles) <= 0
        if no_friends_flag:
            return render(request, "portfoliohut/stream.html", context)

        # Calculate percent returns for each public profile
        annotated_profiles = []
        friends_series = []
        friends_names = []
        for profile in unsorted_friends_profiles:
            profile.returns = profile.get_most_recent_return()
            annotated_profiles.append(profile)
            friend_returns = profile.get_cumulative_returns()
            friends_series.append(friend_returns)
            friends_names.append(profile.user.first_name + " " + profile.user.last_name)

        # Sort friends by their percent returns
        profiles = _sort_profiles_by_percent_returns(annotated_profiles)

        # Create the competition table
        page = request.GET.get("page", 1)
        context["competition_table"] = _build_competition_table(profiles, page)

        # Create the competition graph
        user_returns = my_profile.get_cumulative_returns()
        index_returns = _get_sp_index(user_returns.index[0])
        merged_df = combine_data(
            friends_series, friends_names, user_returns, index_returns
        )
        graph = multi_plot(merged_df)
        context["graph"] = graph

        return render(request, "portfoliohut/stream.html", context)


def landing_page(request):
    return render(request, "portfoliohut/landing.html")
