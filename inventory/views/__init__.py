# inventory/views/__init__.py
"""
Views package for inventory app.
Imports all views for backward compatibility with existing urls.py
"""

from .amb_export_vue_view import (
    amb_export_vue,
)

# API views
from .api_views import (
    api_all_printer_models,
    api_models_by_manufacturer,
    api_printer,
    api_printer_replacement_history,
    api_printers,
    api_probe_serial,
    api_status_statistics,
    api_system_status,
)

# Export views
from .export_views import (
    export_amb,
    export_excel,
)
from .netscan_views import (
    ScanNetworkCreateView,
    ScanNetworkDeleteView,
    ScanNetworkDetailView,
    ScanNetworkListView,
    ScanNetworkUpdateView,
    netscan_device_move_ip,
    netscan_device_toggle_ignore,
    netscan_all_status,
    netscan_device_glpi_push,
    netscan_export,
    netscan_glpi_check,
    netscan_glpi_push_all,
    netscan_glpi_push_status,
    netscan_glpi_check_all,
    netscan_glpi_status,
    netscan_scan_all,
    netscan_run_now,
    netscan_run_status,
)
from .printer_form_vue_view import (
    printer_form_vue_add,
    printer_form_vue_edit,
)

# Vue.js printer list view
from .printer_list_vue_view import (
    printer_list_vue,
)

# CRUD views
from .printer_views import poll_printer  # 🆕
from .printer_views import (
    add_printer,
    delete_printer,
    edit_printer,
    history_view,
    printer_change_history,
    run_inventory,
    run_inventory_all,
)

# Report views
from .report_views import (
    generate_email_from_inventory,
)

# Vue.js test view
from .vue_test_view import (
    vue_test_view,
)

# Web parser views
from .web_parser_views import (
    apply_template,
    delete_template,
    execute_action,
    export_printer_xml,
    fetch_page,
    get_all_templates,
    get_rules,
    get_templates,
    proxy_page,
    save_template,
    save_web_parsing_rule,
    test_all_rules,
    test_xpath,
)
from .web_parser_vue_view import (
    update_polling_method,
    web_parser_setup_vue,
)

__all__ = [
    # CRUD
    "printer_list_vue",
    "printer_form_vue_add",
    "printer_form_vue_edit",
    "amb_export_vue",
    "add_printer",
    "edit_printer",
    "delete_printer",
    "history_view",
    "printer_change_history",
    "run_inventory",
    "run_inventory_all",
    "poll_printer",
    # API
    "api_printers",
    "api_printer",
    "api_probe_serial",
    "api_models_by_manufacturer",
    "api_all_printer_models",
    "api_system_status",
    "api_status_statistics",
    "api_printer_replacement_history",
    # Export
    "export_excel",
    "export_amb",
    # Report
    "generate_email_from_inventory",
    # Web parser
    "web_parser_setup_vue",
    "update_polling_method",
    "save_web_parsing_rule",
    "get_rules",
    "test_xpath",
    "test_all_rules",
    "fetch_page",
    "proxy_page",
    "execute_action",
    "export_printer_xml",
    "get_templates",
    "get_all_templates",
    "save_template",
    "apply_template",
    "delete_template",
    # Vue.js test
    "vue_test_view",
    # Network scan
    "ScanNetworkListView",
    "ScanNetworkCreateView",
    "ScanNetworkDetailView",
    "ScanNetworkUpdateView",
    "ScanNetworkDeleteView",
    "netscan_run_now",
    "netscan_run_status",
    "netscan_device_move_ip",
    "netscan_device_toggle_ignore",
    "netscan_glpi_check",
    "netscan_glpi_status",
    "netscan_scan_all",
    "netscan_glpi_check_all",
    "netscan_all_status",
    "netscan_export",
    "netscan_device_glpi_push",
    "netscan_glpi_push_all",
    "netscan_glpi_push_status",
]
