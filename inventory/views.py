from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

import openpyxl
from openpyxl.utils import get_column_letter

from concurrent.futures import ThreadPoolExecutor
import threading

from .models import Printer, InventoryTask, PageCounter, Organization
from .forms import PrinterForm
from .services import run_inventory_for_printer, inventory_daemon

import json
from .services import extract_serial_from_xml

# ---------- Пул фоновых задач + предохранитель от дублей ----------
EXECUTOR = ThreadPoolExecutor(max_workers=5)
_RUNNING: set[int] = set()
_RUNNING_LOCK = threading.Lock()


def _queue_inventory(pk: int) -> bool:
    """
    Ставит опрос принтера в очередь. Возвращает False, если уже идёт.
    """
    with _RUNNING_LOCK:
        if pk in _RUNNING:
            return False
        _RUNNING.add(pk)

    def _job():
        try:
            try:
                run_inventory_for_printer(pk)
            except Exception:
                # здесь можно залогировать traceback
                pass
        finally:
            with _RUNNING_LOCK:
                _RUNNING.discard(pk)

    EXECUTOR.submit(_job)
    return True


# ------------------------------- LIST -------------------------------

@login_required
def printer_list(request):
    q_ip     = request.GET.get('q_ip', '').strip()
    q_model  = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    q_org    = request.GET.get('q_org', '').strip()
    q_rule   = request.GET.get('q_rule', '').strip()  # SN_MAC / MAC_ONLY / SN_ONLY / NONE
    per_page = request.GET.get('per_page', '100').strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    qs = Printer.objects.select_related('organization').all()

    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
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
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    data = []
    for p in page_obj:
        last_task = (
            InventoryTask.objects
            .filter(printer=p, status='SUCCESS')
            .order_by('-task_timestamp')
            .first()
        )
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None

        if last_task:
            last_date_iso = int(last_task.task_timestamp.timestamp() * 1000)
            last_date = localtime(last_task.task_timestamp).strftime('%d.%m.%Y %H:%M')
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


# ----------------------------- EXPORTS ------------------------------

