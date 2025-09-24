# inventory/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDate
from django.core.cache import cache, caches
from django.utils import timezone
from django.conf import settings

import openpyxl
from openpyxl.utils import get_column_letter

from .models import Printer, InventoryTask, PageCounter, Organization
from .forms import PrinterForm
from .services import (
    run_discovery_for_ip,
    extract_serial_from_xml,
    get_cached_printer_data,
    cache_printer_data,
    invalidate_printer_cache,
    get_printer_inventory_status,
    get_cached_printer_statistics,
    get_redis_health_status,
    # fallback цели из services для случая без Celery
    run_inventory_for_printer,
    inventory_daemon,
)

# Попытка подтянуть Celery задачи
try:
    from .tasks import run_inventory_task, inventory_daemon_task
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False

import json
import logging

logger = logging.getLogger(__name__)

# inventory-кэш алиас (если нет — используем default)
inventory_cache = caches["inventory"] if hasattr(settings, "CACHES") and "inventory" in settings.CACHES else cache


# ──────────────────────────────────────────────────────────────────────────────
# Fallback пул фоновых задач + предохранитель от дублей (если нет Celery)
# ──────────────────────────────────────────────────────────────────────────────
if not CELERY_AVAILABLE:
    from concurrent.futures import ThreadPoolExecutor
    import threading

    EXECUTOR = ThreadPoolExecutor(max_workers=5)
    _RUNNING: set[int] = set()
    _RUNNING_LOCK = threading.Lock()

    def _queue_inventory(pk: int) -> bool:
        """Запускает инвентаризацию в пуле, если ещё не идёт для этого принтера."""
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
    # Заглушка, чтобы не падала ссылка ниже
    def _queue_inventory(pk: int) -> bool:
        return True


# ──────────────────────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────────────────────
from datetime import timedelta
from django.utils import timezone

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def printer_list(request):
    # Кэш всей страницы (контекста) на 5 минут, если не запрошен refresh
    cache_key = f"printer_list_params_{request.user.id}_{hash(request.GET.urlencode())}"
    cached_data = cache.get(cache_key)
    if cached_data and not request.GET.get("refresh"):
        return render(request, "inventory/index.html", cached_data)

    q_ip = request.GET.get("q_ip", "").strip()
    q_model = request.GET.get("q_model", "").strip()
    q_serial = request.GET.get("q_serial", "").strip()
    q_org = request.GET.get("q_org", "").strip()
    q_rule = request.GET.get("q_rule", "").strip()
    per_page = request.GET.get("per_page", "100").strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    qs = Printer.objects.select_related("organization").all()

    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    if q_org == "none":
        qs = qs.filter(organization__isnull=True)
    elif q_org:
        try:
            qs = qs.filter(organization_id=int(q_org))
        except ValueError:
            qs = qs.filter(organization__name__icontains=q_org)

    if q_rule in ("SN_MAC", "MAC_ONLY", "SN_ONLY"):
        qs = qs.filter(last_match_rule=q_rule)
    elif q_rule == "NONE":
        qs = qs.filter(last_match_rule__isnull=True)

    qs = qs.order_by("ip_address")
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    data = []
    for p in page_obj:
        # Пробуем кэш карточки принтера
        if not get_cached_printer_data(p.id):
            cache_printer_data(p)

        inv_status = get_printer_inventory_status(p.id)
        counters = inv_status.get("counters", {})
        is_fresh = inv_status.get("is_fresh", False)  # НОВОЕ: флаг свежести данных

        last_date_iso = ""
        last_date = "—"
        if inv_status.get("timestamp"):
            try:
                dt = timezone.datetime.fromisoformat(inv_status["timestamp"].replace("Z", "+00:00"))
                last_date_iso = int(dt.timestamp() * 1000)
                last_date = localtime(dt).strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass

        data.append(
            {
                "printer": p,
                "bw_a4": counters.get("bw_a4"),
                "color_a4": counters.get("color_a4"),
                "bw_a3": counters.get("bw_a3"),
                "color_a3": counters.get("color_a3"),
                "total": counters.get("total_pages"),
                "drum_black": counters.get("drum_black", ""),
                "drum_cyan": counters.get("drum_cyan", ""),
                "drum_magenta": counters.get("drum_magenta", ""),
                "drum_yellow": counters.get("drum_yellow", ""),
                "toner_black": counters.get("toner_black", ""),
                "toner_cyan": counters.get("toner_cyan", ""),
                "toner_magenta": counters.get("toner_magenta", ""),
                "toner_yellow": counters.get("toner_yellow", ""),
                "fuser_kit": counters.get("fuser_kit", ""),
                "transfer_kit": counters.get("transfer_kit", ""),
                "waste_toner": counters.get("waste_toner", ""),
                "last_date": last_date,
                "last_date_iso": last_date_iso,
                "is_fresh": is_fresh,
            }
        )

    # === Блок статистики: недавние ошибки инвентаризации ===
    # Отсечка "недавности" — последние 24 часа (при необходимости замените на вашу бизнес-логику)
    recent_cutoff = timezone.now() - timedelta(hours=24)
    recent_failed = (
        InventoryTask.objects
        .filter(
            task_timestamp__gte=recent_cutoff,
            status__in=["FAILED", "VALIDATION_ERROR", "HISTORICAL_INCONSISTENCY"]  # Добавлен новый статус
        )
        .values("printer")
        .distinct()
        .count()
    )

    per_page_options = [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]
    organizations = Organization.objects.filter(active=True).order_by("name")

    context = {
        "data": data,
        "page_obj": page_obj,
        "q_ip": q_ip,
        "q_model": q_model,
        "q_serial": q_serial,
        "q_org": q_org,
        "q_rule": q_rule,
        "per_page": per_page,
        "per_page_options": per_page_options,
        "organizations": organizations,
        "celery_available": CELERY_AVAILABLE,
        "redis_status": get_redis_health_status(),
        "recent_failed": recent_failed,  # <- в контекст
        "recent_cutoff": recent_cutoff,  # если нужно показать в шаблоне
    }

    cache.set(cache_key, context, timeout=300)
    return render(request, "inventory/index.html", context)

