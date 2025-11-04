# inventory/urls.py
from django.urls import path
from . import views
from .views import web_parser_views
from .views import printer_views


app_name = "inventory"

urlpatterns = [
    path("", views.printer_list, name="printer_list"),            # /printers/
    path("add/", views.add_printer, name="add_printer"),          # /printers/add/
    path("<int:pk>/edit/", views.edit_printer, name="edit_printer"),
    path("<int:pk>/delete/", views.delete_printer, name="delete_printer"),
    path("<int:pk>/history/", views.history_view, name="history"),
    path("<int:pk>/run/", views.run_inventory, name="run_inventory"),
    path("run_all/", views.run_inventory_all, name="run_inventory_all"),

    path("api/printers/", views.api_printers, name="api_printers"),
    path("api/printer/<int:pk>/", views.api_printer, name="api_printer"),
    path("api/probe-serial/", views.api_probe_serial, name="api_probe_serial"),
    path('api/models-by-manufacturer/', views.api_models_by_manufacturer, name='api_models_by_manufacturer'),
    path('api/all-printer-models/', views.api_all_printer_models, name='api_all_printer_models'),
    path("export/", views.export_excel, name="export_excel"),
    path("export-amb/", views.export_amb, name="export_amb"),
    path("<int:pk>/email/", views.generate_email_from_inventory, name="generate_email"),
    path("api/system-status/", views.api_system_status, name="api_system_status"),
    path("api/status-statistics/", views.api_status_statistics, name="api_status_statistics"),
    # Веб-парсинг
    path('<int:printer_id>/web-parser/', views.web_parser_setup, name='web_parser_setup'),    path('<int:printer_id>/web-parser/', web_parser_views.web_parser_setup, name='web_parser_setup'),
    path('<int:printer_id>/web-parser/', web_parser_views.web_parser_setup, name='web_parser_setup'),
    path('api/web-parser/save-rule/', web_parser_views.save_web_parsing_rule, name='save_web_parsing_rule'),
    path('api/web-parser/test-xpath/', web_parser_views.test_xpath, name='test_xpath'),
    path('api/web-parser/fetch-page/', web_parser_views.fetch_page, name='fetch_page'),
    path('api/web-parser/proxy-page/', web_parser_views.proxy_page, name='proxy_page'),
    path('api/web-parser/execute-action/', web_parser_views.execute_action, name='execute_action'),  # ← НОВЫЙ
    path('<int:printer_id>/poll/', printer_views.poll_printer, name='poll_printer'),
]