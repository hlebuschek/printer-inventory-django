from django.urls import path

from .views import permissions_overview, theme_preference_api

app_name = "access"

urlpatterns = [
    path("permissions/", permissions_overview, name="permissions_overview"),
    path("api/theme/", theme_preference_api, name="theme_preference_api"),
]