from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def permissions_overview(request):
    u = request.user

    apps = [
        {
            "name": "Опрос устройств",
            "code": "inventory",
            "access": u.has_perm("inventory.access_inventory_app"),
            "can_view": any(u.has_perm(f"inventory.view_{m}") for m in ["printer", "organization", "inventorytask", "pagecounter"]),
            "can_edit": any(u.has_perm(f"inventory.change_{m}") for m in ["printer", "organization", "inventorytask"]),
            "can_add":  any(u.has_perm(f"inventory.add_{m}")    for m in ["printer", "organization", "inventorytask"]),
            "can_delete": any(u.has_perm(f"inventory.delete_{m}") for m in ["printer", "organization", "inventorytask"]),
            "special": {
                "Запуск опроса":     u.has_perm("inventory.run_inventory"),
                "Экспорт в excel":   u.has_perm("inventory.export_printers"),
                "Отчет для АМБ": u.has_perm("inventory.export_amb_report"),
            },
        },
        {
            "name": "Устройства в договоре",
            "code": "contracts",
            "access": u.has_perm("contracts.access_contracts_app"),
            "can_view": any(u.has_perm(f"contracts.view_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
            "can_edit": any(u.has_perm(f"contracts.change_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
            "can_add":  any(u.has_perm(f"contracts.add_{m}")    for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
            "can_delete": any(u.has_perm(f"contracts.delete_{m}") for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]),
            "special": {
                "Экспорт в excel": u.has_perm("contracts.export_contracts"),
            },
        },
        {
            "name": "Ежемесячные отчёты",
            "code": "monthly_report",
            # колонка «Доступ»
            "access": (
                u.has_module_perms("monthly_report")
                or u.has_perm("monthly_report.access_monthly_report")
            ),
            # базовые CRUD для строки приложения
            "can_view": any(u.has_perm(f"monthly_report.view_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_add":  any(u.has_perm(f"monthly_report.add_{m}")  for m in ("monthlyreport", "monthcontrol")),
            "can_edit": any(u.has_perm(f"monthly_report.change_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_delete": any(u.has_perm(f"monthly_report.delete_{m}") for m in ("monthlyreport", "monthcontrol")),
            # спец-права (правая колонка)
            "special": {
                "Доступ к модулю":            u.has_perm("monthly_report.access_monthly_report"),
                "Загрузка Excel":             u.has_perm("monthly_report.upload_monthly_report"),
                "Редактировать поля *_start": u.has_perm("monthly_report.edit_counters_start"),
                "Редактировать поля *_end":   u.has_perm("monthly_report.edit_counters_end"),
                "Синхронизация из Inventory": u.has_perm("monthly_report.sync_from_inventory"),
                "Просмотр истории изменений": u.has_perm("monthly_report.view_change_history"),  # ← фикс
            },
        },
    ]

    return render(request, "access/permissions_overview.html", {"apps": apps})
