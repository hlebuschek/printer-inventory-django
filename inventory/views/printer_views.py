# inventory/views/printer_views.py
"""
CRUD views for printer management.
Handles listing, adding, editing, deleting printers and running inventory scans.
"""

import json
import logging
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from django.conf import settings

from ..models import Printer, InventoryTask, PageCounter, Organization, WebParsingRule
from ..forms import PrinterForm
from ..services import run_inventory_for_printer, inventory_daemon
from ..web_parser import execute_web_parsing, export_to_xml

logger = logging.getLogger(__name__)

# Проверка доступности Celery
try:
    from ..tasks import run_inventory_task_priority, inventory_daemon_task
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False

# Fallback executor если нет Celery
if not CELERY_AVAILABLE:
    EXECUTOR = ThreadPoolExecutor(max_workers=5)
    _RUNNING = set()
    _RUNNING_LOCK = threading.Lock()

    def _queue_inventory(pk: int) -> bool:
        with _RUNNING_LOCK:
            if pk in _RUNNING:
                return False
            _RUNNING.add(pk)

        def _job():
            try:
                run_inventory_for_printer(pk, triggered_by='manual')
            except Exception as e:
                logger.error(f"Error in inventory job for printer {pk}: {e}")
            finally:
                with _RUNNING_LOCK:
                    _RUNNING.discard(pk)

        EXECUTOR.submit(_job)
        return True
else:
    def _queue_inventory(pk: int) -> bool:
        return True


# ──────────────────────────────────────────────────────────────────────────────
# CRUD OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.add_printer", raise_exception=True)
def add_printer(request):
    """Добавление нового принтера."""
    form = PrinterForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        printer = form.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "printer": {
                    "id": printer.id,
                    "ip_address": printer.ip_address,
                    "serial_number": printer.serial_number,
                    "mac_address": printer.mac_address,
                    "model": printer.model_display,
                    "snmp_community": printer.snmp_community,
                    "organization": printer.organization.name if printer.organization_id else None,
                    "organization_id": printer.organization_id,
                },
            })

        messages.success(request, f"Принтер {printer.ip_address} добавлен")
        return redirect("inventory:printer_list")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": form.errors.as_json()}, status=400)

    return render(request, "inventory/printer_form_vue.html", {"form": form})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.change_printer", raise_exception=True)
def edit_printer(request, pk):
    """Редактирование принтера."""
    printer = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST or None, instance=printer)

    if request.method == "POST" and form.is_valid():
        printer = form.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": True,
                "printer": {
                    "id": printer.id,
                    "ip_address": printer.ip_address,
                    "serial_number": printer.serial_number,
                    "mac_address": printer.mac_address,
                    "model": printer.model_display,
                    "snmp_community": printer.snmp_community,
                    "organization": printer.organization.name if printer.organization_id else None,
                    "organization_id": printer.organization_id,
                },
            })

        messages.success(request, f"Принтер {printer.ip_address} обновлён")
        return redirect("inventory:printer_list")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": form.errors.as_json()}, status=400)

    return render(request, "inventory/printer_form_vue.html", {"form": form})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.delete_printer", raise_exception=True)
def delete_printer(request, pk):
    """Удаление принтера."""
    printer = get_object_or_404(Printer, pk=pk)

    if request.method == "POST":
        ip = printer.ip_address
        printer.delete()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        messages.success(request, f"Принтер {ip} удалён")
        return redirect("inventory:printer_list")

    return printer_list(request)


# ──────────────────────────────────────────────────────────────────────────────
# HISTORY VIEW
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def history_view(request, pk):
    """История опросов принтера."""
    printer = get_object_or_404(Printer, pk=pk)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        daily_tasks = (
            InventoryTask.objects.filter(
                printer=printer,
                status__in=['SUCCESS', 'HISTORICAL_INCONSISTENCY']
            )
            .annotate(day=TruncDate("task_timestamp"))
            .order_by("-day", "-task_timestamp", "-pk")
            .distinct("day")
        )

        daily_list = list(daily_tasks)
        counters = PageCounter.objects.filter(task__in=daily_list)
        counter_by_task_id = {c.task_id: c for c in counters}

        data = []
        for t in daily_list:
            c = counter_by_task_id.get(t.id)

            if t.status == 'HISTORICAL_INCONSISTENCY':
                last_valid_task = InventoryTask.objects.filter(
                    printer=printer,
                    status='SUCCESS',
                    task_timestamp__lt=t.task_timestamp
                ).order_by('-task_timestamp').first()

                if last_valid_task:
                    c = PageCounter.objects.filter(task=last_valid_task).first()

            data.append({
                "task_timestamp": localtime(t.task_timestamp).strftime("%Y-%m-%dT%H:%M:%S"),
                "match_rule": t.match_rule,
                "status": t.status,
                "status_display": t.get_status_display(),
                "bw_a4": c.bw_a4 if c else None,
                "color_a4": c.color_a4 if c else None,
                "bw_a3": c.bw_a3 if c else None,
                "color_a3": c.color_a3 if c else None,
                "total_pages": c.total_pages if c else None,
                "drum_black": c.drum_black if c else None,
                "drum_cyan": c.drum_cyan if c else None,
                "drum_magenta": c.drum_magenta if c else None,
                "drum_yellow": c.drum_yellow if c else None,
                "toner_black": c.toner_black if c else None,
                "toner_cyan": c.toner_cyan if c else None,
                "toner_magenta": c.toner_magenta if c else None,
                "toner_yellow": c.toner_yellow if c else None,
                "fuser_kit": c.fuser_kit if c else None,
                "transfer_kit": c.transfer_kit if c else None,
                "waste_toner": c.waste_toner if c else None,
                "is_historical_issue": t.status == 'HISTORICAL_INCONSISTENCY',
                "error_message": t.error_message if t.status == 'HISTORICAL_INCONSISTENCY' else None,
            })

        return JsonResponse(data, safe=False)

    # Если не AJAX запрос - возвращаем ошибку, так как история доступна только через API
    return JsonResponse({"error": "History is only available via AJAX"}, status=400)