# ──────────────────────────────────────────────────────────────────────────────
# EXPORTS
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.export_printers", raise_exception=True)
def export_excel(request):
    cache_key = f"export_excel_{hash(request.GET.urlencode())}"
    cached_response = cache.get(cache_key)
    if cached_response:
        logger.info("Using cached export data")
        return cached_response

    q_ip = request.GET.get("q_ip", "").strip()
    q_model = request.GET.get("q_model", "").strip()
    q_serial = request.GET.get("q_serial", "").strip()
    q_org = request.GET.get("q_org", "").strip()
    q_rule = request.GET.get("q_rule", "").strip()

    qs = Printer.objects.select_related("organization").all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    if q_org == "none":
        qs = qs.filter(organization__isnull=True)
    elif q_org:
        try:
            qs = qs.filter(organization_id=int(q_org))
        except ValueError:
            qs = qs.filter(organization__name__icontains=q_org)

    if q_rule in ("SN_MAC", "MAC_ONLY", "SN_ONLY"):
        qs = qs.filter(last_match_rule=q_rule)
    elif q_rule == "NONE":
        qs = qs.filter(last_match_rule__isnull=True)

    qs = qs.order_by("ip_address")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Printers"

    headers = [
        "Организация",
        "IP-адрес",
        "Серийный №",
        "MAC-адрес",
        "Модель",
        "ЧБ A4",
        "Цвет A4",
        "ЧБ A3",
        "Цвет A3",
        "Всего",
        "Тонер K",
        "Тонер C",
        "Тонер M",
        "Тонер Y",
        "Барабан K",
        "Барабан C",
        "Барабан M",
        "Барабан Y",
        "Fuser Kit",
        "Transfer Kit",
        "Waste Toner",
        "Правило",
        "Дата последнего опроса",
        "Статус последнего опроса",  # Новый столбец
        "Последняя ошибка",          # Новый столбец
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = openpyxl.styles.Font(bold=True)

    col_widths = [len(h) for h in headers]

    # индекс колонки с датой (1-based)
    date_col_idx = headers.index("Дата последнего опроса") + 1

    rule_label = {
        "SN_MAC": "Серийник+MAC",
        "MAC_ONLY": "Только MAC",
        "SN_ONLY": "Только серийник",
    }

    row_idx = 2
    for p in qs:
        inv_status = get_printer_inventory_status(p.id)
        counters = inv_status.get("counters", {})

        dt_value = None
        if inv_status.get("timestamp"):
            try:
                dt = timezone.datetime.fromisoformat(inv_status["timestamp"].replace("Z", "+00:00"))
                dt_value = localtime(dt).replace(tzinfo=None)
            except Exception:
                pass

        # Последняя задача инвентаризации для статуса/ошибки
        last_task = InventoryTask.objects.filter(printer=p).order_by("-task_timestamp").first()
        if last_task:
            try:
                status_map = dict(InventoryTask.STATUS_CHOICES)
                last_status = status_map.get(last_task.status, last_task.status or "—")
            except Exception:
                last_status = last_task.status or "—"
        else:
            last_status = "—"

        last_error = ""
        if last_task and last_task.status in ["FAILED", "VALIDATION_ERROR", "HISTORICAL_INCONSISTENCY"]:
            last_error = (last_task.error_message or "")[:100]

        values = [
            p.organization.name if p.organization_id else "—",
            p.ip_address,
            p.serial_number,
            p.mac_address or "",
            p.model,
            counters.get("bw_a4", ""),
            counters.get("color_a4", ""),
            counters.get("bw_a3", ""),
            counters.get("color_a3", ""),
            counters.get("total_pages", ""),
            counters.get("toner_black", ""),
            counters.get("toner_cyan", ""),
            counters.get("toner_magenta", ""),
            counters.get("toner_yellow", ""),
            counters.get("drum_black", ""),
            counters.get("drum_cyan", ""),
            counters.get("drum_magenta", ""),
            counters.get("drum_yellow", ""),
            counters.get("fuser_kit", ""),
            counters.get("transfer_kit", ""),
            counters.get("waste_toner", ""),
            rule_label.get(p.last_match_rule, "—"),
            dt_value,
            last_status,
            last_error,
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)

            # формат для даты в нужной колонке
            if col_idx == date_col_idx and dt_value:
                cell.number_format = "dd.mm.yyyy hh:mm"

            # расчёт ширины столбца
            disp = val if val is not None else ""
            if hasattr(val, "strftime"):
                disp = val.strftime("%d.%m.%Y %H:%M")
            col_widths[col_idx - 1] = max(col_widths[col_idx - 1], len(str(disp)))

        row_idx += 1

    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(w + 2, 10), 50)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="printers.xlsx"'
    wb.save(response)

    cache.set(cache_key, response, timeout=120)
    return response