@login_required
def export_excel(request):
    # Фильтры как в списке
    q_ip     = request.GET.get('q_ip', '').strip()
    q_model  = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    q_org    = request.GET.get('q_org', '').strip()
    q_rule   = request.GET.get('q_rule', '').strip()

    qs = Printer.objects.select_related('organization').all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
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

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Printers'

    headers = [
        'Организация', 'IP-адрес', 'Серийный №', 'MAC-адрес', 'Модель',
        'ЧБ A4', 'Цвет A4', 'ЧБ A3', 'Цвет A3', 'Всего',
        'Тонер K', 'Тонер C', 'Тонер M', 'Тонер Y',
        'Барабан K', 'Барабан C', 'Барабан M', 'Барабан Y',
        'Fuser Kit', 'Transfer Kit', 'Waste Toner',
        'Правило', 'Дата последнего опроса'
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = openpyxl.styles.Font(bold=True)

    col_widths = [len(h) for h in headers]

    rule_label = {
        'SN_MAC':   'Серийник+MAC',
        'MAC_ONLY': 'Только MAC',
        'SN_ONLY':  'Только серийник',
    }

    row_idx = 2
    for p in qs:
        last_task = (
            InventoryTask.objects
            .filter(printer=p, status='SUCCESS')
            .order_by('-task_timestamp')
            .first()
        )
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None

        # Excel-friendly datetime (без tz), чтобы формат работал как дата
        dt_value = None
        if last_task:
            dt_value = localtime(last_task.task_timestamp).replace(tzinfo=None)

        values = [
            p.organization.name if p.organization_id else '—',
            p.ip_address,
            p.serial_number,
            p.mac_address or '',
            p.model,
            getattr(counter, 'bw_a4', ''),
            getattr(counter, 'color_a4', ''),
            getattr(counter, 'bw_a3', ''),
            getattr(counter, 'color_a3', ''),
            getattr(counter, 'total_pages', ''),
            getattr(counter, 'toner_black', ''),
            getattr(counter, 'toner_cyan', ''),
            getattr(counter, 'toner_magenta', ''),
            getattr(counter, 'toner_yellow', ''),
            getattr(counter, 'drum_black', ''),
            getattr(counter, 'drum_cyan', ''),
            getattr(counter, 'drum_magenta', ''),
            getattr(counter, 'drum_yellow', ''),
            getattr(counter, 'fuser_kit', ''),
            getattr(counter, 'transfer_kit', ''),
            getattr(counter, 'waste_toner', ''),
            rule_label.get(p.last_match_rule, '—'),
            dt_value,
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            # последний столбец — отформатированная дата
            if col_idx == len(headers) and dt_value:
                cell.number_format = 'dd.mm.yyyy hh:mm'

            disp = val if val is not None else ''
            if hasattr(val, 'strftime'):
                disp = val.strftime('%d.%m.%Y %H:%M')
            col_widths[col_idx - 1] = max(col_widths[col_idx - 1], len(str(disp)))

        row_idx += 1

    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(w + 2, 10), 50)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="printers.xlsx"'
    wb.save(response)
    return response


@login_required
def export_amb(request):
    if request.method != 'POST' or 'template' not in request.FILES:
        return render(request, 'inventory/export_amb.html')

    wb = openpyxl.load_workbook(request.FILES['template'])
    ws = wb.active

    # 1) Поиск строки заголовков
    header_row = next(
        (r for r in range(1, 11)
         if any(str(c.value).strip().lower() == 'серийный номер оборудования' for c in ws[r])),
        None
    )
    if not header_row:
        return HttpResponse("Строка заголовков не найдена.", status=400)

    headers = {
        str(ws.cell(row=header_row, column=col).value).strip().lower(): col
        for col in range(1, ws.max_column + 1)
        if ws.cell(row=header_row, column=col).value
    }
    lookup = {
        'serial'    : lambda k: 'серийный номер оборудования' in k,
        'a4_bw'     : lambda k: 'ч/б'  in k and 'конец периода' in k and 'а4' in k,
        'a4_color'  : lambda k: 'цветные' in k and 'конец периода' in k and 'а4' in k,
        'a3_bw'     : lambda k: 'ч/б'  in k and 'конец периода' in k and 'а3' in k,
        'a3_color'  : lambda k: 'цветные' in k and 'конец периода' in k and 'а3' in k,
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
        raw = ws.cell(row=row, column=cols['serial']).value
        serial = str(raw).strip() if raw else ''
        if serial:
            serial_cells.append((row, serial))
    serials = {s for _, s in serial_cells}
    if not serials:
        return HttpResponse("В файле нет серийных номеров.", status=400)

    # 3) Последние SUCCESS-задачи по каждому серийнику
    latest_tasks = (
        InventoryTask.objects
        .filter(printer__serial_number__in=serials, status='SUCCESS')
        .order_by('printer__serial_number', '-task_timestamp')
        .distinct('printer__serial_number')  # PostgreSQL
        .select_related('printer')
        .values('id', 'printer__serial_number', 'task_timestamp', 'printer_id')
    )
    task_by_serial = {t['printer__serial_number']: t for t in latest_tasks}

    # 4) Счётчики
    counters = (
        PageCounter.objects
        .filter(task_id__in=[t['id'] for t in latest_tasks])
        .values('task_id', 'bw_a4', 'color_a4', 'bw_a3', 'color_a3')
    )
    counter_by_task = {c['task_id']: c for c in counters}

    # 5) Запись значений
    date_col = ws.max_column + 1
    ws.cell(row=header_row, column=date_col, value='Дата опроса')

    for row_idx, serial in serial_cells:
        task = task_by_serial.get(serial)
        if not task:
            continue
        counter = counter_by_task.get(task['id'])
        if not counter:
            continue

        ws.cell(row=row_idx, column=cols['a4_bw'],    value=counter['bw_a4'] or 0)
        ws.cell(row=row_idx, column=cols['a4_color'], value=counter['color_a4'] or 0)
        ws.cell(row=row_idx, column=cols['a3_bw'],    value=counter['bw_a3'] or 0)
        ws.cell(row=row_idx, column=cols['a3_color'], value=counter['color_a3'] or 0)

        dt_local = localtime(task['task_timestamp']).replace(tzinfo=None)
        c = ws.cell(row=row_idx, column=date_col, value=dt_local)
        c.number_format = 'dd.mm.yyyy hh:mm'

    # 6) Отдаём результат
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="amb_report.xlsx"'
    wb.save(response)
    wb.close()
    return response


# --------------------------- CRUD (forms/modals) ---------------------------

@login_required
def add_printer(request):
    form = PrinterForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Принтер добавлен")
        return redirect('printer_list')
    return render(request, 'inventory/add_printer.html', {'form': form})


@login_required
def edit_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST or None, instance=printer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'printer': {
                    'id': printer.id,
                    'ip_address': printer.ip_address,
                    'serial_number': printer.serial_number,
                    'mac_address': printer.mac_address,
                    'model': printer.model,
                    'snmp_community': printer.snmp_community,
                    'organization': printer.organization.name if printer.organization_id else None,
                    'organization_id': printer.organization_id
                }
            })
        messages.success(request, "Принтер обновлён")
        return redirect('printer_list')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': form.errors.as_json()}, status=400)
    return render(request, 'inventory/edit_printer.html', {'form': form})


