"""
Vue.js версия страницы настройки веб-парсинга
"""
import json
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404
from inventory.models import Printer, WebParsingRule, WebParsingTemplate


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def web_parser_setup_vue(request, printer_id):
    """Vue.js страница настройки веб-парсинга для принтера"""

    printer = get_object_or_404(Printer, pk=printer_id)

    # Получаем существующие правила для этого принтера
    rules = WebParsingRule.objects.filter(printer=printer).order_by('field_name')
    rules_data = [
        {
            'id': rule.id,
            'protocol': rule.protocol,
            'url_path': rule.url_path,
            'field_name': rule.field_name,
            'xpath': rule.xpath,
            'regex': rule.regex_pattern,
            'regex_replacement': rule.regex_replacement,
            'is_calculated': rule.is_calculated,
            'calculation_formula': rule.calculation_formula,
            'selected_rules': rule.source_rules or '',
            'actions': json.loads(rule.actions_chain) if rule.actions_chain else []
        }
        for rule in rules
    ]

    # Получаем шаблоны
    templates = WebParsingTemplate.objects.all().order_by('name')
    templates_data = [
        {
            'id': template.id,
            'name': template.name,
            'description': template.description or '',
        }
        for template in templates
    ]

    initial_data = {
        'rules': rules_data,
        'templates': templates_data,
    }

    context = {
        'printer': printer,
        'rules': rules,
        'rules_data': json.dumps(rules_data),
        'printer_id': printer_id,
        'printer_ip': printer.ip_address,
        'device_model_id': printer.device_model_id if printer.device_model else None,
        'initial_data_json': json.dumps(initial_data),
    }

    return render(request, "inventory/web_parser_vue.html", context)
