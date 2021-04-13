import math

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
    annotated_public_profiles = []
    for p in unsorted_public_profiles:
        p.returns = p.get_most_recent_return()
        annotated_public_profiles.append(p)
    public_profiles = sorted(
        annotated_public_profiles, key=lambda prof: prof.returns, reverse=True
    )

    rank = 0
    leaders = []
    for i in range(len(public_profiles)):
        if rank < NUM_LEADERS:
            if not math.isnan(public_profiles[i].returns):
                leaders.append(public_profiles[i])
            else:
                print("entered")
        rank += 1

    context["profiles"] = leaders
    if request.user.profile in public_profiles:
        context["logged_in_user_rank"] = (
            (*public_profiles,).index(Profile.objects.get(user=request.user))
        ) + 1

    # TODO: Show logged in user their percet returns no matter what
    else:
        pass
    context["page_name"] = "Global Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {"page_name": "Friends Competition"}
    return render(request, "portfoliohut/stream.html", context)
