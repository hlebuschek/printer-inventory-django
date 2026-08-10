from django.urls import path

from .views import (
    okdesk_token_api,
    permissions_overview,
    theme_preference_api,
    user_delete_api,
    user_management,
    user_save_api,
    users_api,
)

app_name = "access"

urlpatterns = [
    path("permissions/", permissions_overview, name="permissions_overview"),
    path("users/", user_management, name="user_management"),
    path("api/theme/", theme_preference_api, name="theme_preference_api"),
    path("api/okdesk-token/", okdesk_token_api, name="okdesk_token_api"),
    path("api/users/", users_api, name="users_api"),
    path("api/users/save/", user_save_api, name="user_save_api"),
    path("api/users/delete/", user_delete_api, name="user_delete_api"),
]
