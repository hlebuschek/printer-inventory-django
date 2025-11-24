"""
Тестовое представление для проверки Vue.js интеграции
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def vue_test_view(request):
    """Тестовая страница для проверки Vue.js"""

    # Собираем permissions для передачи в Vue
    permissions = {
        'add_printer': request.user.has_perm('inventory.add_printer'),
        'change_printer': request.user.has_perm('inventory.change_printer'),
        'delete_printer': request.user.has_perm('inventory.delete_printer'),
        'run_inventory': request.user.has_perm('inventory.run_inventory'),
        'export_printers': request.user.has_perm('inventory.export_printers'),
        'manage_web_parsing': request.user.has_perm('inventory.manage_web_parsing'),
    }

    context = {
        'permissions_json': json.dumps(permissions),
    }

    return render(request, 'vue_test.html', context)
