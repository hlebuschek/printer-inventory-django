"""
Vue.js версия формы добавления/редактирования принтера
"""
import json
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404
from inventory.models import Printer
from contracts.models import Organization


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.add_printer", raise_exception=True)
def printer_form_vue_add(request):
    """Vue.js форма добавления принтера"""

    # Получаем список активных организаций
    organizations = Organization.objects.filter(active=True).order_by("name")
    organizations_data = [
        {"id": org.id, "name": org.name}
        for org in organizations
    ]

    initial_data = {
        "organizations": organizations_data
    }

    context = {
        "printer_id": None,
        "initial_data_json": json.dumps(initial_data),
    }

    return render(request, "inventory/printer_form_vue.html", context)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.change_printer", raise_exception=True)
def printer_form_vue_edit(request, pk):
    """Vue.js форма редактирования принтера"""

    # Проверяем что принтер существует
    printer = get_object_or_404(Printer, pk=pk)

    # Получаем список активных организаций
    organizations = Organization.objects.filter(active=True).order_by("name")
    organizations_data = [
        {"id": org.id, "name": org.name}
        for org in organizations
    ]

    initial_data = {
        "organizations": organizations_data
    }

    context = {
        "printer_id": pk,
        "initial_data_json": json.dumps(initial_data),
    }

    return render(request, "inventory/printer_form_vue.html", context)
