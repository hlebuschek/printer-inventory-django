from django.urls import path
from . import views

app_name = "contracts"

urlpatterns = [
    path("", views.ContractDeviceListView.as_view(), name="list"),
    path("new/", views.ContractDeviceCreateView.as_view(), name="new"),  # можно оставить, но уже не обязателен
    path("<int:pk>/edit/", views.ContractDeviceUpdateView.as_view(), name="edit"),
    path("api/<int:pk>/update/", views.contractdevice_update_api, name="api_update"),
    path("api/<int:pk>/delete/", views.contractdevice_delete_api, name="api_delete"),
    path("api/create/", views.contractdevice_create_api, name="api_create"),  # ← НОВЫЙ
    path("export/", views.contractdevice_export_excel, name="export"),
]
