from django.urls import path

from .views import okdesk_token_api, permissions_overview, theme_preference_api

app_name = "access"

urlpatterns = [
    path("permissions/", permissions_overview, name="permissions_overview"),
    path("api/theme/", theme_preference_api, name="theme_preference_api"),
    path("api/okdesk-token/", okdesk_token_api, name="okdesk_token_api"),
]