# ──────────────────────────────────────────────────────────────────────────────
# INVENTORY RUNNERS
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def run_inventory(request, pk):
    """Запуск инвентаризации одного принтера."""
    pk = int(pk)

    if CELERY_AVAILABLE:
        try:
            # Приоритет уже установлен в декораторе задачи, можно не дублировать
            task = run_inventory_task_priority.apply_async(
                args=[pk, request.user.id],
            )
            logger.info(f"Queued PRIORITY Celery task {task.id} for printer {pk}")
            return JsonResponse({
                "success": True,
                "celery": True,
                "task_id": task.id,
                "queued": True
            })
        except Exception as e:
            logger.error(f"Error queuing Celery task for printer {pk}: {e}")
            return JsonResponse({
                "success": False,
                "celery": True,
                "error": str(e)
            }, status=500)
    else:
        queued = _queue_inventory(pk)
        return JsonResponse({
            "success": True,
            "celery": False,
            "queued": queued
        })


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("monthly_report.can_poll_all_printers", raise_exception=True)
@require_POST
def run_inventory_all(request):
    """
    Запуск инвентаризации всех принтеров.
    Требуется право monthly_report.can_poll_all_printers
    """

    if CELERY_AVAILABLE:
        try:
            task = inventory_daemon_task.apply_async(priority=5)
            logger.info(f"User {request.user.id} queued daemon task {task.id}")
            return JsonResponse({
                "success": True,
                "celery": True,
                "task_id": task.id,
                "queued": True
            })
        except Exception as e:
            logger.error(f"Error queuing daemon task: {e}")
            return JsonResponse({
                "success": False,
                "celery": True,
                "error": str(e)
            }, status=500)
    else:
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(inventory_daemon)
        return JsonResponse({
            "success": True,
            "celery": False,
            "queued": True
        })


# ──────────────────────────────────────────────────────────────────────────────
# WEB PARSER - POLL PRINTER
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.change_printer", raise_exception=True)
@require_POST
def poll_printer(request, printer_id):
    """Опрос принтера по веб-интерфейсу с сохранением XML"""

    printer = get_object_or_404(Printer, pk=printer_id)
    rules = WebParsingRule.objects.filter(printer=printer)

    if not rules.exists():
        return JsonResponse({
            'success': False,
            'error': 'Нет настроенных правил парсинга для этого принтера'
        }, status=400)

    # Выполняем парсинг
    success, results, error_message = execute_web_parsing(printer, list(rules))

    if not success:
        return JsonResponse({
            'success': False,
            'error': error_message
        }, status=400)

    # Обновляем данные принтера
    for field_name, value in results.items():
        if hasattr(printer, field_name):
            setattr(printer, field_name, value)

    printer.save()

    # Экспортируем в XML
    try:
        from ..web_parser import export_to_xml
        xml_content = export_to_xml(printer, results)

        # Создаем папку если не существует
        xml_export_dir = os.path.join(settings.MEDIA_ROOT, 'xml_exports')
        os.makedirs(xml_export_dir, exist_ok=True)

        # Сохраняем только последний файл (без даты в имени)
        xml_filename = f"{printer.serial_number}.xml"
        xml_filepath = os.path.join(xml_export_dir, xml_filename)

        with open(xml_filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        logger.info(f"✓ XML exported: {xml_filename}")

    except Exception as e:
        logger.error(f"Error exporting XML: {e}")

    return JsonResponse({
        'success': True,
        'results': results,
        'xml_exported': True
    })