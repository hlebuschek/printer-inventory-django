from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    # GLPI интеграция
    path("glpi/check-device/<int:device_id>/", views.check_device_glpi, name="check_device_glpi"),
    path("glpi/check-multiple/", views.check_multiple_devices_glpi, name="check_multiple_devices_glpi"),
    path("glpi/sync-status/<int:device_id>/", views.get_device_sync_status, name="get_device_sync_status"),
    path("glpi/conflicts/", views.get_glpi_conflicts, name="get_glpi_conflicts"),
    path("glpi/not-found/", views.get_devices_not_in_glpi_view, name="get_devices_not_in_glpi"),
    # Okdesk
    path("okdesk/issues/<int:device_id>/", views.get_okdesk_issues, name="get_okdesk_issues"),
    path("okdesk/create-issue/", views.create_okdesk_issue, name="create_okdesk_issue"),
    # Service Desk dashboard (Vue page + JSON API + Excel-экспорт)
    path("okdesk/", views.okdesk_dashboard_view, name="okdesk_dashboard"),
    path("okdesk/api/daily-stats/", views.api_okdesk_daily_stats, name="okdesk_daily_stats"),
    path("okdesk/api/daily-comments/", views.api_okdesk_daily_comments, name="okdesk_daily_comments"),
    path("okdesk/api/active-grouped/", views.api_okdesk_active_grouped, name="okdesk_active_grouped"),
    path("okdesk/api/by-status/<str:status_name>/", views.api_okdesk_by_status, name="okdesk_by_status"),
    path("okdesk/api/closed/", views.api_okdesk_closed, name="okdesk_closed"),
    path("okdesk/api/authors/", views.api_okdesk_authors, name="okdesk_authors"),
    path("okdesk/api/analytics/", views.api_okdesk_analytics, name="okdesk_analytics"),
    path("okdesk/api/issue/<int:issue_id>/", views.api_okdesk_issue_detail, name="okdesk_issue_detail"),
    path(
        "okdesk/api/issue/<int:issue_id>/refresh-comments/",
        views.okdesk_refresh_issue_comments,
        name="okdesk_refresh_issue_comments",
    ),
    path("okdesk/api/issue/<int:issue_id>/comments/", views.okdesk_post_comment, name="okdesk_post_comment"),
    path("okdesk/export/created/<str:date_str>/", views.export_okdesk_created, name="okdesk_export_created"),
    path("okdesk/export/closed/<str:date_str>/", views.export_okdesk_closed, name="okdesk_export_closed"),
    path("okdesk/export/by-status/<str:status_name>/", views.export_okdesk_by_status, name="okdesk_export_by_status"),
    path("okdesk/export/active-all/", views.export_okdesk_active_all, name="okdesk_export_active_all"),
    path(
        "okdesk/export/active-filtered/",
        views.export_okdesk_active_filtered,
        name="okdesk_export_active_filtered",
    ),
    path(
        "okdesk/export/closed-filtered/",
        views.export_okdesk_closed_filtered,
        name="okdesk_export_closed_filtered",
    ),
    path("okdesk/sync-now/", views.okdesk_sync_now, name="okdesk_sync_now"),
    path("okdesk/sync-status/", views.okdesk_sync_status, name="okdesk_sync_status"),
    path(
        "okdesk/api/export/<str:task_id>/download/",
        views.okdesk_export_download,
        name="okdesk_export_download",
    ),
]
