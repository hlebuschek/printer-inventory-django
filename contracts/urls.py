from django.urls import path
from .views import (
    ContractDeviceListView, ContractDeviceCreateView, ContractDeviceUpdateView,
    contractdevice_update_api, contractdevice_delete_api, contractdevice_create_api
)

app_name = "contracts"

urlpatterns = [
    path("",        ContractDeviceListView.as_view(), name="list"),
    path("new/",    ContractDeviceCreateView.as_view(), name="new"),
    path("<int:pk>/edit/", ContractDeviceUpdateView.as_view(), name="edit"),
    path("api/<int:pk>/update/", contractdevice_update_api, name="api_update"),
    path("api/<int:pk>/delete/", contractdevice_delete_api, name="api_delete"),
    path("api/create/", contractdevice_create_api, name="api_create"),
]
