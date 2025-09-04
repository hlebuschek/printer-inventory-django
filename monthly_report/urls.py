from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.MonthListView.as_view(), name='month_list'),
    path('upload/', views.upload_excel, name='upload_excel'),

    # API — ставим выше маршрута месяца и даём имя, как в шаблоне
    path('api/update-counters/<int:pk>/', views.api_update_counters,
         name='api_update_counters'),

    # Страница месяца — ограничиваем форматом YYYY-MM, чтобы не ловить /api/...
    re_path(r'^(?P<month>\d{4}-\d{2})/$', views.MonthDetailView.as_view(),
            name='month_detail'),
]
