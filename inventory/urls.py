# inventory/urls.py
from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    # ═══════════════════════════════════════════════════════════════
    # VUE.JS PAGES
    # ═══════════════════════════════════════════════════════════════
    path("vue-test/", views.vue_test_view, name="vue_test"),

    # Main inventory page - now using Vue.js!
    path("", views.printer_list_vue, name="printer_list"),

    # Old HTML version (for backup/comparison during transition)
    path("old/", views.printer_list, name="printer_list_old"),

    # ═══════════════════════════════════════════════════════════════
    # CRUD ОПЕРАЦИИ С ПРИНТЕРАМИ
    # ═══════════════════════════════════════════════════════════════
    # Form pages (GET - show Vue.js form, POST - process Django form)
    path("add/", views.printer_form_vue_add, name="add_printer"),
    path("<int:pk>/edit-form/", views.printer_form_vue_edit, name="edit_printer_form"),

    # API endpoints for form submission (POST only)
    path("<int:pk>/edit/", views.edit_printer, name="edit_printer"),
    path("add-submit/", views.add_printer, name="add_printer_submit"),
    path("<int:pk>/delete/", views.delete_printer, name="delete_printer"),
    path("<int:pk>/history/", views.history_view, name="history"),

    # ═══════════════════════════════════════════════════════════════
    # ОПРОС ПРИНТЕРОВ
    # ═══════════════════════════════════════════════════════════════
    path("<int:pk>/run/", views.run_inventory, name="run_inventory"),
    path("run_all/", views.run_inventory_all, name="run_inventory_all"),
    path('<int:printer_id>/poll/', views.poll_printer, name='poll_printer'),

    # ═══════════════════════════════════════════════════════════════
    # API ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    path("api/printers/", views.api_printers, name="api_printers"),
    path("api/printer/<int:pk>/", views.api_printer, name="api_printer"),
    path("api/probe-serial/", views.api_probe_serial, name="api_probe_serial"),
    path('api/models-by-manufacturer/', views.api_models_by_manufacturer, name='api_models_by_manufacturer'),
    path('api/all-printer-models/', views.api_all_printer_models, name='api_all_printer_models'),
    path("api/system-status/", views.api_system_status, name="api_system_status"),
    path("api/status-statistics/", views.api_status_statistics, name="api_status_statistics"),

    # ═══════════════════════════════════════════════════════════════
    # ЭКСПОРТ ДАННЫХ
    # ═══════════════════════════════════════════════════════════════
    path("export/", views.export_excel, name="export_excel"),
    # AMB export - Vue.js page (GET) + old handler (POST)
    path("export-amb/", views.amb_export_vue, name="export_amb"),
    path("<int:pk>/email/", views.generate_email_from_inventory, name="generate_email"),

    # ═══════════════════════════════════════════════════════════════
    # ВЕБ-ПАРСИНГ
    # ═══════════════════════════════════════════════════════════════

    # Основная страница настройки веб-парсинга
    path('<int:printer_id>/web-parser/', views.web_parser_setup, name='web_parser_setup'),

    # API для работы с правилами веб-парсинга
    path('api/web-parser/save-rule/', views.save_web_parsing_rule, name='save_web_parsing_rule'),
    path('api/web-parser/test-xpath/', views.test_xpath, name='test_xpath'),
    path('api/web-parser/fetch-page/', views.fetch_page, name='fetch_page'),
    path('api/web-parser/proxy-page/', views.proxy_page, name='proxy_page'),
    path('api/web-parser/execute-action/', views.execute_action, name='execute_action'),

    # Экспорт XML из веб-парсинга
    path('<int:printer_id>/web-parser/export-xml/', views.export_printer_xml, name='export_printer_xml'),
    path('api/web-parser/templates/', views.get_templates, name='get_templates'),
    path('api/web-parser/save-template/', views.save_template, name='save_template'),
    path('api/web-parser/apply-template/', views.apply_template, name='apply_template'),
    path('api/web-parser/delete-template/<int:template_id>/', views.delete_template, name='delete_template'),
]