from .views import permissions_overview
from django.urls import path

app_name = "access"

urlpatterns = [
    path("permissions/", permissions_overview, name="permissions_overview"),
]