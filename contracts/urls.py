# contracts/urls.py
from django.urls import path
from .views import ContractDeviceListView, ContractDeviceCreateView, ContractDeviceUpdateView

app_name = "contracts"

urlpatterns = [
    path("", ContractDeviceListView.as_view(), name="list"),
    path("new/", ContractDeviceCreateView.as_view(), name="new"),
    path("<int:pk>/edit/", ContractDeviceUpdateView.as_view(), name="edit"),
]
