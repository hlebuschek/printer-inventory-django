from django.urls import path

from . import api_views, api_views_drf, api_views_import, api_views_requests, views, vue_views

app_name = "contracts"

urlpatterns = [
    # ═══════════════════════════════════════════════════════════════
    # VUE.JS PAGES
    # ═══════════════════════════════════════════════════════════════
    path("", vue_views.contract_device_list_vue, name="list"),
    path("import/", vue_views.contract_import_vue, name="import"),
    path("requests/", vue_views.service_request_journal_vue, name="request_journal"),
    # ═══════════════════════════════════════════════════════════════
    # ЖУРНАЛ ЗАЯВОК ПОДРЯДЧИКУ
    # ═══════════════════════════════════════════════════════════════
    path("api/requests/", api_views_requests.api_service_requests, name="api_requests"),
    path("api/requests/<int:pk>/restore/", api_views_requests.api_service_request_restore, name="api_request_restore"),
    path("api/requests/<int:pk>/act/", api_views_requests.api_service_request_act, name="api_request_act"),
    path(
        "api/requests/<int:pk>/messages/",
        api_views_requests.api_service_request_messages,
        name="api_request_messages",
    ),
    path("api/requests/<int:pk>/reply/", api_views_requests.api_service_request_reply, name="api_request_reply"),
    path(
        "api/requests/<int:pk>/close-by-message/<int:message_id>/",
        api_views_requests.api_service_request_close_by_message,
        name="api_request_close_by_message",
    ),
    path(
        "api/requests/<int:pk>/subscribe/",
        api_views_requests.api_service_request_subscribe,
        name="api_request_subscribe",
    ),
    path("api/requests/export/", api_views_requests.api_service_requests_export, name="api_requests_export"),
    path(
        "api/requests/export/<str:task_id>/",
        api_views_requests.api_service_requests_export_download,
        name="api_requests_export_download",
    ),
    path("api/requests/analytics/", api_views_requests.api_service_requests_analytics, name="api_requests_analytics"),
    path("api/requests/colleagues/", api_views_requests.api_reply_colleagues, name="api_reply_colleagues"),
    path("api/requests/messages/unmatched/", api_views_requests.api_unmatched_messages, name="api_unmatched_messages"),
    path(
        "api/requests/okdesk/unmatched/",
        api_views_requests.api_unmatched_okdesk_issues,
        name="api_unmatched_okdesk_issues",
    ),
    path("api/requests/messages/<int:pk>/attach/", api_views_requests.api_message_attach, name="api_message_attach"),
    path(
        "api/requests/attachments/<int:pk>/fetch/",
        api_views_requests.api_attachment_fetch,
        name="api_attachment_fetch",
    ),
    path(
        "api/requests/okdesk/device-search/",
        api_views_requests.api_okdesk_device_search,
        name="api_okdesk_device_search",
    ),
    path(
        "api/requests/okdesk/<int:issue_id>/import/",
        api_views_requests.api_okdesk_issue_import,
        name="api_okdesk_issue_import",
    ),
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
