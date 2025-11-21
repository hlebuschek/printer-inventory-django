"""
Vue.js version of printer list view
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def printer_list_vue(request):
    """Vue.js версия страницы списка принтеров"""

    # Собираем permissions для передачи в Vue
    permissions = {
        'add_printer': request.user.has_perm('inventory.add_printer'),
        'change_printer': request.user.has_perm('inventory.change_printer'),
        'delete_printer': request.user.has_perm('inventory.delete_printer'),
        'run_inventory': request.user.has_perm('inventory.run_inventory'),
        'export_printers': request.user.has_perm('inventory.export_printers'),
        'export_amb_report': request.user.has_perm('inventory.export_amb_report'),
        'manage_web_parsing': request.user.has_perm('inventory.manage_web_parsing'),
        'can_poll_all_printers': request.user.has_perm('monthly_report.can_poll_all_printers'),
    }

    # Начальные данные и фильтры из GET параметров
    initial_data = {
        'filters': {
            'q_ip': request.GET.get('q_ip', ''),
            'q_serial': request.GET.get('q_serial', ''),
            'q_manufacturer': request.GET.get('q_manufacturer', ''),
            'q_device_model': request.GET.get('q_device_model', ''),
            'q_model_text': request.GET.get('q_model_text', ''),
            'q_org': request.GET.get('q_org', ''),
            'q_rule': request.GET.get('q_rule', ''),
            'per_page': int(request.GET.get('per_page', 100)),
            'page': int(request.GET.get('page', 1)),
        }
    }

    context = {
        'permissions_json': json.dumps(permissions),
        'initial_data_json': json.dumps(initial_data),
    }

    return render(request, 'inventory/index.html', context)
