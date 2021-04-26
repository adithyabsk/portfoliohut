"""Social URLs"""

from django.urls import path

from portfoliohut.views import (
    friend,
    friends_competition,
    global_competition,
    landing_page,
    logged_in_user_profile,
    login_action,
    logout_action,
    portfolio,
    profile,
    register_action,
    respond_to_friend_request,
    transaction_input,
)

urlpatterns = [
    path("", landing_page, name="landing-page"),
    path("login", login_action, name="login"),
    path("logout", logout_action, name="logout"),
    path("register", register_action, name="register"),
    path("global-competition", global_competition, name="global-competition"),
    path("friends-competition", friends_competition, name="friends-competition"),
    path(
        "logged-in-user-profile", logged_in_user_profile, name="logged-in-user-profile"
    ),
    path("profile/<str:username>", profile, name="profile"),
    path("add-transaction", transaction_input, name="add-transaction"),
    path("portfolio", portfolio, name="portfolio"),
    path("friend/<str:username>", friend, name="friend"),
    path(
        "respond-to-friend-request/<str:username>/<str:action>",
        respond_to_friend_request,
        name="respond-to-friend-request",
    ),
    path("landing-page", landing_page, name="landing-page"),
]
