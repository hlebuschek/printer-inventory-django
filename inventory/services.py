# inventory/services.py
import os
import logging
import threading
import concurrent.futures
from typing import Optional, Tuple, Union
import xml.etree.ElementTree as ET

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

# === Пути вывода GLPI Agent ===
OUTPUT_DIR = os.path.join(settings.BASE_DIR, "inventory_output")
INV_DIR = os.path.join(OUTPUT_DIR, "netinventory")
DISC_DIR = os.path.join(OUTPUT_DIR, "netdiscovery")
os.makedirs(INV_DIR, exist_ok=True)
os.makedirs(DISC_DIR, exist_ok=True)

scheduler: Optional[BackgroundScheduler] = None


# ──────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ
# ──────────────────────────────────────────────────────────────────────────────
def _get_glpi_paths() -> Tuple[str, str]:
    """
    Возвращает пути к glpi-netdiscovery.bat и glpi-netinventory.bat,
    учитывая вариант, когда настроен путь к одному .bat.
    """
    glpi_path = getattr(settings, "GLPI_PATH", "")
    if not glpi_path:
        raise RuntimeError("GLPI_PATH не задан в настройках")

    if glpi_path.lower().endswith(".bat"):
        disc_exe = glpi_path
        inv_exe = glpi_path.replace("discovery", "inventory")
    else:
        disc_exe = os.path.join(glpi_path, "glpi-netdiscovery.bat")
        inv_exe = os.path.join(glpi_path, "glpi-netinventory.bat")

    return disc_exe, inv_exe


def _possible_xml_paths(ip: str, prefer: str) -> Tuple[str, ...]:
    """
    Список кандидатных путей к XML для данного IP.
    prefer='disc' -> ставим в начало DISC_DIR, иначе INV_DIR.
    """
    disc_xml = os.path.join(DISC_DIR, f"{ip}.xml")
    inv_xml = os.path.join(INV_DIR, f"{ip}.xml")
    direct = os.path.join(OUTPUT_DIR, f"{ip}.xml")  # иногда агент кладёт напрямую в save-dir
    if prefer == "disc":
        return (disc_xml, direct, inv_xml)
    return (inv_xml, direct, disc_xml)


