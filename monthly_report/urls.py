from django.urls import path, re_path

from . import views, api_views_drf

urlpatterns = [
    path("", views.MonthListView.as_view(), name="month_list"),
    path("upload/", views.upload_excel, name="upload_excel"),
    path("api/months/", views.api_months_list, name="api_months_list"),
    path("api/month/<int:year>/<int:month>/", views.api_month_detail, name="api_month_detail"),
    path("api/update-counters/<int:pk>/", views.api_update_counters, name="api_update_counters"),
    path("api/sync/<int:year>/<int:month>/", views.api_sync_from_inventory, name="api_sync_from_inventory"),
    path("api/revert-change/<int:change_id>/", views.revert_change, name="revert_change"),
    path("api/reset-manual-flag/<int:pk>/", views.api_reset_manual_flag, name="api_reset_manual_flag"),
    path("api/reset-all-manual-flags/", views.reset_manual_flags, name="reset_manual_flags"),
    path("api/toggle-month-published/", views.api_toggle_month_published, name="api_toggle_month_published"),
    path("api/toggle-auto-sync/", views.api_toggle_auto_sync, name="api_toggle_auto_sync"),
    path("api/toggle-serial-override/", views.api_toggle_serial_override, name="api_toggle_serial_override"),
    path("api/delete-month/", views.api_delete_month, name="api_delete_month"),
    path("api/change-history/<int:pk>/", views.api_change_history, name="api_change_history"),
    path("api/month-users-stats/<int:year>/<int:month>/", views.api_month_users_stats, name="api_month_users_stats"),
    path("api/month-diff/<int:year>/<int:month>/", views.api_month_diff, name="api_month_diff"),
    path("api/month-changes/<int:year>/<int:month>/", views.api_month_changes_list, name="api_month_changes_list"),
    path(
        "api/device-report/<int:year>/<int:month>/<str:serial_number>/",
        views.api_device_report,
        name="api_device_report",
    ),
    path("history/<int:pk>/", views.change_history_view, name="change_history"),
    path("month-changes/<int:year>/<int:month>/", views.month_changes_view, name="month_changes"),
    # GLPI Export API
    path("api/glpi-export/start/", views.api_start_glpi_export, name="api_start_glpi_export"),
    path("api/glpi-export/status/<str:task_id>/", views.api_glpi_export_status, name="api_glpi_export_status"),
    path("<int:year>/<int:month>/export-excel/", views.export_month_excel, name="export_month_excel"),
    re_path(r"^(?P<month>\d{4}-\d{2})/$", views.MonthDetailView.as_view(), name="month_detail"),
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path("api/v2/months/", api_views_drf.api_months_list_drf, name="api_v2_months_list"),
    path("api/v2/month/<int:year>/<int:month>/", api_views_drf.api_month_detail_drf, name="api_v2_month_detail"),
    path(
        "api/v2/update-counters/<int:pk>/", api_views_drf.UpdateCountersAPIView.as_view(), name="api_v2_update_counters"
    ),
    path(
        "api/v2/sync/<int:year>/<int:month>/",
        api_views_drf.SyncFromInventoryAPIView.as_view(),
        name="api_v2_sync_from_inventory",
    ),
    path(
        "api/v2/reset-manual-flag/<int:pk>/",
        api_views_drf.ResetManualFlagAPIView.as_view(),
        name="api_v2_reset_manual_flag",
    ),
    path("api/v2/change-history/<int:pk>/", api_views_drf.api_change_history_drf, name="api_v2_change_history"),
    path("api/v2/month-diff/<int:year>/<int:month>/", api_views_drf.api_month_diff_drf, name="api_v2_month_diff"),
    path(
        "api/v2/toggle-serial-override/",
        api_views_drf.ToggleSerialOverrideAPIView.as_view(),
        name="api_v2_toggle_serial_override",
    ),
    path(
        "api/v2/toggle-month-published/",
        api_views_drf.ToggleMonthPublishedAPIView.as_view(),
        name="api_v2_toggle_month_published",
    ),
    path("api/v2/toggle-auto-sync/", api_views_drf.ToggleAutoSyncAPIView.as_view(), name="api_v2_toggle_auto_sync"),
    path("api/v2/delete-month/", api_views_drf.DeleteMonthAPIView.as_view(), name="api_v2_delete_month"),
    path(
        "api/v2/month-users-stats/<int:year>/<int:month>/",
        api_views_drf.api_month_users_stats_drf,
        name="api_v2_month_users_stats",
    ),
    path(
        "api/v2/month-changes/<int:year>/<int:month>/",
        api_views_drf.api_month_changes_list_drf,
        name="api_v2_month_changes_list",
    ),
    path(
        "api/v2/device-report/<int:year>/<int:month>/<str:serial_number>/",
        api_views_drf.api_device_report_drf,
        name="api_v2_device_report",
    ),
    path("api/v2/glpi-export/start/", api_views_drf.StartGLPIExportAPIView.as_view(), name="api_v2_start_glpi_export"),
    path(
        "api/v2/glpi-export/status/<str:task_id>/",
        api_views_drf.api_glpi_export_status_drf,
        name="api_v2_glpi_export_status",
    ),
]