@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.export_amb_report", raise_exception=True)
def export_amb(request):
    if request.method != "POST" or "template" not in request.FILES:
        return render(request, "inventory/export_amb.html")

    wb = openpyxl.load_workbook(request.FILES["template"])
    ws = wb.active

    # 1) Поиск строки заголовков
    header_row = next(
        (r for r in range(1, 11) if any(str(c.value).strip().lower() == "серийный номер оборудования" for c in ws[r])),
        None,
    )
    if not header_row:
        return HttpResponse("Строка заголовков не найдена.", status=400)

    headers = {
        str(ws.cell(row=header_row, column=col).value).strip().lower(): col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row=header_row, column=col).value
    }
    lookup = {
        "serial": lambda k: "серийный номер оборудования" in k,
        "a4_bw": lambda k: "ч/б" in k and "конец периода" in k and "а4" in k,
        "a4_color": lambda k: "цветные" in k and "конец периода" in k and "а4" in k,
        "a3_bw": lambda k: "ч/б" in k and "конец периода" in k and "а3" in k,
        "a3_color": lambda k: "цветные" in k and "конец периода" in k and "а3" in k,
    }
    cols = {}
    for internal, cond in lookup.items():
        for key, idx in headers.items():
            if cond(key):
                cols[internal] = idx
                break
        if internal not in cols:
            return HttpResponse(f"Колонка для '{internal}' не найдена.", status=400)

    # 2) Серийники
    serial_cells = []
    for row in range(header_row + 1, ws.max_row + 1):
        raw = ws.cell(row=row, column=cols["serial"]).value
        serial = str(raw).strip() if raw else ""
        if serial:
            serial_cells.append((row, serial))
    serials = {s for _, s in serial_cells}
    if not serials:
        return HttpResponse("В файле нет серийных номеров.", status=400)

    # 3) Данные инвентаризации из кэша/БД
    counters_by_serial = {}
    for serial in serials:
        try:
            printer = Printer.objects.get(serial_number=serial)
            inv_status = get_printer_inventory_status(printer.id)
            counters = inv_status.get("counters", {})
            timestamp = inv_status.get("timestamp")
            if counters and timestamp:
                counters_by_serial[serial] = {"counters": counters, "timestamp": timestamp}
        except Printer.DoesNotExist:
            continue

    # 4) Запись значений
    date_col = ws.max_column + 1
    ws.cell(row=header_row, column=date_col, value="Дата опроса")

    for row_idx, serial in serial_cells:
        data = counters_by_serial.get(serial)
        if not data:
            continue

        counters = data["counters"]
        ws.cell(row=row_idx, column=cols["a4_bw"], value=counters.get("bw_a4") or 0)
        ws.cell(row=row_idx, column=cols["a4_color"], value=counters.get("color_a4") or 0)
        ws.cell(row=row_idx, column=cols["a3_bw"], value=counters.get("bw_a3") or 0)
        ws.cell(row=row_idx, column=cols["a3_color"], value=counters.get("color_a3") or 0)

        # Дата
        try:
            dt = timezone.datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            dt_local = localtime(dt).replace(tzinfo=None)
            c = ws.cell(row=row_idx, column=date_col, value=dt_local)
            c.number_format = "dd.mm.yyyy hh:mm"
        except Exception:
            pass

    # 5) Отдаём результат
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="amb_report.xlsx"'
    wb.save(response)
    wb.close()
    return response


