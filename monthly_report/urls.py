from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.MonthListView.as_view(), name='month_list'),
    path('upload/', views.upload_excel, name='upload_excel'),
    path('api/months/', views.api_months_list, name='api_months_list'),
    path('api/month/<int:year>/<int:month>/', views.api_month_detail, name='api_month_detail'),
    path('api/update-counters/<int:pk>/', views.api_update_counters, name='api_update_counters'),
    path('api/sync/<int:year>/<int:month>/', views.api_sync_from_inventory, name='api_sync_from_inventory'),
    path('api/revert-change/<int:change_id>/', views.revert_change, name='revert_change'),
    path('api/reset-manual-flag/<int:pk>/', views.api_reset_manual_flag, name='api_reset_manual_flag'),  # если есть
    path('history/<int:pk>/', views.change_history_view, name='change_history'),

    path('<int:year>/<int:month>/export-excel/', views.export_month_excel, name='export_month_excel'),

    re_path(r'^(?P<month>\d{4}-\d{2})/$', views.MonthDetailView.as_view(), name='month_detail'),
]