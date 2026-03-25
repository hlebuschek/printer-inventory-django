"""
Vue.js views для приложения contracts
"""

import json

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.view_contractdevice", raise_exception=True)
def contract_device_list_vue(request):
    """Vue.js страница списка устройств по договорам"""

    # Подготавливаем permissions для фронтенда
    permissions = {
        # Права на contracts
        "view_contractdevice": request.user.has_perm("contracts.view_contractdevice"),
        "add_contractdevice": request.user.has_perm("contracts.add_contractdevice"),
        "change_contractdevice": request.user.has_perm("contracts.change_contractdevice"),
        "delete_contractdevice": request.user.has_perm("contracts.delete_contractdevice"),
        "export_contracts": request.user.has_perm("contracts.export_contracts"),
        # Права на inventory (для модального окна редактирования принтера)
        "view_printer": request.user.has_perm("inventory.view_printer"),
        "add_printer": request.user.has_perm("inventory.add_printer"),
        "change_printer": request.user.has_perm("inventory.change_printer"),
        "delete_printer": request.user.has_perm("inventory.delete_printer"),
        "run_inventory": request.user.has_perm("inventory.run_inventory"),
        "view_entity_changes": request.user.has_perm("access.view_entity_changes"),
        # Права на Okdesk
        "view_okdesk_issues": request.user.has_perm("integrations.view_okdesk_issues"),
        "create_okdesk_issue": request.user.has_perm("integrations.create_okdesk_issue"),
        "manage_okdesk_token": request.user.has_perm("integrations.manage_okdesk_token"),
    }

    context = {
        "permissions_json": json.dumps(permissions),
    }

    return render(request, "contracts/contractdevice_list_vue.html", context)