# ──────────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.add_printer", raise_exception=True)
def add_printer(request):
    form = PrinterForm(request.POST or None)
    if form.is_valid():
        printer = form.save()
        cache_printer_data(printer)  # прогреем кэш
        messages.success(request, "Принтер добавлен")
        return redirect("inventory:printer_list")
    return render(request, "inventory/add_printer.html", {"form": form})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.change_printer", raise_exception=True)
def edit_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST or None, instance=printer)
    if request.method == "POST" and form.is_valid():
        printer = form.save()
        cache_printer_data(printer)  # обновим кэш
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "printer": {
                        "id": printer.id,
                        "ip_address": printer.ip_address,
                        "serial_number": printer.serial_number,
                        "mac_address": printer.mac_address,
                        "model": printer.model,
                        "snmp_community": printer.snmp_community,
                        "organization": printer.organization.name if printer.organization_id else None,
                        "organization_id": printer.organization_id,
                    },
                }
            )
        messages.success(request, "Принтер обновлён")
        return redirect("inventory:printer_list")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": False, "error": form.errors.as_json()}, status=400)
    return render(request, "inventory/edit_printer.html", {"form": form})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.delete_printer", raise_exception=True)
def delete_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)

    if request.method == "POST":
        invalidate_printer_cache(pk)  # очистим кэш
        printer.delete()
        messages.success(request, "Принтер удалён")
        return JsonResponse({"success": True})

    # GET → отрисовываем список с открытой модалкой подтверждения (из первой версии)
    q_ip = request.GET.get("q_ip", "").strip()
    q_model = request.GET.get("q_model", "").strip()
    q_serial = request.GET.get("q_serial", "").strip()
    q_org = request.GET.get("q_org", "").strip()
    q_rule = request.GET.get("q_rule", "").strip()
    per_page = request.GET.get("per_page", "100").strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    qs = Printer.objects.select_related("organization").all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    if q_org == "none":
        qs = qs.filter(organization__isnull=True)
    elif q_org:
        try:
            qs = qs.filter(organization_id=int(q_org))
        except ValueError:
            qs = qs.filter(organization__name__icontains=q_org)

    if q_rule in ("SN_MAC", "MAC_ONLY", "SN_ONLY"):
        qs = qs.filter(last_match_rule=q_rule)
    elif q_rule == "NONE":
        qs = qs.filter(last_match_rule__isnull=True)

    qs = qs.order_by("ip_address")
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    data = []
    for p in page_obj:
        last_task = (
            InventoryTask.objects.filter(printer=p, status="SUCCESS").order_by("-task_timestamp").first()
        )
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        last_date = localtime(last_task.task_timestamp).strftime("%d.%m.%Y %H:%M") if last_task else "—"
        last_date_iso = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ""
        data.append(
            {
                "printer": p,
                "bw_a4": getattr(counter, "bw_a4", None),
                "color_a4": getattr(counter, "color_a4", None),
                "bw_a3": getattr(counter, "bw_a3", None),
                "color_a3": getattr(counter, "color_a3", None),
                "total": getattr(counter, "total_pages", None),
                "drum_black": getattr(counter, "drum_black", ""),
                "drum_cyan": getattr(counter, "drum_cyan", ""),
                "drum_magenta": getattr(counter, "drum_magenta", ""),
                "drum_yellow": getattr(counter, "drum_yellow", ""),
                "toner_black": getattr(counter, "toner_black", ""),
                "toner_cyan": getattr(counter, "toner_cyan", ""),
                "toner_magenta": getattr(counter, "toner_magenta", ""),
                "toner_yellow": getattr(counter, "toner_yellow", ""),
                "fuser_kit": getattr(counter, "fuser_kit", ""),
                "transfer_kit": getattr(counter, "transfer_kit", ""),
                "waste_toner": getattr(counter, "waste_toner", ""),
                "last_date": last_date,
                "last_date_iso": last_date_iso,
            }
        )

    per_page_options = [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]

    return render(
        request,
        "inventory/index.html",
        {
            "data": data,
            "page_obj": page_obj,
            "q_ip": q_ip,
            "q_model": q_model,
            "q_serial": q_serial,
            "q_org": q_org,
            "q_rule": q_rule,
            "per_page": per_page,
            "per_page_options": per_page_options,
            "organizations": Organization.objects.filter(active=True).order_by("name"),
            "confirm_delete_pk": pk,
            "printer": printer,
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# HISTORY
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def history_view(request, pk):
    printer = get_object_or_404(Printer, pk=pk)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        cache_key = f"printer_history_{pk}"
        cached_history = cache.get(cache_key)
        if cached_history:
            return JsonResponse(cached_history, safe=False)

        # Включаем все статусы, включая HISTORICAL_INCONSISTENCY
        daily_tasks = (
            InventoryTask.objects.filter(
                printer=printer,
                status__in=['SUCCESS', 'HISTORICAL_INCONSISTENCY']  # Показываем исторические несоответствия
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

            # Для исторических несоответствий показываем предыдущие данные или NULL
            if t.status == 'HISTORICAL_INCONSISTENCY':
                # Ищем последние валидные данные
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
                "waste_toner": c.waste_toner if c else None,"is_historical_issue": t.status == 'HISTORICAL_INCONSISTENCY',
                "error_message": t.error_message if t.status == 'HISTORICAL_INCONSISTENCY' else None,
            })


        cache.set(cache_key, data, timeout=900)
        return JsonResponse(data, safe=False)

    # HTML версия — постранично
    tasks = InventoryTask.objects.filter(printer=printer, status="SUCCESS").order_by("-task_timestamp")
    paginator = Paginator(tasks, 50)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [(t, PageCounter.objects.filter(task=t).first()) for t in page_obj]

    return render(request, "inventory/history.html", {"printer": printer, "rows": rows, "page_obj": page_obj})


# ──────────────────────────────────────────────────────────────────────────────
# RUNNERS
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def run_inventory(request, pk):
    pk = int(pk)

    # Проверяем rate limit для пользователя
    from inventory.tasks import UserRateLimiter
    if not UserRateLimiter.check_rate_limit(request.user.id, pk):
        return JsonResponse(
            {
                "success": False,
                "error": "Слишком много запросов. Попробуйте через минуту.",
            },
            status=429,
        )

    if CELERY_AVAILABLE:
        try:
            # Используем приоритетную задачу для пользовательских запросов
            from inventory.tasks import run_inventory_task_priority

            task = run_inventory_task_priority.apply_async(
                args=[pk, request.user.id],
                priority=9,  # Высокий приоритет
            )
            logger.info(
                f"Queued PRIORITY Celery inventory task {task.id} for printer {pk} by user {request.user.id}"
            )
            return JsonResponse({"success": True, "celery": True, "task_id": task.id, "queued": True})
        except Exception as e:
            logger.error(f"Error queuing priority Celery task for printer {pk}: {e}")
            # Снимаем лок, чтобы пользователь мог повторить попытку
            try:
                UserRateLimiter.clear_printer_lock(request.user.id, pk)
            except Exception:
                pass
            return JsonResponse({"success": False, "celery": True, "error": str(e)}, status=500)
    else:
        queued = _queue_inventory(pk)
        return JsonResponse({"success": True, "celery": False, "queued": queued})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def run_inventory_all(request):
    # Проверяем базовый rate limit для массовых операций
    user_key = f"inventory_bulk_user_{request.user.id}"
    if cache.get(user_key):
        return JsonResponse(
            {
                "success": False,
                "error": "Массовый опрос можно запускать не чаще раза в 5 минут.",
            },
            status=429,
        )

    cache.set(user_key, True, timeout=300)  # 5 минут блокировка

    if CELERY_AVAILABLE:
        try:
            # Для массового опроса используем обычную задачу демона (средний приоритет)
            task = inventory_daemon_task.apply_async(priority=5)
            logger.info(f"User {request.user.id} queued Celery daemon task {task.id}")
            return JsonResponse({"success": True, "celery": True, "task_id": task.id, "queued": True})
        except Exception as e:
            logger.error(f"Error queuing Celery daemon task: {e}")
            cache.delete(user_key)
            return JsonResponse({"success": False, "celery": True, "error": str(e)}, status=500)
    else:
        from concurrent.futures import ThreadPoolExecutor

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(inventory_daemon)
        return JsonResponse({"success": True, "celery": False, "queued": True})


# ──────────────────────────────────────────────────────────────────────────────
# APIs
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def api_printers(request):
    cache_key = f"api_printers_{request.user.id}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return JsonResponse(cached_response, safe=False)

    output = []
    for p in Printer.objects.select_related("organization").all():
        inv_status = get_printer_inventory_status(p.id)
        counters = inv_status.get("counters", {})

        ts_ms = ""
        if inv_status.get("timestamp"):
            try:
                dt = timezone.datetime.fromisoformat(inv_status["timestamp"].replace("Z", "+00:00"))
                ts_ms = int(dt.timestamp() * 1000)
            except Exception:
                pass

        output.append(
            {
                "id": p.id,
                "ip_address": p.ip_address,
                "serial_number": p.serial_number,
                "mac_address": p.mac_address or "-",
                "model": p.model,
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
            }
        )

    cache.set(cache_key, output, timeout=300)
    return JsonResponse(output, safe=False)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_printer", raise_exception=True)
def api_printer(request, pk):
    pk = int(pk)
    printer = get_object_or_404(Printer, pk=pk)

    cached_data = get_cached_printer_data(pk) or cache_printer_data(printer)
    inv_status = get_printer_inventory_status(pk)
    counters = inv_status.get("counters", {})

    ts_ms = ""
    if inv_status.get("timestamp"):
        try:
            dt = timezone.datetime.fromisoformat(inv_status["timestamp"].replace("Z", "+00:00"))
            ts_ms = int(dt.timestamp() * 1000)
        except Exception:
            pass

    data = {
        "id": printer.id,
        "ip_address": printer.ip_address,
        "serial_number": printer.serial_number,
        "mac_address": printer.mac_address or "-",
        "model": printer.model,
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


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.run_inventory", raise_exception=True)
@require_POST
def api_probe_serial(request):
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
# МОНИТОРИНГ REDIS/CELERY + УПРАВЛЕНИЕ КЭШЕМ
# ──────────────────────────────────────────────────────────────────────────────
@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_system_status(request):
    """API для получения статуса системы, Redis и Celery."""
    redis_status = get_redis_health_status()

    celery_status = {"available": CELERY_AVAILABLE}
    if CELERY_AVAILABLE:
        try:
            from celery import current_app

            inspect = current_app.control.inspect()
            active_workers = inspect.active()
            stats = inspect.stats()

            celery_status.update(
                {
                    "workers_count": len(stats) if stats else 0,
                    "workers_active": len(active_workers) if active_workers else 0,
                    "broker_url": current_app.conf.broker_url,
                    "result_backend": current_app.conf.result_backend,
                }
            )

            if stats:
                total_completed = sum(s.get("total", {}).get("completed", 0) for s in stats.values())
                total_failed = sum(s.get("total", {}).get("failed", 0) for s in stats.values())
                celery_status.update(
                    {
                        "total_completed": total_completed,
                        "total_failed": total_failed,
                        "success_rate": (total_completed / (total_completed + total_failed) * 100)
                        if (total_completed + total_failed) > 0
                        else 0,
                    }
                )
        except Exception as e:
            celery_status["error"] = str(e)

    printer_stats = get_cached_printer_statistics()
    if not printer_stats:
        total_printers = Printer.objects.count()
        printer_stats = {
            "total_printers": total_printers,
            "cache_miss": True,
            "updated_at": timezone.now().isoformat(),
        }

    # Информация о бэкендах кэша (без прямого доступа к приватным атрибутам)
    cache_backends = {
        "main_cache_alias": getattr(settings, "CACHES", {}).get("default", {}).get("BACKEND", "Unknown"),
        "inventory_cache_alias": getattr(settings, "CACHES", {}).get("inventory", {}).get("BACKEND", "Fallback(default)")
        if hasattr(settings, "CACHES")
        else "Unknown",
    }

    return JsonResponse(
        {
            "timestamp": timezone.now().isoformat(),
            "redis": redis_status,
            "celery": celery_status,
            "printers": printer_stats,
            "cache_info": cache_backends,
        }
    )


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_cache_control(request):
    """API для управления кэшем."""
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "clear_all":
            try:
                cache.clear()
                inventory_cache.clear()
                return JsonResponse({"success": True, "message": "Весь кэш очищен"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "clear_printer":
            printer_id = request.POST.get("printer_id")
            if printer_id:
                try:
                    invalidate_printer_cache(int(printer_id))
                    return JsonResponse({"success": True, "message": f"Кэш принтера {printer_id} очищен"})
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)})
            else:
                return JsonResponse({"success": False, "error": "printer_id не указан"})

        elif action == "warm_cache":
            try:
                from .services import warm_printer_cache

                count = warm_printer_cache()
                return JsonResponse({"success": True, "message": f"Кэш прогрет для {count} принтеров"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Неверный запрос"})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
def api_status_statistics(request):
    """API для получения статистики по статусам задач"""
    from datetime import timedelta
    from django.db.models import Count, Q

    # Параметры временного интервала
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)

    # Общая статистика
    total_tasks = InventoryTask.objects.filter(task_timestamp__gte=start_date).count()

    # Статистика по статусам
    status_stats = InventoryTask.objects.filter(
        task_timestamp__gte=start_date
    ).values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    # Преобразуем в читаемый формат
    status_data = []
    for stat in status_stats:
        status_display = dict(InventoryTask.STATUS_CHOICES).get(stat['status'], stat['status'])
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
        'printer__ip_address', 'printer__model', 'status'
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