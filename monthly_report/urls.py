from django.urls import path
from .views import MonthListView, MonthDetailView, upload_excel

urlpatterns = [
    path('', MonthListView.as_view(), name='month_list'),
    path('upload/', upload_excel, name='upload_excel'),
    path('<str:month>/', MonthDetailView.as_view(), name='month_detail'),  # month как '2025-09'
]