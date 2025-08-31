import os
import logging
import threading
import concurrent.futures
import re

from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apscheduler.schedulers.background import BackgroundScheduler

from .models import Printer, InventoryTask, PageCounter
from .utils import (
    run_glpi_command,
    send_device_get_request,
    xml_to_json,
    validate_inventory,
    extract_page_counters,
    extract_mac_address,
)

scheduler = None
OUTPUT_DIR = os.path.join(settings.BASE_DIR, 'inventory_output')
INV_DIR = os.path.join(OUTPUT_DIR, 'netinventory')
DISC_DIR = os.path.join(OUTPUT_DIR, 'netdiscovery')
os.makedirs(INV_DIR, exist_ok=True)
os.makedirs(DISC_DIR, exist_ok=True)


def run_inventory_for_printer(printer_id, xml_path=None):
    try:
        printer = Printer.objects.get(pk=printer_id)
    except Printer.DoesNotExist:
        return False, f"Printer {printer_id} not found"

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'inventory_updates',
        {'type': 'inventory_start', 'printer_id': printer.id}
    )

    ip = printer.ip_address
    serial = printer.serial_number
    community = printer.snmp_community
    logging.info(f"Starting inventory for {ip}")

    # Если xml_path не передан, выполняем полный опрос через GLPI
    if not xml_path:
        # HTTP-проверка доступности веб-интерфейса принтера (не критично)
        if getattr(settings, 'HTTP_CHECK', True):
            ok, err = send_device_get_request(ip)
            if not ok:
                logging.warning(f"HTTP check failed for {ip}: {err}")

        # Определение путей к bat-скриптам GLPI
        glpi_path = settings.GLPI_PATH
        if glpi_path.lower().endswith('.bat'):
            disc_exe = glpi_path
            inv_exe = glpi_path.replace('discovery', 'inventory')
        else:
            disc_exe = os.path.join(glpi_path, 'glpi-netdiscovery.bat')
            inv_exe = os.path.join(glpi_path, 'glpi-netinventory.bat')

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

    # Проверка наличия счётчиков
    page_counters = data.get('CONTENT', {}).get('DEVICE', {}).get('PAGECOUNTERS', {})
    if not page_counters or not any(page_counters.get(tag) for tag in ['TOTAL', 'BW_A3', 'BW_A4', 'COLOR_A3', 'COLOR_A4']):
        logging.warning(f"No valid page counters found in XML for {ip}")
        InventoryTask.objects.create(
            printer=printer,
            status='FAILED',
            error_message='No valid page counters in XML',
        )
        async_to_sync(channel_layer.group_send)(
            'inventory_updates',
            {
                'type': 'inventory_update',
                'printer_id': printer.id,
                'status': 'FAILED',
                'message': 'No valid page counters in XML'
            }
        )
        return False, 'No valid page counters in XML'

    # Обновление MAC-адреса, если не установлен
    mac_address = extract_mac_address(data)
    if mac_address and not printer.mac_address:
        printer.mac_address = mac_address
        printer.save(update_fields=['mac_address'])

    # Валидация и определение правила сопоставления
    valid, err, rule = validate_inventory(data, ip, serial, printer.mac_address)
    if not valid:
        InventoryTask.objects.create(
            printer=printer,
            status='VALIDATION_ERROR',
            error_message=err,
        )
        return False, err

    # Сохранение счётчиков и расходников
    counters = extract_page_counters(data)
    task = InventoryTask.objects.create(
        printer=printer,
        status='SUCCESS',
        match_rule=rule
    )
    PageCounter.objects.create(task=task, **counters)

    # Обновим «последнее правило» на принтере (для UI/фильтров)
    if rule:
        printer.last_match_rule = rule
        printer.save(update_fields=['last_match_rule'])

    # Оповещение о завершении опроса
    update_payload = {
        'type': 'inventory_update',
        'printer_id': printer.id,
        'status': 'SUCCESS',
        'match_rule': rule,
        'bw_a3': counters.get('bw_a3'),
        'bw_a4': counters.get('bw_a4'),
        'color_a3': counters.get('color_a3'),
        'color_a4': counters.get('color_a4'),
        'total': counters.get('total_pages'),
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
    async_to_sync(channel_layer.group_send)('inventory_updates', update_payload)

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

def extract_serial_from_xml(xml_text: str) -> str | None:
    """
    Достаём серийник из SNMP-XML.
    1) через xml_to_json() — ищем ключи, содержащие 'serial' или OID prtGeneralSerialNumber
    2) фоллбек: прямой regex по XML
    """
    if not xml_text:
        return None

    try:
        data = xml_to_json(xml_text)  # уже есть у тебя
    except Exception:
        data = None

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                yield from walk(v, f"{path}[{i}]")
        else:
            yield path, ("" if obj is None else str(obj))

    candidates = []
    if isinstance(data, (dict, list)):
        for path, val in walk(data):
            k = path.lower()
            if ("serial" in k) or ("1.3.6.1.2.1.43.5.1.1.17" in k):  # prtGeneralSerialNumber
                v = (val or "").strip()
                if v and len(v) >= 5 and v.lower() not in {"none", "n/a"}:
                    candidates.append(v)

    if candidates:
        # берём самый «осмысленный» (чаще всего самый длинный)
        return max(candidates, key=len)

    # грубый фоллбек — на случай неожиданных форматов:
    m = re.search(r"(?i)<[^>]*serial[^>]*>([^<]{5,})</", xml_text)
    if m:
        return m.group(1).strip()

    return None