from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django_tables2 import RequestConfig

from portfoliohut.graph import _get_sp_index, combine_data, multi_plot
from portfoliohut.models import Profile
from portfoliohut.tables import ReturnsTable

NUM_LEADERS = 10


def _build_competition_table(profiles, request):
    competition_table = ReturnsTable(profiles)
    RequestConfig(request).configure(competition_table)
    return HttpResponse(competition_table.as_html(request))


def _annotate_profiles_with_returns(profiles, current_profile):
    [
        setattr(  # noqa: B010
            profile, "returns", profile.get_most_recent_return() * 100
        )  # noqa: B010
        for profile in profiles
    ]
    current_profile_rank = None
    profiles = sorted(profiles, key=lambda prof: prof.returns, reverse=True)
    for i, profile in enumerate(profiles):
        profile.rank = i + 1
        if current_profile == profile:
            current_profile_rank = i
    return profiles, current_profile_rank


@login_required
def display_global_table(request):
    # Get all public profiles
    public_profiles = Profile.objects.filter(profile_type="public")
    unsorted_public_profiles = public_profiles.all()

    # Calculate percent returns for each public profile
    annotated_profiles, curr_prof_rank = _annotate_profiles_with_returns(
        unsorted_public_profiles, request.user.profile
    )

    # Create the competition table
    return _build_competition_table(annotated_profiles, request)


@login_required
def display_friends_table(request):
    # Get all public profiles
    unsorted_friends_profiles = request.user.profile.friends.all()
    my_profile = Profile.objects.filter(user=request.user)
    unsorted_friends_profiles = unsorted_friends_profiles.union(my_profile)

    # Calculate percent returns for each friend
    no_friends_flag = len(unsorted_friends_profiles) <= 0
    if no_friends_flag:
        return None

    # Sort friends by their percent returns
    annotated_profiles, curr_prof_rank = _annotate_profiles_with_returns(
        unsorted_friends_profiles, request.user.profile
    )

    # Create the competition table
    return _build_competition_table(annotated_profiles, request)


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
        friend_returns = profile.get_cumulative_returns()  # * 100
        friends_series.append(friend_returns)
        friends_names.append(profile.user.first_name + " " + profile.user.last_name)
    user_returns = my_profile.get_cumulative_returns() * 100
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


def page_not_found(request, exeption=None):
    response = render(request, "portfoliohut/error.html", {})
    response.status_code = 400
    return response
