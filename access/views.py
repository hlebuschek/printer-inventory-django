import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import UserThemePreference


@login_required
@require_http_methods(["GET", "POST"])
def theme_preference_api(request):
    """
    API для работы с настройками темы пользователя.

    GET: Получить текущую тему пользователя
    POST: Сохранить тему пользователя
    """
    if request.method == "GET":
        try:
            pref = UserThemePreference.objects.get(user=request.user)
            return JsonResponse({"ok": True, "theme": pref.theme, "updated_at": pref.updated_at.isoformat()})
        except UserThemePreference.DoesNotExist:
            return JsonResponse({"ok": True, "theme": None, "updated_at": None})  # Настройки ещё не сохранены

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            theme = data.get("theme", "light")

            # Валидация
            valid_themes = ["light", "dark", "system"]
            if theme not in valid_themes:
                return JsonResponse(
                    {"ok": False, "error": f"Invalid theme. Must be one of: {', '.join(valid_themes)}"}, status=400
                )

            # Создаём или обновляем настройки
            pref, created = UserThemePreference.objects.update_or_create(user=request.user, defaults={"theme": theme})

            return JsonResponse(
                {"ok": True, "theme": pref.theme, "created": created, "updated_at": pref.updated_at.isoformat()}
            )

        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"ok": False, "error": str(e)}, status=500)


@login_required
def permissions_overview(request):
    u = request.user

    apps = [
        {
            "name": "Опрос устройств",
            "code": "inventory",
            "access": u.has_perm("inventory.access_inventory_app"),
            "can_view": any(
                u.has_perm(f"inventory.view_{m}") for m in ["printer", "organization", "inventorytask", "pagecounter"]
            ),
            "can_edit": any(u.has_perm(f"inventory.change_{m}") for m in ["printer", "organization", "inventorytask"]),
            "can_add": any(u.has_perm(f"inventory.add_{m}") for m in ["printer", "organization", "inventorytask"]),
            "can_delete": any(
                u.has_perm(f"inventory.delete_{m}") for m in ["printer", "organization", "inventorytask"]
            ),
            "special": {
                "Запуск опроса": u.has_perm("inventory.run_inventory"),
                "Опрос всех принтеров": u.has_perm("monthly_report.can_poll_all_printers"),
                "Экспорт в excel": u.has_perm("inventory.export_printers"),
                "Отчет для АМБ": u.has_perm("inventory.export_amb_report"),
                "Управление веб-парсингом": u.has_perm("inventory.manage_web_parsing"),  # 🆕
                "Просмотр веб-парсинга": u.has_perm("inventory.view_web_parsing"),  # 🆕
            },
        },
        {
            "name": "Устройства в договоре",
            "code": "contracts",
            "access": u.has_perm("contracts.access_contracts_app"),
            "can_view": any(
                u.has_perm(f"contracts.view_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_edit": any(
                u.has_perm(f"contracts.change_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_add": any(
                u.has_perm(f"contracts.add_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "can_delete": any(
                u.has_perm(f"contracts.delete_{m}")
                for m in ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]
            ),
            "special": {
                "Экспорт в excel": u.has_perm("contracts.export_contracts"),
            },
        },
        {
            "name": "Дашборд",
            "code": "dashboard",
            "access": u.has_perm("dashboard.access_dashboard_app"),
            "can_view": False,
            "can_edit": False,
            "can_add": False,
            "can_delete": False,
            "special": {
                "Доступ к дашборду": u.has_perm("dashboard.access_dashboard_app"),
            },
        },
        {
            "name": "Ежемесячные отчёты",
            "code": "monthly_report",
            # колонка «Доступ»
            "access": (u.has_module_perms("monthly_report") or u.has_perm("monthly_report.access_monthly_report")),
            # базовые CRUD для строки приложения
            "can_view": any(u.has_perm(f"monthly_report.view_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_add": any(u.has_perm(f"monthly_report.add_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_edit": any(u.has_perm(f"monthly_report.change_{m}") for m in ("monthlyreport", "monthcontrol")),
            "can_delete": any(u.has_perm(f"monthly_report.delete_{m}") for m in ("monthlyreport", "monthcontrol")),
            # спец-права (правая колонка)
            "special": {
                "Доступ к модулю": u.has_perm("monthly_report.access_monthly_report"),
                "Загрузка Excel": u.has_perm("monthly_report.upload_monthly_report"),
                "Редактировать поля *_start": u.has_perm("monthly_report.edit_counters_start"),
                "Редактировать поля *_end": u.has_perm("monthly_report.edit_counters_end"),
                "Синхронизация из Inventory": u.has_perm("monthly_report.sync_from_inventory"),
                "Просмотр истории изменений": u.has_perm("monthly_report.view_change_history"),
                "Управление видимостью месяцев": u.has_perm("monthly_report.can_manage_month_visibility"),
                "Возврат на автоопрос": u.has_perm("monthly_report.can_reset_auto_polling"),
            },
        },
    ]

    return render(request, "access/permissions_overview.html", {"apps": apps})
