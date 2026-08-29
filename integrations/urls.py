from django.urls import path

from . import views, api_views_drf

app_name = "integrations"

urlpatterns = [
    # GLPI интеграция
    path("glpi/check-device/<int:device_id>/", views.check_device_glpi, name="check_device_glpi"),
    path("glpi/check-multiple/", views.check_multiple_devices_glpi, name="check_multiple_devices_glpi"),
    path("glpi/sync-status/<int:device_id>/", views.get_device_sync_status, name="get_device_sync_status"),
    path("glpi/conflicts/", views.get_glpi_conflicts, name="get_glpi_conflicts"),
    path("glpi/not-found/", views.get_devices_not_in_glpi_view, name="get_devices_not_in_glpi"),
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path(
        "api/v2/glpi/check-device/<int:device_id>/",
        api_views_drf.CheckDeviceGLPIAPIView.as_view(),
        name="api_v2_check_device_glpi",
    ),
    path(
        "api/v2/glpi/check-multiple/",
        api_views_drf.CheckMultipleDevicesGLPIAPIView.as_view(),
        name="api_v2_check_multiple_devices_glpi",
    ),
    path(
        "api/v2/glpi/sync-status/<int:device_id>/",
        api_views_drf.get_device_sync_status_drf,
        name="api_v2_get_device_sync_status",
    ),
    path("api/v2/glpi/conflicts/", api_views_drf.get_glpi_conflicts_drf, name="api_v2_get_glpi_conflicts"),
    path("api/v2/glpi/not-found/", api_views_drf.get_devices_not_in_glpi_drf, name="api_v2_get_devices_not_in_glpi"),
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
    path("okdesk/api/instances/", views.api_okdesk_instances, name="okdesk_instances"),
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
    # ═══════════════════════════════════════════════════════════════
    # DRF API ENDPOINTS (для OpenAPI документации)
    # ═══════════════════════════════════════════════════════════════
    path("api/v2/okdesk/issues/<int:device_id>/", api_views_drf.get_okdesk_issues_drf, name="api_v2_get_okdesk_issues"),
    path(
        "api/v2/okdesk/create-issue/",
        api_views_drf.CreateOkdeskIssueAPIView.as_view(),
        name="api_v2_create_okdesk_issue",
    ),
    path("api/v2/okdesk/daily-stats/", api_views_drf.api_okdesk_daily_stats_drf, name="api_v2_okdesk_daily_stats"),
    path(
        "api/v2/okdesk/daily-comments/",
        api_views_drf.api_okdesk_daily_comments_drf,
        name="api_v2_okdesk_daily_comments",
    ),
    path(
        "api/v2/okdesk/active-grouped/",
        api_views_drf.api_okdesk_active_grouped_drf,
        name="api_v2_okdesk_active_grouped",
    ),
    path(
        "api/v2/okdesk/by-status/<str:status_name>/",
        api_views_drf.api_okdesk_by_status_drf,
        name="api_v2_okdesk_by_status",
    ),
    path("api/v2/okdesk/closed/", api_views_drf.api_okdesk_closed_drf, name="api_v2_okdesk_closed"),
    path("api/v2/okdesk/authors/", api_views_drf.api_okdesk_authors_drf, name="api_v2_okdesk_authors"),
    path("api/v2/okdesk/analytics/", api_views_drf.api_okdesk_analytics_drf, name="api_v2_okdesk_analytics"),
    path(
        "api/v2/okdesk/issue/<int:issue_id>/",
        api_views_drf.api_okdesk_issue_detail_drf,
        name="api_v2_okdesk_issue_detail",
    ),
    path(
        "api/v2/okdesk/export/created/<str:date_str>/",
        api_views_drf.export_okdesk_created_drf,
        name="api_v2_okdesk_export_created",
    ),
    path(
        "api/v2/okdesk/export/closed/<str:date_str>/",
        api_views_drf.export_okdesk_closed_drf,
        name="api_v2_okdesk_export_closed",
    ),
    path(
        "api/v2/okdesk/export/by-status/<str:status_name>/",
        api_views_drf.export_okdesk_by_status_drf,
        name="api_v2_okdesk_export_by_status",
    ),
    path(
        "api/v2/okdesk/export/active-all/",
        api_views_drf.export_okdesk_active_all_drf,
        name="api_v2_okdesk_export_active_all",
    ),
    path(
        "api/v2/okdesk/export/active-filtered/",
        api_views_drf.export_okdesk_active_filtered_drf,
        name="api_v2_okdesk_export_active_filtered",
    ),
    path(
        "api/v2/okdesk/export/closed-filtered/",
        api_views_drf.export_okdesk_closed_filtered_drf,
        name="api_v2_okdesk_export_closed_filtered",
    ),
    path(
        "api/v2/okdesk/export/<str:task_id>/download/",
        api_views_drf.okdesk_export_download_drf,
        name="api_v2_okdesk_export_download",
    ),
    path(
        "api/v2/okdesk/issue/<int:issue_id>/refresh-comments/",
        api_views_drf.OkdeskRefreshIssueCommentsAPIView.as_view(),
        name="api_v2_okdesk_refresh_issue_comments",
    ),
    path(
        "api/v2/okdesk/issue/<int:issue_id>/comments/",
        api_views_drf.OkdeskPostCommentAPIView.as_view(),
        name="api_v2_okdesk_post_comment",
    ),
    path("api/v2/okdesk/sync-now/", api_views_drf.OkdeskSyncNowAPIView.as_view(), name="api_v2_okdesk_sync_now"),
    path("api/v2/okdesk/sync-status/", api_views_drf.okdesk_sync_status_drf, name="api_v2_okdesk_sync_status"),
]
