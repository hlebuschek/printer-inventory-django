from django.urls import path

from . import api_views, api_views_drf, api_views_import, views, vue_views

app_name = "contracts"

urlpatterns = [
    # ═══════════════════════════════════════════════════════════════
    # VUE.JS PAGES
    # ═══════════════════════════════════════════════════════════════
    path("", vue_views.contract_device_list_vue, name="list"),
    path("import/", vue_views.contract_import_vue, name="import"),
    # ═══════════════════════════════════════════════════════════════
    # МАССОВЫЙ ИМПОРТ ИЗ EXCEL
    # ═══════════════════════════════════════════════════════════════
    path("api/import/sessions/", api_views_import.create_session, name="api_import_create_session"),
    path("api/import/sessions/<int:pk>/", api_views_import.delete_session, name="api_import_delete_session"),
    path("api/import/sessions/<int:pk>/files/", api_views_import.upload_file, name="api_import_upload"),
    path("api/import/sessions/<int:pk>/preview/", api_views_import.preview, name="api_import_preview"),
    path("api/import/sessions/<int:pk>/decisions/", api_views_import.set_decisions, name="api_import_decisions"),
    path("api/import/sessions/<int:pk>/apply/", api_views_import.apply, name="api_import_apply"),
    path("api/import/sessions/<int:pk>/missing/", api_views_import.missing, name="api_import_missing"),
    path(
        "api/import/sessions/<int:pk>/missing/export/",
        api_views_import.missing_export,
        name="api_import_missing_export",
    ),
    path("api/import/sessions/<int:pk>/autopoll/", api_views_import.autopoll_list, name="api_import_autopoll"),
    path(
        "api/import/sessions/<int:pk>/autopoll/probe/",
        api_views_import.autopoll_probe,
        name="api_import_autopoll_probe",
    ),
    path(
        "api/import/sessions/<int:pk>/autopoll/create/",
        api_views_import.autopoll_create,
        name="api_import_autopoll_create",
    ),
    path(
        "api/import/sessions/<int:pk>/autopoll/<int:candidate_id>/verify/",
        api_views_import.autopoll_verify,
        name="api_import_autopoll_verify",
    ),
    # ═══════════════════════════════════════════════════════════════
    # API ENDPOINTS (для Vue.js)
    # ═══════════════════════════════════════════════════════════════
    path("api/devices/", api_views.api_contract_devices, name="api_devices"),
    path("api/filters/", api_views.api_contract_filters, name="api_filters"),
    path("api/models-by-manufacturer/", api_views.api_device_models_by_manufacturer, name="api_models_by_manufacturer"),
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path("api/v2/devices/", api_views_drf.api_contract_devices_drf, name="api_v2_devices"),
    path("api/v2/filters/", api_views_drf.api_contract_filters_drf, name="api_v2_filters"),
    path(
        "api/v2/models-by-manufacturer/",
        api_views_drf.api_device_models_by_manufacturer_drf,
        name="api_v2_models_by_manufacturer",
    ),
    # ═══════════════════════════════════════════════════════════════
    # API ENDPOINTS (старые, для совместимости)
    # ═══════════════════════════════════════════════════════════════
    path("api/<int:pk>/update/", views.contractdevice_update_api, name="api_update"),
    path("api/<int:pk>/delete/", views.contractdevice_delete_api, name="api_delete"),
    path("api/<int:pk>/acceptance-docs/upload/", views.acceptance_docs_upload, name="api_acceptance_docs_upload"),
    path("api/acceptance-docs/<int:doc_id>/", views.acceptance_doc_download, name="api_acceptance_doc_download"),
    path(
        "api/acceptance-docs/<int:doc_id>/delete/",
        views.acceptance_doc_delete,
        name="api_acceptance_doc_delete",
    ),
    path("api/create/", views.contractdevice_create_api, name="api_create"),
    path("api/lookup-by-serial/", views.contractdevice_lookup_by_serial_api, name="api_lookup_by_serial"),
    # ═══════════════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════════════
    path("export/", views.contractdevice_export_excel, name="export"),
    path("<int:pk>/email/", views.generate_email_msg, name="generate_email"),
    # ═══════════════════════════════════════════════════════════════
    # CHANGE HISTORY
    # ═══════════════════════════════════════════════════════════════
    path("api/<int:pk>/history/", views.contractdevice_change_history, name="api_history"),
]
