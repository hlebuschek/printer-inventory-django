from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def permissions_overview(request):
    u = request.user
    ctx = {
        "apps": [
            {
                "name": "Inventory",
                "code": "inventory",
                "access": u.has_perm("inventory.access_inventory_app"),
                "can_view": any(u.has_perm(f"inventory.view_{m}") for m in ["printer", "organization", "inventorytask", "pagecounter"]),
                "can_edit": any(u.has_perm(f"inventory.change_{m}") for m in ["printer", "organization", "inventorytask"]),
                "can_add": any(u.has_perm(f"inventory.add_{m}") for m in ["printer", "organization", "inventorytask"]),
                "can_delete": any(u.has_perm(f"inventory.delete_{m}") for m in ["printer", "organization", "inventorytask"]),
                "special": {
                    "run_inventory": u.has_perm("inventory.run_inventory"),
                    "export_printers": u.has_perm("inventory.export_printers"),
                    "export_amb_report": u.has_perm("inventory.export_amb_report"),
                },
            },
            {
                "name": "Contracts",
                "code": "contracts",
                "access": u.has_perm("contracts.access_contracts_app"),
                "can_view": any(u.has_perm(f"contracts.view_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
                "can_edit": any(u.has_perm(f"contracts.change_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
                "can_add": any(u.has_perm(f"contracts.add_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
                "can_delete": any(u.has_perm(f"contracts.delete_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
                "special": {
                    "export_contracts": u.has_perm("contracts.export_contracts"),
                },
            },
        ]
    }
    return render(request, "access/permissions_overview.html", ctx)