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

from ..models import Printer, InventoryTask, PageCounter, Organization
from ..forms import PrinterForm
from ..services import run_inventory_for_printer, inventory_daemon

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
                run_inventory_for_printer(pk)
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
# LIST VIEW
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def printer_list(request):
    """
    Список принтеров с фильтрацией и пагинацией.
    Оптимизирован для работы с большим количеством записей.
    """
    # Получаем параметры фильтрации
    q_ip = request.GET.get('q_ip', '').strip()
    q_model = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    q_org = request.GET.get('q_org', '').strip()
    q_rule = request.GET.get('q_rule', '').strip()
    per_page = request.GET.get('per_page', '100').strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    # Базовый запрос с оптимизацией - включаем device_model
    qs = Printer.objects.select_related(
        'organization',
        'device_model',
        'device_model__manufacturer'
    ).all()

    # Применяем фильтры
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)

    if q_model:
        # Ищем и в старом текстовом поле, и в новом справочнике
        qs = qs.filter(
            Q(model__icontains=q_model) |
            Q(device_model__name__icontains=q_model) |
            Q(device_model__manufacturer__name__icontains=q_model)
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
    page_obj = paginator.get_page(request.GET.get('page'))

    # Получаем ID всех принтеров на текущей странице
    printer_ids = [p.id for p in page_obj]

    # Получаем последние SUCCESS задачи для каждого принтера
    tasks_dict = {}
    if printer_ids:
        # Для каждого принтера находим последнюю успешную задачу
        for printer_id in printer_ids:
            task = (
                InventoryTask.objects
                .filter(printer_id=printer_id, status='SUCCESS')
                .order_by('-task_timestamp')
                .first()
            )
            if task:
                tasks_dict[printer_id] = task

    # Получаем все счётчики одним запросом
    task_ids = [task.id for task in tasks_dict.values()]
    counters_dict = {}
    if task_ids:
        counters = PageCounter.objects.filter(task_id__in=task_ids).select_related('task')
        counters_dict = {c.task_id: c for c in counters}

    # Формируем данные для шаблона
    data = []
    for p in page_obj:
        task = tasks_dict.get(p.id)
        counter = counters_dict.get(task.id) if task else None

        if task:
            last_date_iso = int(task.task_timestamp.timestamp() * 1000)
            last_date = localtime(task.task_timestamp).strftime('%d.%m.%Y %H:%M')
        else:
            last_date_iso = ''
            last_date = '—'

        data.append({
            'printer': p,
            'bw_a4': getattr(counter, 'bw_a4', None),
            'color_a4': getattr(counter, 'color_a4', None),
            'bw_a3': getattr(counter, 'bw_a3', None),
            'color_a3': getattr(counter, 'color_a3', None),
            'total': getattr(counter, 'total_pages', None),
            'drum_black': getattr(counter, 'drum_black', ''),
            'drum_cyan': getattr(counter, 'drum_cyan', ''),
            'drum_magenta': getattr(counter, 'drum_magenta', ''),
            'drum_yellow': getattr(counter, 'drum_yellow', ''),
            'toner_black': getattr(counter, 'toner_black', ''),
            'toner_cyan': getattr(counter, 'toner_cyan', ''),
            'toner_magenta': getattr(counter, 'toner_magenta', ''),
            'toner_yellow': getattr(counter, 'toner_yellow', ''),
            'fuser_kit': getattr(counter, 'fuser_kit', ''),
            'transfer_kit': getattr(counter, 'transfer_kit', ''),
            'waste_toner': getattr(counter, 'waste_toner', ''),
            'last_date': last_date,
            'last_date_iso': last_date_iso,
        })
    per_page_options = [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]

    return render(request, 'inventory/index.html', {
        'data': data,
        'page_obj': page_obj,
        'q_ip': q_ip,
        'q_model': q_model,
        'q_serial': q_serial,
        'q_org': q_org,
        'q_rule': q_rule,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'organizations': Organization.objects.filter(active=True).order_by('name'),
    })


# ──────────────────────────────────────────────────────────────────────────────
# CRUD OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.add_printer", raise_exception=True)
def add_printer(request):
    """Добавление нового принтера."""
    form = PrinterForm(request.POST or None)
    if form.is_valid():
        printer = form.save()
        messages.success(request, f"Принтер {printer.ip_address} добавлен")
        return redirect("inventory:printer_list")
    return render(request, "inventory/add_printer.html", {"form": form})


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
                    "model": printer.model_display,  # Используем свойство model_display
                    "snmp_community": printer.snmp_community,
                    "organization": printer.organization.name if printer.organization_id else None,
                    "organization_id": printer.organization_id,
                },
            })

        messages.success(request, f"Принтер {printer.ip_address} обновлён")
        return redirect("inventory:printer_list")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": form.errors.as_json()}, status=400)

    return render(request, "inventory/edit_printer.html", {"form": form})


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

    # GET запрос - показываем список
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
        # AJAX запрос - возвращаем JSON для графика
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

            # Для исторических несоответствий показываем предыдущие данные
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

    # HTML версия - постранично
    tasks = InventoryTask.objects.filter(
        printer=printer,
        status="SUCCESS"
    ).order_by("-task_timestamp")

    paginator = Paginator(tasks, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [(t, PageCounter.objects.filter(task=t).first()) for t in page_obj]

    return render(
        request,
        "inventory/history.html",
        {"printer": printer, "rows": rows, "page_obj": page_obj}
    )


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
            task = run_inventory_task_priority.apply_async(
                args=[pk, request.user.id],
                priority=9,
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
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def run_inventory_all(request):
    """Запуск инвентаризации всех принтеров."""

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