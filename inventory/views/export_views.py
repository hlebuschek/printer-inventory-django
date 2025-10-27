# inventory/views/export_views.py
"""
Export views for generating Excel reports and AMB templates.
Handles data export for external systems and reporting.
"""

import logging

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.http import HttpResponse
from django.utils.timezone import localtime
from django.utils import timezone

import openpyxl
from openpyxl.utils import get_column_letter

from ..models import Printer, InventoryTask
from ..services import get_printer_inventory_status

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.export_printers", raise_exception=True)
def export_excel(request):
    """
    Экспорт списка принтеров в Excel с фильтрацией.
    БЕЗ кэширования - данные читаются напрямую из БД.
    """
    # Применяем те же фильтры, что и в списке
    q_ip = request.GET.get("q_ip", "").strip()
    q_model = request.GET.get("q_model", "").strip()
    q_serial = request.GET.get("q_serial", "").strip()
    q_org = request.GET.get("q_org", "").strip()
    q_rule = request.GET.get("q_rule", "").strip()

    qs = Printer.objects.select_related(
        "organization",
        "device_model",
        "device_model__manufacturer"
    ).all()

    # Фильтры
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)

    if q_model:
        from django.db.models import Q
        qs = qs.filter(
            Q(model__icontains=q_model) |
            Q(device_model__name__icontains=q_model) |
            Q(device_model__manufacturer__name__icontains=q_model)
        )

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

    # Создаём Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Printers"

    # Заголовки
    headers = [
        "Организация", "IP-адрес", "Серийный №", "MAC-адрес", "Модель",
        "ЧБ A4", "Цвет A4", "ЧБ A3", "Цвет A3", "Всего",
        "Тонер K", "Тонер C", "Тонер M", "Тонер Y",
        "Барабан K", "Барабан C", "Барабан M", "Барабан Y",
        "Fuser Kit", "Transfer Kit", "Waste Toner",
        "Правило", "Дата последнего опроса",
        "Статус последнего опроса", "Последняя ошибка",
    ]

    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = openpyxl.styles.Font(bold=True)

    col_widths = [len(h) for h in headers]
    date_col_idx = headers.index("Дата последнего опроса") + 1

    rule_label = {
        "SN_MAC": "Серийник+MAC",
        "MAC_ONLY": "Только MAC",
        "SN_ONLY": "Только серийник",
    }

    # Заполняем данные
    row_idx = 2
    for p in qs:
        inv_status = get_printer_inventory_status(p.id)
        counters = inv_status.get("counters", {})

        # Дата последнего опроса
        dt_value = None
        if inv_status.get("timestamp"):
            try:
                dt = timezone.datetime.fromisoformat(inv_status["timestamp"].replace("Z", "+00:00"))
                dt_value = localtime(dt).replace(tzinfo=None)
            except Exception:
                pass

        # Последняя задача для статуса/ошибки
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
            p.model_display,  # Используем свойство model_display
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

            if col_idx == date_col_idx and dt_value:
                cell.number_format = "dd.mm.yyyy hh:mm"

            disp = val if val is not None else ""
            if hasattr(val, "strftime"):
                disp = val.strftime("%d.%m.%Y %H:%M")
            col_widths[col_idx - 1] = max(col_widths[col_idx - 1], len(str(disp)))

        row_idx += 1

    # Автоподбор ширины колонок
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(w + 2, 10), 50)

    # Возвращаем файл
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="printers.xlsx"'
    wb.save(response)

    return response


# ──────────────────────────────────────────────────────────────────────────────
# AMB REPORT EXPORT
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.export_amb_report", raise_exception=True)
def export_amb(request):
    """
    Экспорт AMB отчёта на основе загруженного шаблона.
    БЕЗ кэширования - данные читаются напрямую из БД.
    """
    if request.method != "POST" or "template" not in request.FILES:
        return render(request, "inventory/export_amb.html")

    # Загружаем шаблон
    wb = openpyxl.load_workbook(request.FILES["template"])
    ws = wb.active

    # Поиск строки заголовков
    header_row = next(
        (r for r in range(1, 11) if any(
            str(c.value).strip().lower() == "серийный номер оборудования" for c in ws[r]
        )),
        None,
    )
    if not header_row:
        return HttpResponse("Строка заголовков не найдена.", status=400)

    # Парсим заголовки
    headers = {
        str(ws.cell(row=header_row, column=col).value).strip().lower(): col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row=header_row, column=col).value
    }

    # Находим нужные колонки
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

    # Собираем серийные номера из файла
    serial_cells = []
    for row in range(header_row + 1, ws.max_row + 1):
        raw = ws.cell(row=row, column=cols["serial"]).value
        serial = str(raw).strip() if raw else ""
        if serial:
            serial_cells.append((row, serial))

    serials = {s for _, s in serial_cells}
    if not serials:
        return HttpResponse("В файле нет серийных номеров.", status=400)

    # Получаем данные инвентаризации напрямую из БД
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

    # Добавляем колонку для даты опроса
    date_col = ws.max_column + 1
    ws.cell(row=header_row, column=date_col, value="Дата опроса")

    # Заполняем данные
    for row_idx, serial in serial_cells:
        data = counters_by_serial.get(serial)
        if not data:
            continue

        counters = data["counters"]
        ws.cell(row=row_idx, column=cols["a4_bw"], value=counters.get("bw_a4") or 0)
        ws.cell(row=row_idx, column=cols["a4_color"], value=counters.get("color_a4") or 0)
        ws.cell(row=row_idx, column=cols["a3_bw"], value=counters.get("bw_a3") or 0)
        ws.cell(row=row_idx, column=cols["a3_color"], value=counters.get("color_a3") or 0)

        # Дата опроса
        try:
            dt = timezone.datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            dt_local = localtime(dt).replace(tzinfo=None)
            c = ws.cell(row=row_idx, column=date_col, value=dt_local)
            c.number_format = "dd.mm.yyyy hh:mm"
        except Exception:
            pass

    # Возвращаем файл
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="amb_report.xlsx"'
    wb.save(response)
    wb.close()

    return response