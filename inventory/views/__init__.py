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
    test_xpath,
)
from .web_parser_vue_view import (
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
    "save_web_parsing_rule",
    "get_rules",
    "test_xpath",
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
]