def _cleanup_xml(ip: str):
    """Удаляет старые XML по всем местам для IP, чтобы не ловить мусор."""
    for p in _possible_xml_paths(ip, prefer="inv"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# DISCOVERY ДЛЯ КНОПКИ НА /printers/add/  → только вынуть <SERIAL>
# ──────────────────────────────────────────────────────────────────────────────
def run_discovery_for_ip(ip: str, community: str = "public") -> Tuple[bool, str]:
    """
    Запускает glpi-netdiscovery для IP и возвращает (ok, xml_path | error).
    XML ожидаем в DISC_DIR/{ip}.xml (или, на крайняк, в OUTPUT_DIR).
    """
    disc_exe, _ = _get_glpi_paths()

    # чистим возможные старые файлы
    for p in _possible_xml_paths(ip, prefer="disc"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    cmd = (
        f'"{disc_exe}" --host {ip} -i '
        f'--community {community} '
        f'--save="{OUTPUT_DIR}" --debug'
    )
    ok, out = run_glpi_command(cmd)
    if not ok:
        return False, out or "netdiscovery failed"

    # ищем XML
    for candidate in _possible_xml_paths(ip, prefer="disc"):
        if os.path.exists(candidate):
            return True, candidate

    return False, f"XML not found for {ip} (save={OUTPUT_DIR})"


def extract_serial_from_xml(xml_input: Union[str, os.PathLike, bytes]) -> Optional[str]:
    """
    Возвращает содержимое первого тега <SERIAL> из XML.
    Поддерживает: путь к файлу, байты XML или строку XML.
    Игнорирует namespace и регистр тега.
    """
    try:
        # Путь к файлу
        if isinstance(xml_input, (str, os.PathLike)) and os.path.exists(str(xml_input)):
            for _, elem in ET.iterparse(str(xml_input), events=("end",)):
                tag = str(elem.tag).split("}", 1)[-1]  # отрезаем namespace
                if tag.upper() == "SERIAL":
                    val = (elem.text or "").strip()
                    return val or None
            return None

        # Прямой XML-контент
        root = ET.fromstring(xml_input if isinstance(xml_input, (str, bytes)) else str(xml_input))
        for elem in root.iter():
            tag = str(elem.tag).split("}", 1)[-1]
            if tag.upper() == "SERIAL":
                val = (elem.text or "").strip()
                return val or None
        return None
    except ET.ParseError:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# ПОЛНЫЙ ИНВЕНТАРЬ (задачи, счётчики, расходники) — используется демоном
# ──────────────────────────────────────────────────────────────────────────────
def run_inventory_for_printer(printer_id: int, xml_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Полный цикл: (опционально) HTTP-check → discovery → inventory → парсинг → валидация → сохранение.
    Если xml_path задан — пропускаем discovery/inventory и сразу парсим.
    """
    try:
        printer = Printer.objects.get(pk=printer_id)
    except Printer.DoesNotExist:
        return False, f"Printer {printer_id} not found"

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "inventory_updates",
        {"type": "inventory_start", "printer_id": printer.id},
    )

    ip = printer.ip_address
    serial = printer.serial_number
    community = printer.snmp_community or "public"
    logging.info(f"Starting inventory for {ip}")

    # Если xml_path не передан — запускаем GLPI discovery + inventory
    if not xml_path:
        if getattr(settings, "HTTP_CHECK", True):
            ok_check, err = send_device_get_request(ip)
            if not ok_check:
                logging.warning(f"HTTP check failed for {ip}: {err}")

        disc_exe, inv_exe = _get_glpi_paths()

        # ожидаемый итоговый XML после inventory
        final_xml = _possible_xml_paths(ip, prefer="inv")[0]
        _cleanup_xml(ip)

        # 1) Discovery
        disc_cmd = (
            f'"{disc_exe}" -i --host {ip} '
            f'--community {community} --save="{OUTPUT_DIR}" --debug'
        )
        ok, out = run_glpi_command(disc_cmd)
        if not ok:
            InventoryTask.objects.create(
                printer=printer, status="FAILED", error_message=out
            )
            return False, out

        # 2) Inventory
        inv_cmd = (
            f'"{inv_exe}" -i --host {ip} '
            f'--community {community} --save="{OUTPUT_DIR}" --debug'
        )
        ok, out = run_glpi_command(inv_cmd)
        if not ok:
            InventoryTask.objects.create(
                printer=printer, status="FAILED", error_message=out
            )
            return False, out or "netinventory failed"

        # 3) Проверяем наличие XML
        xml_candidates = _possible_xml_paths(ip, prefer="inv")
        xml_path = None
        for candidate in xml_candidates:
            if os.path.exists(candidate):
                xml_path = candidate
                break

        if not xml_path:
            msg = f"XML missing for {ip} (expected: {final_xml})"
            InventoryTask.objects.create(printer=printer, status="FAILED", error_message=msg)
            return False, msg

    # ── Парсинг XML ───────────────────────────────────────────────────────────
    data = xml_to_json(xml_path)
    if not data:
        InventoryTask.objects.create(
            printer=printer, status="FAILED", error_message="XML parse error"
        )
        return False, "XML parse error"

    # ── Проверка наличия счётчиков ───────────────────────────────────────────
    page_counters = data.get("CONTENT", {}).get("DEVICE", {}).get("PAGECOUNTERS", {})
    if not page_counters or not any(
        page_counters.get(tag) for tag in ["TOTAL", "BW_A3", "BW_A4", "COLOR_A3", "COLOR_A4"]
    ):
        logging.warning(f"No valid page counters found in XML for {ip}")
        InventoryTask.objects.create(
            printer=printer, status="FAILED", error_message="No valid page counters in XML"
        )
        async_to_sync(channel_layer.group_send)(
            "inventory_updates",
            {
                "type": "inventory_update",
                "printer_id": printer.id,
                "status": "FAILED",
                "message": "No valid page counters in XML",
            },
        )
        return False, "No valid page counters in XML"

    # ── Обновление MAC ───────────────────────────────────────────────────────
    mac_address = extract_mac_address(data)
    if mac_address and not printer.mac_address:
        printer.mac_address = mac_address
        printer.save(update_fields=["mac_address"])

    # ── Валидация и сопоставление ────────────────────────────────────────────
    valid, err, rule = validate_inventory(data, ip, serial, printer.mac_address)
    if not valid:
        InventoryTask.objects.create(
            printer=printer, status="VALIDATION_ERROR", error_message=err
        )
        return False, err

    # ── Сохранение счётчиков/расходников ─────────────────────────────────────
    counters = extract_page_counters(data)
    task = InventoryTask.objects.create(printer=printer, status="SUCCESS", match_rule=rule)
    PageCounter.objects.create(task=task, **counters)

    # Обновим «последнее правило»
    if rule:
        printer.last_match_rule = rule
        printer.save(update_fields=["last_match_rule"])

    # ── WS-уведомление ───────────────────────────────────────────────────────
    update_payload = {
        "type": "inventory_update",
        "printer_id": printer.id,
        "status": "SUCCESS",
        "match_rule": rule,
        "bw_a3": counters.get("bw_a3"),
        "bw_a4": counters.get("bw_a4"),
        "color_a3": counters.get("color_a3"),
        "color_a4": counters.get("color_a4"),
        "total": counters.get("total_pages"),
        "drum_black": counters.get("drum_black"),
        "drum_cyan": counters.get("drum_cyan"),
        "drum_magenta": counters.get("drum_magenta"),
        "drum_yellow": counters.get("drum_yellow"),
        "toner_black": counters.get("toner_black"),
        "toner_cyan": counters.get("toner_cyan"),
        "toner_magenta": counters.get("toner_magenta"),
        "toner_yellow": counters.get("toner_yellow"),
        "fuser_kit": counters.get("fuser_kit"),
        "transfer_kit": counters.get("transfer_kit"),
        "waste_toner": counters.get("waste_toner"),
        "timestamp": int(task.task_timestamp.timestamp() * 1000),
    }
    async_to_sync(channel_layer.group_send)("inventory_updates", update_payload)

    return True, "Success"


# ──────────────────────────────────────────────────────────────────────────────
# ФОНОВЫЕ ЗАДАЧИ
# ──────────────────────────────────────────────────────────────────────────────
def inventory_daemon():
    """Опрос всех принтеров параллельно пулом потоков."""
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
    """
    Стартует APScheduler с периодическим запуском демона опроса.
    Для dev-сервера Django возможен двойной запуск — контролируйте через переменные окружения при необходимости.
    """
    global scheduler
    if scheduler:
        return
    scheduler = BackgroundScheduler()
    interval = int(getattr(settings, "POLL_INTERVAL_MINUTES", 60))
    scheduler.add_job(inventory_daemon, "interval", minutes=interval)
    scheduler.start()
