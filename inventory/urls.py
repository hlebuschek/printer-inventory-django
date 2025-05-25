from django.urls import path
from . import views

urlpatterns = [
    path('', views.printer_list, name='printer_list'),
    path('add/', views.add_printer, name='add_printer'),
    path('edit/<int:pk>/', views.edit_printer, name='edit_printer'),
    path('delete/<int:pk>/', views.delete_printer, name='delete_printer'),
    path('history/<int:pk>/', views.history_view, name='history'),
    path('run/<int:pk>/', views.run_inventory, name='run_inventory'),
    path('run_all/', views.run_inventory_all, name='run_inventory_all'),
    path('api/printers/', views.api_printers, name='api_printers'),
    path('export/', views.export_excel, name='export_excel'),
    path('export-amb/', views.export_amb, name='export_amb'),

]
