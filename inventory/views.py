from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.timezone import localtime
from .models import Printer, InventoryTask, PageCounter
from .forms import PrinterForm
from .services import run_inventory_for_printer, inventory_daemon


def printer_list(request):
    q_ip     = request.GET.get('q_ip', '').strip()
    q_model  = request.GET.get('q_model', '').strip()
    q_serial = request.GET.get('q_serial', '').strip()

    qs = Printer.objects.all()
    if q_ip:
        qs = qs.filter(ip_address__icontains=q_ip)
    if q_model:
        qs = qs.filter(model__icontains=q_model)
    if q_serial:
        qs = qs.filter(serial_number__icontains=q_serial)

    data = []
    for p in qs.order_by('ip_address'):
        last_task = (InventoryTask.objects
                         .filter(printer=p, status='SUCCESS')
                         .order_by('-task_timestamp')
                         .first())
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None

        if last_task:
            ts_ms = int(last_task.task_timestamp.timestamp() * 1000)
            last_date_iso = ts_ms
            last_date = localtime(last_task.task_timestamp).strftime('%d.%m.%Y %H:%M')
        else:
            last_date_iso = ''
            last_date = '—'

        data.append({
            'printer':       p,
            'bw_a4':         counter.bw_a4 if counter else None,
            'color_a4':      counter.color_a4 if counter else None,
            'bw_a3':         counter.bw_a3 if counter else None,
            'color_a3':      counter.color_a3 if counter else None,
            'total':         counter.total_pages if counter else None,
            'last_date':     last_date,
            'last_date_iso': last_date_iso,
        })

    return render(request, 'inventory/index.html', {
        'data':     data,
        'q_ip':     q_ip,
        'q_model':  q_model,
        'q_serial': q_serial,
    })


def add_printer(request):
    form = PrinterForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Принтер добавлен")
        return redirect('printer_list')
    return render(request, 'inventory/add_printer.html', {'form': form})


def edit_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST or None, instance=printer)
    if form.is_valid():
        form.save()
        messages.success(request, "Принтер обновлён")
        return redirect('printer_list')
    return render(request, 'inventory/edit_printer.html', {'form': form})


def delete_printer(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    printer.delete()
    messages.success(request, "Принтер удалён")
    return redirect('printer_list')


def history_view(request, pk):
    printer = get_object_or_404(Printer, pk=pk)
    tasks   = (InventoryTask.objects
                   .filter(printer=printer, status='SUCCESS')
                   .order_by('-task_timestamp'))
    rows    = [(t, PageCounter.objects.filter(task=t).first()) for t in tasks]
    return render(request, 'inventory/history.html', {'printer': printer, 'rows': rows})


def run_inventory(request, pk):
    ok, msg = run_inventory_for_printer(pk)
    if ok:
        last_task = (InventoryTask.objects
                         .filter(printer_id=pk, status='SUCCESS')
                         .order_by('-task_timestamp')
                         .first())
        counter = PageCounter.objects.filter(task=last_task).first()
        ts_ms = int(last_task.task_timestamp.timestamp() * 1000)
        payload = {
            'success':  True,
            'message':  msg,
            'bw_a4':    counter.bw_a4,
            'color_a4': counter.color_a4,
            'bw_a3':    counter.bw_a3,
            'color_a3': counter.color_a3,
            'total':    counter.total_pages,
            'timestamp': ts_ms,
        }
    else:
        payload = {'success': False, 'message': msg}
    return JsonResponse(payload)


def run_inventory_all(request):
    inventory_daemon()
    messages.success(request, "Запущен массовый опрос")
    return redirect('printer_list')


def api_printers(request):
    # остался без изменений, возвращает last_date_iso в JSON
    from django.http import JsonResponse
    output = []
    for p in Printer.objects.all():
        last_task = (InventoryTask.objects
                         .filter(printer=p, status='SUCCESS')
                         .order_by('-task_timestamp')
                         .first())
        counter = PageCounter.objects.filter(task=last_task).first() if last_task else None
        ts_ms = int(last_task.task_timestamp.timestamp() * 1000) if last_task else ''
        output.append({
            'ip_address':    p.ip_address,
            'serial_number': p.serial_number,
            'model':         p.model,
            'bw_a4':         getattr(counter, 'bw_a4', '-'),
            'color_a4':      getattr(counter, 'color_a4', '-'),
            'bw_a3':         getattr(counter, 'bw_a3', '-'),
            'color_a3':      getattr(counter, 'color_a3', '-'),
            'total_pages':   getattr(counter, 'total_pages', '-'),
            'last_date_iso': ts_ms,
        })
    return JsonResponse(output, safe=False)