"""
Vue.js версия страницы экспорта AMB
"""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from .export_views import export_amb as export_amb_old


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.export_amb_report", raise_exception=True)
def amb_export_vue(request):
    """
    Vue.js страница выбора шаблона для экспорта AMB.
    GET - показываем Vue.js форму
    POST - обрабатываем через старый view
    """
    if request.method == "POST":
        # Делегируем POST запросы старому view
        return export_amb_old(request)

    # GET - показываем Vue.js страницу
    context = {}
    return render(request, "inventory/amb_export_vue.html", context)
