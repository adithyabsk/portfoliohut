"""Social URLs"""

from django.urls import path

from .views import index, login_action, register_action, global_stream, follower_stream, profile, logout_action

urlpatterns = [
    path("", index, name="index"),
    path("login", login_action, name="login"),
    path("logout", logout_action, name="logout"),
    path("register", register_action, name="register"),
    path("global-stream", global_stream, name="global-stream"),
    path("follower-stream", follower_stream, name="follower-stream"),
    path("profile", profile, name="profile")
]
