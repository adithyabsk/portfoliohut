"""PortfolioHut views"""

from .account_management import login_action, logout_action, register_action
from .base import (
    display_friends_table,
    display_global_table,
    friends_competition,
    friends_returns_graph,
    global_competition,
    landing_page,
    page_not_found,
)
from .portfolio import portfolio, returns_graph
from .profile import (
    friend,
    logged_in_user_profile,
    profile,
    profile_returns,
    respond_to_friend_request,
)
from .transactions import transaction_input

__all__ = [
    "global_competition",
    "friend",
    "friends_competition",
    "landing_page",
    "login_action",
    "logged_in_user_profile",
    "logout_action",
    "page_not_found",
    "register_action",
    "respond_to_friend_request",
    "transaction_input",
    "profile",
    "portfolio",
    "display_friends_table",
    "display_global_table",
    "profile_returns",
    "returns_graph",
    "friends_returns_graph",
]
