"""Social URLs"""

from django.urls import path

from portfoliohut.views import index, login_action, register_action, global_competition, friends_competition, profile_page, logout_action, update_profile

urlpatterns = [
    path("", index, name="index"),
    path("login", login_action, name="login"),
    path("logout", logout_action, name="logout"),
    path("register", register_action, name="register"),
    path("global-competition", global_competition, name="global-competition"),
    path("friends-competition", friends_competition, name="friends-competition"),
    path("profile-page/<int:id_num>", profile_page, name="profile-page"),
    path("update-profile", update_profile, name="update-profile"),
]
