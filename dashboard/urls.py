from django.urls import path

from dashboard.views.api_views import (
    api_glpi_cross_check,
    api_glpi_cross_check_refresh,
    api_low_consumables,
    api_manufacturer_distribution,
    api_org_devices,
    api_org_summary,
    api_organizations,
    api_poll_stats,
    api_print_trend,
    api_printer_status,
    api_problem_printers,
    api_recent_activity,
    api_report_months,
    api_silent_printers,
    api_top_by_volume,
    export_org_devices,
    export_poll_stats,
    export_print_trend,
    start_statistics_export,
    statistics_export_download,
    statistics_export_status,
)
from dashboard import api_views_drf
from dashboard.views.page_views import dashboard_index

app_name = "dashboard"

urlpatterns = [
    path("", dashboard_index, name="index"),
    # API
    path("api/printer-status/", api_printer_status, name="api_printer_status"),
    path("api/poll-stats/", api_poll_stats, name="api_poll_stats"),
    path("api/low-consumables/", api_low_consumables, name="api_low_consumables"),
    path("api/problem-printers/", api_problem_printers, name="api_problem_printers"),
    path("api/print-trend/", api_print_trend, name="api_print_trend"),
    path("api/org-summary/", api_org_summary, name="api_org_summary"),
    path("api/recent-activity/", api_recent_activity, name="api_recent_activity"),
    path("api/organizations/", api_organizations, name="api_organizations"),
    path("api/org-devices/", api_org_devices, name="api_org_devices"),
    path("api/org-devices/export/", export_org_devices, name="export_org_devices"),
    # GLPI cross-check
    path("api/glpi-cross-check/", api_glpi_cross_check, name="api_glpi_cross_check"),
    path("api/glpi-cross-check/refresh/", api_glpi_cross_check_refresh, name="api_glpi_cross_check_refresh"),
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path("api/v2/printer-status/", api_views_drf.api_printer_status_drf, name="api_v2_printer_status"),
    path("api/v2/poll-stats/", api_views_drf.api_poll_stats_drf, name="api_v2_poll_stats"),
    path("api/v2/low-consumables/", api_views_drf.api_low_consumables_drf, name="api_v2_low_consumables"),
    path("api/v2/problem-printers/", api_views_drf.api_problem_printers_drf, name="api_v2_problem_printers"),
    path("api/v2/print-trend/", api_views_drf.api_print_trend_drf, name="api_v2_print_trend"),
    path("api/v2/org-devices/", api_views_drf.api_org_devices_drf, name="api_v2_org_devices"),
    path("api/v2/org-summary/", api_views_drf.api_org_summary_drf, name="api_v2_org_summary"),
    path("api/v2/recent-activity/", api_views_drf.api_recent_activity_drf, name="api_v2_recent_activity"),
    path("api/v2/organizations/", api_views_drf.api_organizations_drf, name="api_v2_organizations"),
    path("api/v2/glpi-cross-check/", api_views_drf.api_glpi_cross_check_drf, name="api_v2_glpi_cross_check"),
    # Excel exports
    path("api/print-trend/export/", export_print_trend, name="export_print_trend"),
    path("api/poll-stats/export/", export_poll_stats, name="export_poll_stats"),
    # Статистика устройств (виджеты)
    path("api/silent-printers/", api_silent_printers, name="api_silent_printers"),
    path("api/top-by-volume/", api_top_by_volume, name="api_top_by_volume"),
    path("api/manufacturer-distribution/", api_manufacturer_distribution, name="api_manufacturer_distribution"),
    path("api/report-months/", api_report_months, name="api_report_months"),
    # Полная XLSX-выгрузка статистики (Celery + polling)
    path("api/statistics-export/start/", start_statistics_export, name="statistics_export_start"),
    path("api/statistics-export/<str:task_id>/status/", statistics_export_status, name="statistics_export_status"),
    path(
        "api/statistics-export/<str:task_id>/download/",
        statistics_export_download,
        name="statistics_export_download",
    ),
]
