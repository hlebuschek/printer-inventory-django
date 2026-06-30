"""
Vue.js версия страницы настройки веб-парсинга
"""

import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from inventory.models import PollingMethod, Printer, WebParsingRule, WebParsingTemplate


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def web_parser_setup_vue(request, printer_id):
    """Vue.js страница настройки веб-парсинга для принтера"""

    printer = get_object_or_404(Printer, pk=printer_id)

    # Получаем существующие правила для этого принтера
    rules = WebParsingRule.objects.filter(printer=printer).order_by("field_name")
    rules_data = [
        {
            "id": rule.id,
            "protocol": rule.protocol,
            "url_path": rule.url_path,
            "field_name": rule.field_name,
            "xpath": rule.xpath,
            "regex": rule.regex_pattern,
            "regex_replacement": rule.regex_replacement,
            "is_calculated": rule.is_calculated,
            "calculation_formula": rule.calculation_formula,
            "selected_rules": rule.source_rules or "",
            "actions": json.loads(rule.actions_chain) if rule.actions_chain else [],
        }
        for rule in rules
    ]

    # Получаем шаблоны
    templates = WebParsingTemplate.objects.all().order_by("name")
    templates_data = [
        {
            "id": template.id,
            "name": template.name,
            "description": template.description or "",
        }
        for template in templates
    ]

    # Методы опроса для dropdown
    polling_methods = [{"value": choice[0], "label": choice[1]} for choice in PollingMethod.choices]

    initial_data = {
        "rules": rules_data,
        "templates": templates_data,
        "printer_polling_method": printer.polling_method,
    }

    context = {
        "printer": printer,
        "rules": rules,
        "rules_data": json.dumps(rules_data),
        "printer_id": printer_id,
        "printer_ip": printer.ip_address,
        "device_model_id": printer.device_model_id if printer.device_model else None,
        "initial_data_json": json.dumps(initial_data),
        "polling_methods_json": json.dumps(polling_methods),
    }

    return render(request, "inventory/web_parser_vue.html", context)


@require_POST
@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def update_polling_method(request, printer_id):
    """API для обновления метода опроса принтера"""
    printer = get_object_or_404(Printer, pk=printer_id)

    new_method = request.POST.get("polling_method")
    if not new_method:
        return JsonResponse({"success": False, "error": "Missing polling_method parameter"}, status=400)

    # Проверяем валидность метода
    valid_methods = [choice[0] for choice in PollingMethod.choices]
    if new_method not in valid_methods:
        return JsonResponse(
            {"success": False, "error": f"Invalid polling_method. Valid options: {valid_methods}"}, status=400
        )

    # Если выбираем HYBRID, проверяем наличие правил веб-парсинга
    if new_method == PollingMethod.HYBRID:
        has_web_rules = WebParsingRule.objects.filter(printer=printer).exists()
        if not has_web_rules:
            return JsonResponse(
                {
                    "success": False,
                    "error": "HYBRID mode requires web parsing rules to be configured first",
                },
                status=400,
            )

    # Обновляем метод опроса
    old_method = printer.polling_method
    printer.polling_method = new_method
    printer.save(update_fields=["polling_method"])

    return JsonResponse(
        {
            "success": True,
            "message": f"Polling method updated from {old_method} to {new_method}",
            "old_method": old_method,
            "new_method": new_method,
        }
    )