@login_required
def delete_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)

    if request.method == 'POST':
        printer.delete()
        messages.success(request, "Принтер удалён")
        return JsonResponse({'success': True})

    # GET → отрисовываем список с открытой модалкой подтверждения
    q_ip     = request.GET.get('q_ip', '').strip()
    q_model  = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    q_org    = request.GET.get('q_org', '').strip()
    q_rule   = request.GET.get('q_rule', '').strip()
    per_page = request.GET.get('per_page', '100').strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    qs = Printer.objects.select_related('organization').all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
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
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    data = []
    for p in page_obj:
        last_task = InventoryTask.objects.filter(printer=p, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        last_date = localtime(last_task.task_timestamp).strftime('%d.%m.%Y %H:%M') if last_task else '—'
        last_date_iso = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ''
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
        'confirm_delete_pk': pk,
        'printer': printer,
    })


# ------------------------------ HISTORY ------------------------------

@login_required
def history_view(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    tasks = InventoryTask.objects.filter(printer=printer, status='SUCCESS').order_by('-task_timestamp')
    paginator = Paginator(tasks, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    rows = [(t, PageCounter.objects.filter(task=t).first()) for t in page_obj]
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = [{
            'task_timestamp': localtime(t.task_timestamp).strftime('%Y-%m-%dT%H:%M:%S'),
            'match_rule': t.match_rule,
            'bw_a4': c.bw_a4 if c else None,
            'color_a4': c.color_a4 if c else None,
            'bw_a3': c.bw_a3 if c else None,
            'color_a3': c.color_a3 if c else None,
            'total_pages': c.total_pages if c else None,
            'drum_black': c.drum_black if c else None,
            'drum_cyan': c.drum_cyan if c else None,
            'drum_magenta': c.drum_magenta if c else None,
            'drum_yellow': c.drum_yellow if c else None,
            'toner_black': c.toner_black if c else None,
            'toner_cyan': c.toner_cyan if c else None,
            'toner_magenta': c.toner_magenta if c else None,
            'toner_yellow': c.toner_yellow if c else None,
            'fuser_kit': c.fuser_kit if c else None,
            'transfer_kit': c.transfer_kit if c else None,
            'waste_toner': c.waste_toner if c else None
        } for t, c in rows]
        return JsonResponse(data, safe=False)
    return render(request, 'inventory/history.html', {
        'printer': printer,
        'rows': rows,
        'page_obj': page_obj,
    })


# ------------------------------ RUNNERS ------------------------------

@login_required
@require_POST
def run_inventory(request, pk):
    queued = _queue_inventory(int(pk))
    return JsonResponse({'success': True, 'queued': queued})


@login_required
@require_POST
def run_inventory_all(request):
    EXECUTOR.submit(inventory_daemon)
    return JsonResponse({'success': True, 'queued': True})


# ------------------------------ APIs ------------------------------

@login_required
def api_printers(request):
    output = []
    for p in Printer.objects.select_related('organization').all():
        last_task = InventoryTask.objects.filter(printer=p, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        ts_ms = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ''
        output.append({
            'id': p.id,
            'ip_address': p.ip_address,
            'serial_number': p.serial_number,
            'mac_address': p.mac_address or '-',
            'model': p.model,
            'snmp_community': p.snmp_community or 'public',
            'organization_id': p.organization_id,
            'organization': p.organization.name if p.organization_id else None,
            'last_match_rule': p.last_match_rule,
            'last_match_rule_label': p.get_last_match_rule_display() if p.last_match_rule else None,
            'bw_a4': getattr(counter, 'bw_a4', '-'),
            'color_a4': getattr(counter, 'color_a4', '-'),
            'bw_a3': getattr(counter, 'bw_a3', '-'),
            'color_a3': getattr(counter, 'color_a3', '-'),
            'total_pages': getattr(counter, 'total_pages', '-'),
            'drum_black': getattr(counter, 'drum_black', '-'),
            'drum_cyan': getattr(counter, 'drum_cyan', '-'),
            'drum_magenta': getattr(counter, 'drum_magenta', '-'),
            'drum_yellow': getattr(counter, 'drum_yellow', '-'),
            'toner_black': getattr(counter, 'toner_black', '-'),
            'toner_cyan': getattr(counter, 'toner_cyan', '-'),
            'toner_magenta': getattr(counter, 'toner_magenta', '-'),
            'toner_yellow': getattr(counter, 'toner_yellow', '-'),
            'fuser_kit': getattr(counter, 'fuser_kit', '-'),
            'transfer_kit': getattr(counter, 'transfer_kit', '-'),
            'waste_toner': getattr(counter, 'waste_toner', '-'),
            'last_date_iso': ts_ms,
        })
    return JsonResponse(output, safe=False)


@login_required
def api_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    last_task = InventoryTask.objects.filter(printer=printer, status='SUCCESS').order_by('-task_timestamp').first()
    counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
    ts_ms = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ''
    data = {
        'id': printer.id,
        'ip_address': printer.ip_address,
        'serial_number': printer.serial_number,
        'mac_address': printer.mac_address or '-',
        'model': printer.model,
        'snmp_community': printer.snmp_community or 'public',
        'organization_id': printer.organization_id,
        'organization': printer.organization.name if printer.organization_id else None,
        'last_match_rule': printer.last_match_rule,
        'last_match_rule_label': printer.get_last_match_rule_display() if printer.last_match_rule else None,
        'bw_a4': getattr(counter, 'bw_a4', '-'),
        'color_a4': getattr(counter, 'color_a4', '-'),
        'bw_a3': getattr(counter, 'bw_a3', '-'),
        'color_a3': getattr(counter, 'color_a3', '-'),
        'total_pages': getattr(counter, 'total_pages', '-'),
        'drum_black': getattr(counter, 'drum_black', '-'),
        'drum_cyan': getattr(counter, 'drum_cyan', '-'),
        'drum_magenta': getattr(counter, 'drum_magenta', '-'),
        'drum_yellow': getattr(counter, 'drum_yellow', '-'),
        'toner_black': getattr(counter, 'toner_black', '-'),
        'toner_cyan': getattr(counter, 'toner_cyan', '-'),
        'toner_magenta': getattr(counter, 'toner_magenta', '-'),
        'toner_yellow': getattr(counter, 'toner_yellow', '-'),
        'fuser_kit': getattr(counter, 'fuser_kit', '-'),
        'transfer_kit': getattr(counter, 'transfer_kit', '-'),
        'waste_toner': getattr(counter, 'waste_toner', '-'),
        'last_date_iso': ts_ms,
    }
    return JsonResponse(data)

@login_required
@require_POST
def api_probe_serial(request):
    """
    Тело: { "ip": "...", "community": "..."? }
    Делает SNMP-опрос, вытаскивает серийник из XML и возвращает его.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректный JSON"}, status=400)

    ip = (payload.get("ip") or "").strip()
    community = (payload.get("community") or "public").strip() or "public"
    if not ip:
        return JsonResponse({"ok": False, "error": "ip не передан"}, status=400)

    # === ВАЖНО: впиши реальную функцию опроса, которая возвращает XML ===
    xml_text = None
    try:
        # вариант 1: если у тебя есть такой хелпер в services
        from .services import get_printer_xml  # <-- замени на реальную
        xml_text = get_printer_xml(ip, community)
    except Exception:
        try:
            # вариант 2: может быть в отдельном модуле _snmp
            from ._snmp import get_printer_xml  # <-- замени на реальную
            xml_text = get_printer_xml(ip, community)
        except Exception:
            xml_text = None

    if not xml_text:
        return JsonResponse({"ok": False, "error": "Не удалось получить XML по SNMP"}, status=400)

    serial = extract_serial_from_xml(xml_text)
    if not serial:
        return JsonResponse({"ok": False, "error": "Серийный номер в XML не найден"}, status=400)

    return JsonResponse({"ok": True, "serial": serial})