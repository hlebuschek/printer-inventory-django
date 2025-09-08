from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.MonthListView.as_view(), name='month_list'),
    path('upload/', views.upload_excel, name='upload_excel'),
    path('api/update-counters/<int:pk>/', views.api_update_counters, name='api_update_counters'),
    path('api/sync/<int:year>/<int:month>/', views.api_sync_from_inventory, name='api_sync_from_inventory'),
    path('api/revert-change/<int:change_id>/', views.revert_change, name='revert_change'),
    path('history/<int:pk>/', views.change_history_view, name='change_history'),
    re_path(r'^(?P<month>\d{4}-\d{2})/$', views.MonthDetailView.as_view(), name='month_detail'),
]