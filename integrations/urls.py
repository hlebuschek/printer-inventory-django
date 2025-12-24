from django.urls import path
from . import views

app_name = 'integrations'

urlpatterns = [
    # GLPI интеграция
    path('glpi/check-device/<int:device_id>/', views.check_device_glpi, name='check_device_glpi'),
    path('glpi/check-multiple/', views.check_multiple_devices_glpi, name='check_multiple_devices_glpi'),
    path('glpi/sync-status/<int:device_id>/', views.get_device_sync_status, name='get_device_sync_status'),
    path('glpi/conflicts/', views.get_glpi_conflicts, name='get_glpi_conflicts'),
    path('glpi/not-found/', views.get_devices_not_in_glpi_view, name='get_devices_not_in_glpi'),
]
