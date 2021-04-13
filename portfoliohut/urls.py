"""Social URLs"""

from django.urls import path

from portfoliohut.views import (
    friends_competition,
    global_competition,
    index,
    logged_in_user_profile,
    login_action,
    logout_action,
    portfolio,
    profile,
    register_action,
    transaction_input,
)

urlpatterns = [
    path("", index, name="index"),
    path("login", login_action, name="login"),
    path("logout", logout_action, name="logout"),
    path("register", register_action, name="register"),
    path("global-competition", global_competition, name="global-competition"),
    path("friends-competition", friends_competition, name="friends-competition"),
    path(
        "logged-in-user-profile", logged_in_user_profile, name="logged-in-user-profile"
    ),
    path("profile/<int:id_num>", profile, name="profile"),
    path("add-transaction", transaction_input, name="add-transaction"),
    path("portfolio", portfolio, name="portfolio"),
]
