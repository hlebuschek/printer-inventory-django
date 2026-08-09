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
        "import_contracts": request.user.has_perm("contracts.import_contracts"),
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


@login_required
@permission_required("contracts.access_contracts_app", raise_exception=True)
@permission_required("contracts.import_contracts", raise_exception=True)
def contract_import_vue(request):
    """Vue.js страница массового импорта устройств из Excel"""
    from .models import ContractStatus, ImportSession, ServiceProvider

    initial_data = {
        "statuses": [
            {"id": s.id, "name": s.name, "color": s.color}
            for s in ContractStatus.objects.filter(is_active=True).order_by("name")
        ],
        "providers": [
            {"id": p.id, "name": p.name, "issue_tracker": p.get_issue_tracker_display()}
            for p in ServiceProvider.objects.filter(is_active=True).order_by("name")
        ],
        "recent_sessions": [
            {
                "id": s.id,
                "name": s.name or f"Импорт от {s.created_at:%d.%m.%Y %H:%M}",
                "state": s.state,
                "stats": s.stats,
            }
            for s in ImportSession.objects.select_related("target_status")[:10]
        ],
    }

    permissions = {
        "import_contracts": True,
        # Автозаведение в опрос создаёт Printer, а право на импорт его не даёт
        "add_printer": request.user.has_perm("inventory.add_printer"),
    }

    context = {
        "permissions_json": json.dumps(permissions),
        "initial_data_json": json.dumps(initial_data),
    }

    return render(request, "contracts/contract_import_vue.html", context)
