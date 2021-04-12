"""Social URLs"""

from django.urls import path

from portfoliohut.views import (
    friends_competition,
    global_competition,
    index,
    login_action,
    logout_action,
    profile_page,
    register_action,
    return_profile,
    transcation_input,
    update_profile,
)

urlpatterns = [
    path("", index, name="index"),
    path("login", login_action, name="login"),
    path("logout", logout_action, name="logout"),
    path("register", register_action, name="register"),
    path("global-competition", global_competition, name="global-competition"),
    path("friends-competition", friends_competition, name="friends-competition"),
    path("profile-page/<int:id_num>", profile_page, name="profile-page"),
    path("update-profile", update_profile, name="update-profile"),
    path("add_transaction", transcation_input, name="add_transaction"),
    path("returns-profile", return_profile, name="returns-profile"),
]
