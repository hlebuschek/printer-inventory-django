# inventory/views/__init__.py
"""
Views package for inventory app.
Imports all views for backward compatibility with existing urls.py
"""

# CRUD views
from .printer_views import (
    printer_list,
    add_printer,
    edit_printer,
    delete_printer,
    history_view,
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
    web_parser_setup,
    save_web_parsing_rule,
    test_xpath,
    fetch_page,
    proxy_page,
    execute_action,
    export_printer_xml,
)

__all__ = [
    # CRUD
    'printer_list',
    'add_printer',
    'edit_printer',
    'delete_printer',
    'history_view',
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
    'web_parser_setup',
    'save_web_parsing_rule',
    'test_xpath',
    'fetch_page',
    'proxy_page',
    'execute_action',
    'export_printer_xml',
]