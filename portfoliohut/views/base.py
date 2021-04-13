from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

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
    # You can't order by a computed column (when the computation is a python function), if it is a
    # simple computations from fields, then you can use `F`
    # https://stackoverflow.com/a/6932807/3262054
    unsorted_public_profiles = public_profiles.all()
    public_profiles = sorted(
        unsorted_public_profiles, key=lambda prof: prof.get_most_recent_return()
    )

    count = 0
    prev_percent_returns = None
    leaders = []
    for i in range(len(public_profiles)):
        if count < NUM_LEADERS:
            leaders.append(public_profiles[i])
        else:
            if prev_percent_returns == public_profiles[i]:
                leaders.append(public_profiles[i])
            else:
                break
        prev_percent_returns = public_profiles[i]
        count += 1

    context["profiles"] = leaders
    if request.user.profile in public_profiles:
        context["logged_in_user_rank"] = (
            (*public_profiles,).index(Profile.objects.get(user=request.user))
        ) + 1
    context["page_name"] = "Global Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {"page_name": "Friends Competition"}
    return render(request, "portfoliohut/stream.html", context)
