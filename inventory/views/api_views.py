# inventory/views/api_views.py
"""
API endpoints for programmatic access to inventory data.
Includes printer data, SNMP probing, system status, and statistics.
ОПТИМИЗИРОВАННАЯ ВЕРСИЯ - убраны N+1 запросы, данные читаются напрямую из БД.
"""

import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, OuterRef, Subquery, Q
from django.utils.timezone import localtime
from django.core.paginator import Paginator

from ..models import Printer, InventoryTask, PageCounter, Organization, PrinterChangeLog
from contracts.models import DeviceModel, Manufacturer
from ..services import (
    run_discovery_for_ip,
    extract_serial_from_xml,
    get_glpi_info,
)

logger = logging.getLogger(__name__)

# Celery availability check
try:
    from ..tasks import run_inventory_task_priority, inventory_daemon_task

    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# PRINTER DATA APIs
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def api_printers(request):
    """
    API списка принтеров с фильтрацией и пагинацией.
    Поддерживает параметры: q_ip, q_serial, q_manufacturer, q_device_model, q_model_text, q_org, q_rule, q_active, per_page, page
    """
    # Получаем параметры фильтрации
    q_ip = request.GET.get('q_ip', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    q_org = request.GET.get('q_org', '').strip()
    q_rule = request.GET.get('q_rule', '').strip()
    q_manufacturer = request.GET.get('q_manufacturer', '').strip()
    q_device_model = request.GET.get('q_device_model', '').strip()
    q_model_text = request.GET.get('q_model_text', '').strip()
    q_active = request.GET.get('q_active', 'true').strip().lower()  # По умолчанию только активные

    # Пагинация
    per_page = request.GET.get('per_page', '100').strip()
    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    # Базовый запрос с оптимизацией
    qs = Printer.objects.select_related(
        'organization',
        'device_model',
        'device_model__manufacturer'
    ).all()

    # Фильтр по активности (по умолчанию только активные)
    if q_active == 'true':
        qs = qs.filter(is_active=True)
    elif q_active == 'false':
        qs = qs.filter(is_active=False)
    # q_active == 'all' - показывать все

    # Применяем фильтры
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)

    if q_device_model:
        qs = qs.filter(device_model_id=q_device_model)
    elif q_manufacturer:
        qs = qs.filter(device_model__manufacturer_id=q_manufacturer)
    elif q_model_text:
        qs = qs.filter(
            Q(model__icontains=q_model_text) |
            Q(device_model__name__icontains=q_model_text) |
            Q(device_model__manufacturer__name__icontains=q_model_text)
        )

    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    if q_org == 'none':
        qs = qs.filter(organization__isnull=True)
    elif q_org:
        try:
            qs = qs.filter(organization_id=int(q_org))
        except ValueError:
            qs = qs.filter(organization__name__icontains=q_org)

    if q_rule in ('SN_MAC', 'MAC_ONLY', 'SN_ONLY'):
        qs = qs.filter(last_match_rule=q_rule)
    elif q_rule == 'NONE':
        qs = qs.filter(last_match_rule__isnull=True)

    qs = qs.order_by('ip_address')

    # Пагинация
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Получаем ID принтеров на текущей странице
    printer_ids = [p.id for p in page_obj]

    # Получаем задачи и счётчики
    tasks_dict = {}
    if printer_ids:
        for printer_id in printer_ids:
            task = (
                InventoryTask.objects
                .filter(printer_id=printer_id, status='SUCCESS')
                .order_by('-task_timestamp')
                .first()
            )
            if task:
                tasks_dict[printer_id] = task

    task_ids = [task.id for task in tasks_dict.values()]
    counters_dict = {}
    if task_ids:
        counters = PageCounter.objects.filter(task_id__in=task_ids).select_related('task')
        counters_dict = {c.task_id: c for c in counters}

    # Формируем данные принтеров
    printers_data = []
    for p in page_obj:
        task = tasks_dict.get(p.id)
        counter = counters_dict.get(task.id) if task else None

        ts_ms = ""
        last_date_str = ""
        if task:
            ts_ms = int(task.task_timestamp.timestamp() * 1000)
            last_date_str = localtime(task.task_timestamp).strftime('%Y-%m-%d %H:%M:%S')

        printers_data.append({
            "id": p.id,
            "ip_address": p.ip_address,
            "serial_number": p.serial_number,
            "mac_address": p.mac_address or None,
            "organization": {"id": p.organization_id, "name": p.organization.name} if p.organization else None,
            "device_model": {
                "id": p.device_model_id,
                "name": p.device_model.name,
                "manufacturer": {
                    "id": p.device_model.manufacturer_id,
                    "name": p.device_model.manufacturer.name
                } if p.device_model.manufacturer else None
            } if p.device_model else None,
            "last_match_rule": p.last_match_rule,
            "last_date": last_date_str,
            "last_date_iso": ts_ms,
            "counters": {
                "bw_a4": counter.bw_a4 if counter else None,
                "color_a4": counter.color_a4 if counter else None,
                "bw_a3": counter.bw_a3 if counter else None,
                "color_a3": counter.color_a3 if counter else None,
                "total": counter.total_pages if counter else None,
                "drum_black": counter.drum_black if counter else None,
                "drum_cyan": counter.drum_cyan if counter else None,
                "drum_magenta": counter.drum_magenta if counter else None,
                "drum_yellow": counter.drum_yellow if counter else None,
                "toner_black": counter.toner_black if counter else None,
                "toner_cyan": counter.toner_cyan if counter else None,
                "toner_magenta": counter.toner_magenta if counter else None,
                "toner_yellow": counter.toner_yellow if counter else None,
                "fuser_kit": counter.fuser_kit if counter else None,
                "transfer_kit": counter.transfer_kit if counter else None,
                "waste_toner": counter.waste_toner if counter else None,
            } if counter else {},
            "is_fresh": False,  # TODO: implement fresh detection
            "is_active": p.is_active,
            "replaced_by_id": p.replaced_by_id,
        })

    # Получаем доп. данные для фильтров
    manufacturers = list(Manufacturer.objects.filter(
        models__device_type='printer'
    ).distinct().order_by('name').values('id', 'name'))

    # ВАЖНО: Всегда возвращаем ВСЕ модели принтеров
    # Клиентская фильтрация по производителю работает в PrinterFilters.vue через computed filteredModels
    device_models = list(DeviceModel.objects.filter(
        device_type='printer'
    ).order_by('name').values('id', 'name', 'manufacturer_id'))

    organizations = list(Organization.objects.filter(
        active=True
    ).order_by('name').values('id', 'name'))

    return JsonResponse({
        "printers": printers_data,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "total_count": paginator.count,
        "start_index": page_obj.start_index() if page_obj else 0,
        "end_index": page_obj.end_index() if page_obj else 0,
        "manufacturers": manufacturers,
        "device_models": device_models,
        "organizations": organizations
    })


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def api_printer(request, pk):
    """
    API детальной информации об одном принтере.
    ОПТИМИЗИРОВАННАЯ ВЕРСИЯ - прямые запросы к БД.
    """
    pk = int(pk)
    printer = get_object_or_404(
        Printer.objects.select_related('organization', 'device_model', 'device_model__manufacturer'),
        pk=pk
    )

    # Получаем последнюю успешную задачу
    task = (
        InventoryTask.objects
        .filter(printer_id=pk, status='SUCCESS')  # Используем printer_id для консистентности
        .order_by('-task_timestamp')
        .first()
    )

    # Получаем счётчики
    counter = None
    if task:
        counter = PageCounter.objects.filter(task=task).first()

    # Вычисляем timestamp
    ts_ms = ""
    if task:
        ts_ms = int(task.task_timestamp.timestamp() * 1000)

    # Получаем название модели и производителя
    model_name = ""
    manufacturer_name = ""
    if printer.device_model:
        model_name = printer.device_model.name
        manufacturer_name = printer.device_model.manufacturer.name if printer.device_model.manufacturer else ""

    data = {
        "id": printer.id,
        "ip_address": printer.ip_address,
        "serial_number": printer.serial_number,
        "mac_address": printer.mac_address or "-",
        "model_name": model_name,
        "manufacturer_name": manufacturer_name,
        "device_model_id": printer.device_model_id,
        "manufacturer_id": printer.device_model.manufacturer_id if printer.device_model else None,
        "snmp_community": printer.snmp_community or "public",
        "organization_id": printer.organization_id,
        "organization": printer.organization.name if printer.organization_id else None,
        "last_match_rule": printer.last_match_rule,
        "last_match_rule_label": printer.get_last_match_rule_display() if printer.last_match_rule else None,

        # Счетчики страниц
        "bw_a4": counter.bw_a4 if counter else "-",
        "color_a4": counter.color_a4 if counter else "-",
        "bw_a3": counter.bw_a3 if counter else "-",
        "color_a3": counter.color_a3 if counter else "-",
        "total_pages": counter.total_pages if counter else "-",

        # Барабаны
        "drum_black": counter.drum_black if counter else "-",
        "drum_cyan": counter.drum_cyan if counter else "-",
        "drum_magenta": counter.drum_magenta if counter else "-",
        "drum_yellow": counter.drum_yellow if counter else "-",

        # Тонеры
        "toner_black": counter.toner_black if counter else "-",
        "toner_cyan": counter.toner_cyan if counter else "-",
        "toner_magenta": counter.toner_magenta if counter else "-",
        "toner_yellow": counter.toner_yellow if counter else "-",

        # Прочие расходники
        "fuser_kit": counter.fuser_kit if counter else "-",
        "transfer_kit": counter.transfer_kit if counter else "-",
        "waste_toner": counter.waste_toner if counter else "-",

        "last_date_iso": ts_ms,
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
# SNMP PROBING API
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def api_probe_serial(request):
    """
    API для получения серийного номера через SNMP discovery.
    Используется в форме добавления принтера.
    """
    payload = json.loads(request.body.decode("utf-8"))
    ip = (payload.get("ip") or "").strip()
    community = (payload.get("community") or "public").strip() or "public"

    if not ip:
        return JsonResponse({"ok": False, "error": "ip не передан"}, status=400)

    ok, xml_or_err = run_discovery_for_ip(ip, community)
    if not ok:
        return JsonResponse({"ok": False, "error": xml_or_err}, status=502)

    serial = extract_serial_from_xml(xml_or_err)
    if not serial:
        return JsonResponse({"ok": False, "error": "Серийник не найден в XML"}, status=404)

    return JsonResponse({"ok": True, "serial": serial})


# ──────────────────────────────────────────────────────────────────────────────
# DEVICE MODEL APIs
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_models_by_manufacturer(request):
    """API для получения моделей принтеров по производителю"""
    manufacturer_id = request.GET.get('manufacturer_id')

    if not manufacturer_id:
        return JsonResponse({'models': []})

    try:
        models = DeviceModel.objects.filter(
            manufacturer_id=manufacturer_id,
            device_type='printer'
        ).select_related('manufacturer').order_by('name').values('id', 'name', 'manufacturer__name')

        return JsonResponse({
            'models': [
                {
                    'id': m['id'],
                    'name': m['name'],
                    'full_name': f"{m['manufacturer__name']} {m['name']}"
                }
                for m in models
            ]
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_all_printer_models(request):
    """API для получения всех моделей принтеров"""
    models = DeviceModel.objects.filter(
        device_type='printer'
    ).select_related('manufacturer').order_by('manufacturer__name', 'name').values(
        'id', 'name', 'manufacturer__name', 'manufacturer__id'
    )

    return JsonResponse({
        'models': [
            {
                'id': m['id'],
                'name': m['name'],
                'manufacturer': m['manufacturer__name'],
                'manufacturer_id': m['manufacturer__id']
            }
            for m in models
        ]
    })


# ──────────────────────────────────────────────────────────────────────────────
# SYSTEM STATUS APIs
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_system_status(request):
    """
    Упрощённый API статуса системы.
    Возвращает базовую информацию о Celery, принтерах и GLPI.
    """
    # Базовая статистика Celery (если доступен)
    celery_status = {"available": CELERY_AVAILABLE}
    if CELERY_AVAILABLE:
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = inspect.stats()

            if stats:
                celery_status.update({
                    "workers_count": len(stats),
                    "broker_url": current_app.conf.broker_url,
                })
        except Exception as e:
            celery_status["error"] = str(e)

    # Простая статистика принтеров из БД
    total_printers = Printer.objects.count()
    recent_cutoff = timezone.now() - timedelta(hours=24)

    recent_success = InventoryTask.objects.filter(
        task_timestamp__gte=recent_cutoff,
        status='SUCCESS'
    ).values('printer').distinct().count()

    printer_stats = {
        "total_printers": total_printers,
        "recent_success": recent_success,
        "success_rate": round(
            (recent_success / total_printers * 100) if total_printers > 0 else 0,
            1
        ),
        "updated_at": timezone.now().isoformat(),
    }

    return JsonResponse({
        "timestamp": timezone.now().isoformat(),
        "celery": celery_status,
        "printers": printer_stats,
        "glpi": get_glpi_info(),
    })


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_status_statistics(request):
    """
    API статистики по статусам задач инвентаризации.
    Позволяет анализировать качество опросов за период.
    """
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)

    # Общая статистика
    total_tasks = InventoryTask.objects.filter(
        task_timestamp__gte=start_date
    ).count()

    # Статистика по статусам
    status_stats = InventoryTask.objects.filter(
        task_timestamp__gte=start_date
    ).values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    # Преобразуем в читаемый формат
    status_data = []
    for stat in status_stats:
        status_display = dict(InventoryTask.STATUS_CHOICES).get(
            stat['status'],
            stat['status']
        )
        percentage = (stat['count'] / total_tasks * 100) if total_tasks > 0 else 0

        status_data.append({
            'status': stat['status'],
            'status_display': status_display,
            'count': stat['count'],
            'percentage': round(percentage, 1)
        })

    # Топ принтеров с проблемами
    problematic_printers = InventoryTask.objects.filter(
        task_timestamp__gte=start_date,
        status__in=['FAILED', 'VALIDATION_ERROR', 'HISTORICAL_INCONSISTENCY']
    ).values(
        'printer__ip_address',
        'printer__device_model__name',
        'status'
    ).annotate(
        error_count=Count('id')
    ).order_by('-error_count')[:10]

    return JsonResponse({
        'period_days': days,
        'total_tasks': total_tasks,
        'status_statistics': status_data,
        'problematic_printers': list(problematic_printers),
        'timestamp': timezone.now().isoformat(),
    })


# ──────────────────────────────────────────────────────────────────────────────
# PRINTER REPLACEMENT HISTORY API
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_printer_replacement_history(request, pk):
    """
    API истории замен оборудования для принтера.
    Возвращает все события замены/смены IP, связанные с принтером.
    """
    try:
        printer = Printer.objects.get(pk=pk)
    except Printer.DoesNotExist:
        return JsonResponse({'error': 'Printer not found'}, status=404)

    # Получаем все изменения, связанные с этим принтером
    # (как основного, так и связанного)
    changes = PrinterChangeLog.objects.filter(
        Q(printer=printer) | Q(related_printer=printer)
    ).select_related('printer', 'related_printer').order_by('-timestamp')[:50]

    result = []
    for change in changes:
        result.append({
            'id': change.id,
            'action': change.action,
            'action_display': change.get_action_display(),
            'timestamp': change.timestamp.isoformat(),
            'old_values': change.old_values,
            'new_values': change.new_values,
            'comment': change.comment,
            'triggered_by': change.triggered_by,
            'triggered_by_display': change.get_triggered_by_display(),
            'printer': {
                'id': change.printer.id,
                'ip_address': change.printer.ip_address,
                'serial_number': change.printer.serial_number,
                'is_active': change.printer.is_active,
            },
            'related_printer': {
                'id': change.related_printer.id,
                'ip_address': change.related_printer.ip_address,
                'serial_number': change.related_printer.serial_number,
                'is_active': change.related_printer.is_active,
            } if change.related_printer else None,
            'is_main_subject': change.printer_id == printer.id,
        })

    return JsonResponse({
        'printer_id': printer.id,
        'printer_ip': printer.ip_address,
        'printer_serial': printer.serial_number,
        'is_active': printer.is_active,
        'replaced_at': printer.replaced_at.isoformat() if printer.replaced_at else None,
        'replaced_by': {
            'id': printer.replaced_by.id,
            'ip_address': printer.replaced_by.ip_address,
            'serial_number': printer.replaced_by.serial_number,
        } if printer.replaced_by else None,
        'changes': result,
    })