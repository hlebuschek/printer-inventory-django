from django.urls import path
from . import views, api_views, vue_views

app_name = "contracts"

urlpatterns = [
    # ═══════════════════════════════════════════════════════════════
    # VUE.JS PAGES
    # ═══════════════════════════════════════════════════════════════
    path("", vue_views.contract_device_list_vue, name="list"),

    # ═══════════════════════════════════════════════════════════════
    # HTML PAGES (старые версии)
    # ═══════════════════════════════════════════════════════════════
    path("old/", views.ContractDeviceListView.as_view(), name="list_old"),
    path("new/", views.ContractDeviceCreateView.as_view(), name="new"),
    path("<int:pk>/edit/", views.ContractDeviceUpdateView.as_view(), name="edit"),

    # ═══════════════════════════════════════════════════════════════
    # API ENDPOINTS (для Vue.js)
    # ═══════════════════════════════════════════════════════════════
    path("api/devices/", api_views.api_contract_devices, name="api_devices"),
    path("api/filters/", api_views.api_contract_filters, name="api_filters"),
    path("api/models-by-manufacturer/", api_views.api_device_models_by_manufacturer, name="api_models_by_manufacturer"),

    # ═══════════════════════════════════════════════════════════════
    # API ENDPOINTS (старые, для совместимости)
    # ═══════════════════════════════════════════════════════════════
    path("api/<int:pk>/update/", views.contractdevice_update_api, name="api_update"),
    path("api/<int:pk>/delete/", views.contractdevice_delete_api, name="api_delete"),
    path("api/create/", views.contractdevice_create_api, name="api_create"),
    path("api/lookup-by-serial/", views.contractdevice_lookup_by_serial_api, name="api_lookup_by_serial"),

    # ═══════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════
    path("export/", views.contractdevice_export_excel, name="export"),
    path("<int:pk>/email/", views.generate_email_msg, name="generate_email"),
]