# inventory/views/__init__.py
"""
Views package for inventory app.
Imports all views for backward compatibility with existing urls.py
"""

# CRUD views
from .printer_views import (
    add_printer,
    edit_printer,
    delete_printer,
    history_view,
    printer_change_history,
    run_inventory,
    run_inventory_all,
    poll_printer,  # 🆕
)

# API views
from .api_views import (
    api_printers,
    api_printer,
    api_probe_serial,
    api_models_by_manufacturer,
    api_all_printer_models,
    api_system_status,
    api_status_statistics,
)

# Export views
from .export_views import (
    export_excel,
    export_amb,
)

# Report views
from .report_views import (
    generate_email_from_inventory,
)

# Web parser views
from .web_parser_views import (
    save_web_parsing_rule,
    get_rules,
    test_xpath,
    fetch_page,
    proxy_page,
    execute_action,
    export_printer_xml,
    get_templates,
    get_all_templates,
    save_template,
    apply_template,
    delete_template,
)

# Vue.js test view
from .vue_test_view import (
    vue_test_view,
)

# Vue.js printer list view
from .printer_list_vue_view import (
    printer_list_vue,
)

from .printer_form_vue_view import (
    printer_form_vue_add,
    printer_form_vue_edit,
)

from .amb_export_vue_view import (
    amb_export_vue,
)

from .web_parser_vue_view import (
    web_parser_setup_vue,
)

__all__ = [
    # CRUD
    'printer_list_vue',
    'printer_form_vue_add',
    'printer_form_vue_edit',
    'amb_export_vue',
    'add_printer',
    'edit_printer',
    'delete_printer',
    'history_view',
    'printer_change_history',
    'run_inventory',
    'run_inventory_all',
    'poll_printer',

    # API
    'api_printers',
    'api_printer',
    'api_probe_serial',
    'api_models_by_manufacturer',
    'api_all_printer_models',
    'api_system_status',
    'api_status_statistics',

    # Export
    'export_excel',
    'export_amb',

    # Report
    'generate_email_from_inventory',

    # Web parser
    'web_parser_setup_vue',
    'save_web_parsing_rule',
    'get_rules',
    'test_xpath',
    'fetch_page',
    'proxy_page',
    'execute_action',
    'export_printer_xml',
    'get_templates',
    'get_all_templates',
    'save_template',
    'apply_template',
    'delete_template',

    # Vue.js test
    'vue_test_view',
]
