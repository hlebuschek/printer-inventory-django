from django.urls import path
from dashboard.views.page_views import dashboard_index
from dashboard.views.api_views import (
    api_printer_status,
    api_poll_stats,
    api_low_consumables,
    api_problem_printers,
    api_print_trend,
    api_org_summary,
    api_org_devices,
    api_recent_activity,
    api_organizations,
    export_print_trend,
    export_poll_stats,
    export_org_devices,
)

app_name = 'dashboard'

urlpatterns = [
    path('', dashboard_index, name='index'),

    # API
    path('api/printer-status/', api_printer_status, name='api_printer_status'),
    path('api/poll-stats/', api_poll_stats, name='api_poll_stats'),
    path('api/low-consumables/', api_low_consumables, name='api_low_consumables'),
    path('api/problem-printers/', api_problem_printers, name='api_problem_printers'),
    path('api/print-trend/', api_print_trend, name='api_print_trend'),
    path('api/org-summary/', api_org_summary, name='api_org_summary'),
    path('api/recent-activity/', api_recent_activity, name='api_recent_activity'),
    path('api/organizations/', api_organizations, name='api_organizations'),
    path('api/org-devices/', api_org_devices, name='api_org_devices'),
    path('api/org-devices/export/', export_org_devices, name='export_org_devices'),

    # Excel exports
    path('api/print-trend/export/', export_print_trend, name='export_print_trend'),
    path('api/poll-stats/export/', export_poll_stats, name='export_poll_stats'),
]
