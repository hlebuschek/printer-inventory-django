from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

import openpyxl
from openpyxl.utils import get_column_letter

from .models import Printer, InventoryTask, PageCounter
from .forms import PrinterForm
from .services import run_inventory_for_printer, inventory_daemon

@login_required
def printer_list(request):
    q_ip = request.GET.get('q_ip', '').strip()
    q_model = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()
    per_page = request.GET.get('per_page', '100').strip()

    try:
        per_page = int(per_page)
        if per_page not in [10, 25, 50, 100, 250, 500, 1000, 2000, 5000]:
            per_page = 100
    except ValueError:
        per_page = 100

    qs = Printer.objects.all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    qs = qs.order_by('ip_address')
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    data = []
    for p in page_obj:
        last_task = InventoryTask.objects.filter(printer=p, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None

        if last_task and counter:
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
        'per_page': per_page,
        'per_page_options': per_page_options,
    })

@login_required
def export_excel(request):
    q_ip = request.GET.get('q_ip', '').strip()
    q_model = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()

    qs = Printer.objects.all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Printers'

    headers = [
        'IP-адрес', 'Серийный номер', 'MAC-адрес', 'Модель',
        'ЧБ A4', 'Цвет A4', 'ЧБ A3', 'Цвет A3', 'Всего',
        'Дата последнего опроса'
    ]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = openpyxl.styles.Font(bold=True)

    for row_idx, p in enumerate(qs.order_by('ip_address'), start=2):
        last_task = InventoryTask.objects.filter(printer=p, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        dt = localtime(last_task.task_timestamp).strftime('%d.%m.%Y %H:%M') if last_task else ''

        serial_val = int(p.serial_number) if p.serial_number.isdigit() else p.serial_number
        values = [
            p.ip_address,
            serial_val,
            p.mac_address or '',
            p.model,
            getattr(counter, 'bw_a4', ''),
            getattr(counter, 'color_a4', ''),
            getattr(counter, 'bw_a3', ''),
            getattr(counter, 'color_a3', ''),
            getattr(counter, 'total_pages', ''),
            dt,
        ]
        for col_idx, val in enumerate(values, 1):
            ws.cell(row=row_idx, column=col_idx, value=val)

    for i in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].auto_size = True

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="printers.xlsx"'
    wb.save(response)
    return response

@login_required
def export_amb(request):
    if request.method == 'POST' and request.FILES.get('template'):
        wb = openpyxl.load_workbook(request.FILES['template'])
        ws = wb.active

        header_row = next(
            (r for r in range(1, 11)
             if any(str(cell.value).strip().lower() == 'серийный номер оборудования'
                    for cell in ws[r])),
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
            'serial': lambda k: 'серийный номер оборудования' in k,
            'a4_bw': lambda k: 'ч/б' in k and 'конец периода' in k and 'а4' in k,
            'a4_color': lambda k: 'цветные' in k and 'конец периода' in k and 'а4' in k,
            'a3_bw': lambda k: 'ч/б' in k and 'конец периода' in k and 'а3' in k,
            'a3_color': lambda k: 'цветные' in k and 'конец периода' in k and 'а3' in k,
        }

        cols = {}
        for internal, cond in lookup.items():
            for key, idx in headers.items():
                if cond(key):
                    cols[internal] = idx
                    break
            if internal not in cols:
                return HttpResponse(f"Колонка для '{internal}' не найдена.", status=400)

        date_col = ws.max_column + 1
        ws.cell(row=header_row, column=date_col, value='Дата опроса')

        for row in range(header_row + 1, ws.max_row + 1):
            raw = ws.cell(row=row, column=cols['serial']).value
            serial = str(raw).strip() if raw is not None else ''
            if not serial:
                continue

            task = InventoryTask.objects.filter(printer__serial_number=serial, status='SUCCESS').order_by('-task_timestamp').first()
            if not task:
                continue

            counter = PageCounter.objects.filter(task=task).first()
            if not counter:
                continue

            bw_a4_val = counter.bw_a4 or 0
            color_a4_val = counter.color_a4 or 0
            bw_a3_val = counter.bw_a3 or 0
            color_a3_val = counter.color_a3 or 0

            ws.cell(row=row, column=cols['a4_bw'], value=bw_a4_val)
            ws.cell(row=row, column=cols['a4_color'], value=color_a4_val)
            ws.cell(row=row, column=cols['a3_bw'], value=bw_a3_val)
            ws.cell(row=row, column=cols['a3_color'], value=color_a3_val)

            dt = localtime(task.task_timestamp).strftime('%d.%m.%Y %H:%M')
            ws.cell(row=row, column=date_col, value=dt)

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="amb_report.xlsx"'
        wb.save(response)
        wb.close()
        return response

    return render(request, 'inventory/export_amb.html')

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
    if form.is_valid():
        form.save()
        messages.success(request, "Принтер обновлён")
        return redirect('printer_list')
    return render(request, 'inventory/edit_printer.html', {'form': form})

@login_required
def delete_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    printer.delete()
    messages.success(request, "Принтер удалён")
    return redirect('printer_list')

@login_required
def history_view(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    tasks = InventoryTask.objects.filter(printer=printer, status='SUCCESS').order_by('-task_timestamp')
    paginator = Paginator(tasks, 50)
    page_obj = paginator.get_page(request.GET.get('page'))
    rows = [(t, PageCounter.objects.filter(task=t).first()) for t in page_obj]
    return render(request, 'inventory/history.html', {
        'printer': printer,
        'rows': rows,
        'page_obj': page_obj,
    })

@login_required
def run_inventory(request, pk):
    ok, msg = run_inventory_for_printer(pk)
    if ok:
        last_task = InventoryTask.objects.filter(printer_id=pk, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first()
        ts_ms = int(last_task.task_timestamp.timestamp() * 1000)
        payload = {
            'success': True,
            'message': msg,
            'bw_a4': counter.bw_a4,
            'color_a4': counter.color_a4,
            'bw_a3': counter.bw_a3,
            'color_a3': counter.color_a3,
            'total': counter.total_pages,
            'drum_black': counter.drum_black,
            'drum_cyan': counter.drum_cyan,
            'drum_magenta': counter.drum_magenta,
            'drum_yellow': counter.drum_yellow,
            'toner_black': counter.toner_black,
            'toner_cyan': counter.toner_cyan,
            'toner_magenta': counter.toner_magenta,
            'toner_yellow': counter.toner_yellow,
            'fuser_kit': counter.fuser_kit,
            'transfer_kit': counter.transfer_kit,
            'waste_toner': counter.waste_toner,
            'timestamp': ts_ms,
        }
    else:
        payload = {'success': False, 'message': msg}
    return JsonResponse(payload)

@login_required
def run_inventory_all(request):
    inventory_daemon()
    messages.success(request, "Запущен массовый опрос")
    return redirect('printer_list')

@login_required
def api_printers(request):
    output = []
    for p in Printer.objects.all():
        last_task = InventoryTask.objects.filter(printer=p, status='SUCCESS').order_by('-task_timestamp').first()
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        ts_ms = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ''
        output.append({
            'ip_address': p.ip_address,
            'serial_number': p.serial_number,
            'mac_address': p.mac_address or '-',
            'model': p.model,
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