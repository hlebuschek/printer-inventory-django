import os
import logging
import threading
import concurrent.futures
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Printer, InventoryTask, PageCounter
from .utils import (
    run_glpi_command,
    send_device_get_request,
    xml_to_json,
    validate_inventory,
    extract_page_counters,
)
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = None
OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'inventory_output')
INV_DIR    = os.path.join(OUTPUT_DIR, 'netinventory')
DISC_DIR   = os.path.join(OUTPUT_DIR, 'netdiscovery')
os.makedirs(INV_DIR, exist_ok=True)
os.makedirs(DISC_DIR, exist_ok=True)


def run_inventory_for_printer(printer_id):
    printer = Printer.objects.get(pk=printer_id)
    channel_layer = get_channel_layer()
    # Оповещение о старте опроса
    async_to_sync(channel_layer.group_send)(
        'inventory_updates',
        {'type': 'inventory_start', 'printer_id': printer.id}
    )

    ip = printer.ip_address
    serial = printer.serial_number
    community = printer.snmp_community
    logging.info(f"Starting inventory for {ip}")

    # HTTP-проверка (не блокирует SNMP)
    if getattr(settings, 'HTTP_CHECK', True):
        ok, err = send_device_get_request(ip)
        if not ok:
            logging.warning(f"HTTP check failed for {ip}: {err}")

    # Определение путей к батникам
    glpi_path = settings.GLPI_PATH
    if glpi_path.lower().endswith('.bat'):
        disc_exe = glpi_path
        inv_exe  = glpi_path.replace('discovery', 'inventory')
    else:
        disc_exe = os.path.join(glpi_path, 'glpi-netdiscovery.bat')
        inv_exe  = os.path.join(glpi_path, 'glpi-netinventory.bat')

    xml_path = os.path.join(INV_DIR, f"{ip}.xml")
    if os.path.exists(xml_path):
        os.remove(xml_path)

    # SNMP discovery
    disc_cmd = (
        f'"{disc_exe}" -i --host {ip} '
        f'--community {community} --save={OUTPUT_DIR} --debug'
    )
    ok, out = run_glpi_command(disc_cmd)
    if not ok:
        InventoryTask.objects.create(
            printer=printer,
            status='FAILED',
            error_message=out,
        )
        return False, out

    # SNMP inventory
    inv_cmd = (
        f'"{inv_exe}" -i --host {ip} '
        f'--community {community} --save={OUTPUT_DIR} --debug'
    )
    ok, out = run_glpi_command(inv_cmd)
    if not ok or not os.path.exists(xml_path):
        msg = out or f"XML missing for {ip}"
        InventoryTask.objects.create(
            printer=printer,
            status='FAILED',
            error_message=msg,
        )
        return False, msg

    # Парсинг XML
    data = xml_to_json(xml_path)
    if not data:
        InventoryTask.objects.create(
            printer=printer,
            status='FAILED',
            error_message='XML parse error',
        )
        return False, 'XML parse error'

    # Валидация
    valid, err = validate_inventory(data, ip, serial)
    if not valid:
        InventoryTask.objects.create(
            printer=printer,
            status='VALIDATION_ERROR',
            error_message=err,
        )
        return False, err

    # Сохранение счётчиков и расходников
    counters = extract_page_counters(data)
    task = InventoryTask.objects.create(printer=printer, status='SUCCESS')
    PageCounter.objects.create(task=task, **counters)

    # Оповещение о завершении опроса
    update_payload = {
        'type': 'inventory_update',
        'printer_id': printer.id,
        'bw_a3': counters.get('bw_a3'),
        'bw_a4': counters.get('bw_a4'),
        'color_a3': counters.get('color_a3'),
        'color_a4': counters.get('color_a4'),
        'total': counters.get('total_pages'),
        # Добавляем уровни расходников
        'drum_black': counters.get('drum_black'),
        'drum_cyan': counters.get('drum_cyan'),
        'drum_magenta': counters.get('drum_magenta'),
        'drum_yellow': counters.get('drum_yellow'),
        'toner_black': counters.get('toner_black'),
        'toner_cyan': counters.get('toner_cyan'),
        'toner_magenta': counters.get('toner_magenta'),
        'toner_yellow': counters.get('toner_yellow'),
        'fuser_kit': counters.get('fuser_kit'),
        'transfer_kit': counters.get('transfer_kit'),
        'waste_toner': counters.get('waste_toner'),
        'timestamp': int(task.task_timestamp.timestamp() * 1000),
    }
    async_to_sync(channel_layer.group_send)(
        'inventory_updates', update_payload
    )

    return True, 'Success'


def inventory_daemon():
    def worker():
        printers = Printer.objects.all()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(run_inventory_for_printer, p.id): p for p in printers}
            for future in concurrent.futures.as_completed(futures):
                printer = futures[future]
                try:
                    ok, msg = future.result()
                    logging.info(f"Inventory for {printer.ip_address}: {'OK' if ok else 'FAIL'} — {msg}")
                except Exception as e:
                    logging.error(f"Error polling {printer.ip_address}: {e}")
    threading.Thread(target=worker, daemon=True).start()


def start_scheduler():
    global scheduler
    if not scheduler:
        scheduler = BackgroundScheduler()
        interval = getattr(settings, 'POLL_INTERVAL_MINUTES', 60)
        scheduler.add_job(inventory_daemon, 'interval', minutes=interval)
        scheduler.start()