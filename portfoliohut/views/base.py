import math

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django_tables2 import RequestConfig

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


def _build_competition_table(profiles, page, request):
    competition_table = ReturnsTable(profiles)
    RequestConfig(request).configure(competition_table)
    return HttpResponse(competition_table.as_html(request))


def _annotate_profiles_with_returns(unsorted_profiles):
    annotated_profiles = []
    for profile in unsorted_profiles:
        profile.returns = profile.get_most_recent_return()
        annotated_profiles.append(profile)
    return annotated_profiles


@login_required
def display_global_table(request):
    # Get all public profiles
    public_profiles = Profile.objects.filter(profile_type="public")
    unsorted_public_profiles = public_profiles.all()

    # Calculate percent returns for each public profile
    annotated_profiles = _annotate_profiles_with_returns(unsorted_public_profiles)

    # Sort public profiles by their percent returns
    profiles = _sort_profiles_by_percent_returns(annotated_profiles)

    # Identify the current user's rank
    page_num = 1
    if request.user.profile in profiles:
        rank = profiles.index(request.user.profile) + 1
        page_num = math.ceil(rank / NUM_LEADERS)
    page = request.GET.get("page", page_num)

    # Create the competition table
    return _build_competition_table(profiles, page, request)


@login_required
def display_friends_table(request):
    # Get all public profiles
    my_profile = Profile.objects.get(user=request.user)
    friends_profiles = Profile.objects.filter(friends__pk=my_profile.id)
    unsorted_friends_profiles = friends_profiles.all()

    # Calculate percent returns for each friend
    no_friends_flag = len(unsorted_friends_profiles) <= 0
    if no_friends_flag:
        return None

    # Calculate percent returns for each public profile
    annotated_profiles = []
    for profile in unsorted_friends_profiles:
        profile.returns = profile.get_most_recent_return()
        annotated_profiles.append(profile)
    my_profile.returns = my_profile.get_most_recent_return()
    annotated_profiles.append(my_profile)

    # Sort friends by their percent returns
    profiles = _sort_profiles_by_percent_returns(annotated_profiles)

    # Create the competition table
    rank = profiles.index(my_profile) + 1
    page_num = math.ceil(rank / NUM_LEADERS)
    page = request.GET.get("page", page_num)

    # Create the competition table
    return _build_competition_table(profiles, page, request)


@login_required
def global_competition(request):
    if request.method == "GET":
        context = {}
        context["page_name"] = "Global Competition"
        return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_returns_graph(request):
    my_profile = Profile.objects.get(user=request.user)
    friends_profiles = Profile.objects.filter(friends__pk=my_profile.id)
    unsorted_friends_profiles = friends_profiles.all()

    # Get everyone's returns
    friends_series = []
    friends_names = []
    for profile in unsorted_friends_profiles:
        friend_returns = profile.get_cumulative_returns()
        friends_series.append(friend_returns)
        friends_names.append(profile.user.first_name + " " + profile.user.last_name)
    user_returns = my_profile.get_cumulative_returns()
    index_returns = _get_sp_index(user_returns.index[0])

    # Create the competition graph
    merged_df = combine_data(friends_series, friends_names, user_returns, index_returns)
    graph = multi_plot(merged_df)
    return HttpResponse(graph)


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
            context["no_friends_flag"] = True

        return render(request, "portfoliohut/stream.html", context)


def landing_page(request):
    return render(request, "portfoliohut/landing.html")
