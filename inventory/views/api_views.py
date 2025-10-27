# inventory/views/api_views.py
"""
API endpoints for programmatic access to inventory data.
Includes printer data, SNMP probing, system status, and statistics.
"""

import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count

from ..models import Printer, InventoryTask, PageCounter
from contracts.models import DeviceModel
from ..services import (
    run_discovery_for_ip,
    extract_serial_from_xml,
    get_printer_inventory_status,
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
    API списка всех принтеров с последними данными инвентаризации.
    БЕЗ кэширования - данные читаются напрямую из БД.
    """
    output = []
    for p in Printer.objects.select_related("organization", "device_model", "device_model__manufacturer").all():
        inv_status = get_printer_inventory_status(p.id)
        counters = inv_status.get("counters", {})

        ts_ms = ""
        if inv_status.get("timestamp"):
            try:
                dt = timezone.datetime.fromisoformat(
                    inv_status["timestamp"].replace("Z", "+00:00")
                )
                ts_ms = int(dt.timestamp() * 1000)
            except Exception:
                pass

        output.append({
            "id": p.id,
            "ip_address": p.ip_address,
            "serial_number": p.serial_number,
            "mac_address": p.mac_address or "-",
            "model": p.model_display,
            "model_text": p.model,
            "device_model_id": p.device_model_id,
            "device_model_name": str(p.device_model) if p.device_model else None,
            "snmp_community": p.snmp_community or "public",
            "organization_id": p.organization_id,
            "organization": p.organization.name if p.organization_id else None,
            "last_match_rule": p.last_match_rule,
            "last_match_rule_label": p.get_last_match_rule_display() if p.last_match_rule else None,
            "bw_a4": counters.get("bw_a4", "-"),
            "color_a4": counters.get("color_a4", "-"),
            "bw_a3": counters.get("bw_a3", "-"),
            "color_a3": counters.get("color_a3", "-"),
            "total_pages": counters.get("total_pages", "-"),
            "drum_black": counters.get("drum_black", "-"),
            "drum_cyan": counters.get("drum_cyan", "-"),
            "drum_magenta": counters.get("drum_magenta", "-"),
            "drum_yellow": counters.get("drum_yellow", "-"),
            "toner_black": counters.get("toner_black", "-"),
            "toner_cyan": counters.get("toner_cyan", "-"),
            "toner_magenta": counters.get("toner_magenta", "-"),
            "toner_yellow": counters.get("toner_yellow", "-"),
            "fuser_kit": counters.get("fuser_kit", "-"),
            "transfer_kit": counters.get("transfer_kit", "-"),
            "waste_toner": counters.get("waste_toner", "-"),
            "last_date_iso": ts_ms,
        })

    return JsonResponse(output, safe=False)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def api_printer(request, pk):
    """
    API детальной информации об одном принтере.
    БЕЗ кэширования - данные читаются напрямую из БД.
    """
    pk = int(pk)
    printer = get_object_or_404(
        Printer.objects.select_related('organization', 'device_model', 'device_model__manufacturer'),
        pk=pk
    )

    inv_status = get_printer_inventory_status(pk)
    counters = inv_status.get("counters", {})

    ts_ms = ""
    if inv_status.get("timestamp"):
        try:
            dt = timezone.datetime.fromisoformat(
                inv_status["timestamp"].replace("Z", "+00:00")
            )
            ts_ms = int(dt.timestamp() * 1000)
        except Exception:
            pass

    data = {
        "id": printer.id,
        "ip_address": printer.ip_address,
        "serial_number": printer.serial_number,
        "mac_address": printer.mac_address or "-",
        "model": printer.model_display,
        "model_text": printer.model,
        "device_model_id": printer.device_model_id,
        "device_model_name": str(printer.device_model) if printer.device_model else None,
        "snmp_community": printer.snmp_community or "public",
        "organization_id": printer.organization_id,
        "organization": printer.organization.name if printer.organization_id else None,
        "last_match_rule": printer.last_match_rule,
        "last_match_rule_label": printer.get_last_match_rule_display() if printer.last_match_rule else None,
        "bw_a4": counters.get("bw_a4", "-"),
        "color_a4": counters.get("color_a4", "-"),
        "bw_a3": counters.get("bw_a3", "-"),
        "color_a3": counters.get("color_a3", "-"),
        "total_pages": counters.get("total_pages", "-"),
        "drum_black": counters.get("drum_black", "-"),
        "drum_cyan": counters.get("drum_cyan", "-"),
        "drum_magenta": counters.get("drum_magenta", "-"),
        "drum_yellow": counters.get("drum_yellow", "-"),
        "toner_black": counters.get("toner_black", "-"),
        "toner_cyan": counters.get("toner_cyan", "-"),
        "toner_magenta": counters.get("toner_magenta", "-"),
        "toner_yellow": counters.get("toner_yellow", "-"),
        "fuser_kit": counters.get("fuser_kit", "-"),
        "transfer_kit": counters.get("transfer_kit", "-"),
        "waste_toner": counters.get("waste_toner", "-"),
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
        'printer__model',
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