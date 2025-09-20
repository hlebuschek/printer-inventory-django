import os
import logging
import platform
import threading
import concurrent.futures
from typing import Optional, Tuple, Union

import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.cache import cache, caches
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Printer, InventoryTask, PageCounter
from .utils import (
    run_glpi_command,
    send_device_get_request,
    xml_to_json,
    validate_inventory,
    extract_page_counters,
    extract_mac_address,
)

# ──────────────────────────────────────────────────────────────────────────────
# ПУТИ ВЫВОДА GLPI
# ──────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR = os.path.join(settings.BASE_DIR, "inventory_output")
INV_DIR = os.path.join(OUTPUT_DIR, "netinventory")
DISC_DIR = os.path.join(OUTPUT_DIR, "netdiscovery")
os.makedirs(INV_DIR, exist_ok=True)
os.makedirs(DISC_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Именованный кэш для inventory, если есть
inventory_cache = caches['inventory'] if hasattr(settings, 'CACHES') and 'inventory' in settings.CACHES else cache

# Платформа
PLATFORM = platform.system().lower()

# ──────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ
# ──────────────────────────────────────────────────────────────────────────────

def _get_glpi_executable_name(tool: str) -> str:
    """
    Возвращает имя бинаря для ОС.
    tool: 'netdiscovery' | 'netinventory'
    """
    if PLATFORM == 'windows':
        return f"glpi-{tool}.bat"
    return f"glpi-{tool}"

def _get_glpi_paths() -> Tuple[str, str]:
    """
    Возвращает абсолютные пути к glpi-netdiscovery и glpi-netinventory.
    Учитывает:
      - если GLPI_PATH указывает на директорию — ищем внутри
      - если указывает прямо на один из бинарей — второй строим заменой
    """
    glpi_path = getattr(settings, "GLPI_PATH", "")
    if not glpi_path:
        raise RuntimeError("GLPI_PATH не задан в настройках")

    # Если указан полный путь к исполняемому
    base = glpi_path.replace("\\", "/")
    if any(key in base for key in ("netdiscovery", "netinventory")):
        if "netdiscovery" in base:
            disc_exe = glpi_path
            inv_exe = glpi_path.replace("netdiscovery", "netinventory")
        else:
            inv_exe = glpi_path
            disc_exe = glpi_path.replace("netinventory", "netdiscovery")
    else:
        # Каталог установки — собираем имена
        disc_exe = os.path.join(glpi_path, _get_glpi_executable_name("netdiscovery"))
        inv_exe = os.path.join(glpi_path, _get_glpi_executable_name("netinventory"))

    return disc_exe, inv_exe

def _build_glpi_command(executable: str, ip: str, community: str = "public", extra_args: str = "") -> str:
    """
    Собирает команду запуска GLPI с учётом ОС, sudo и пользователя.
    Возвращает строку (Windows) или безопасно разбираемую строку (Linux/macOS).
    """
    base_cmd = f'"{executable}" --host {ip} -i --community {community} --save="{OUTPUT_DIR}" --debug'
    if extra_args:
        base_cmd += f" {extra_args}"

    if PLATFORM in ('linux', 'darwin'):
        use_sudo = getattr(settings, 'GLPI_USE_SUDO', False)
        glpi_user = getattr(settings, 'GLPI_USER', '')
        # Порядок: sudo -u user <cmd>
        if glpi_user:
            base_cmd = f"sudo -u {glpi_user} {base_cmd}" if use_sudo else f"sudo -n -u {glpi_user} {base_cmd}" if os.geteuid() == 0 else base_cmd
        elif use_sudo:
            base_cmd = f"sudo {base_cmd}"
    # На Windows ничего дополнительно не требуется
    return base_cmd

def _validate_glpi_installation() -> Tuple[bool, str]:
    """
    Проверяет наличие и исполнимость glpi-netdiscovery / glpi-netinventory.
    """
    try:
        disc_exe, inv_exe = _get_glpi_paths()

        if not os.path.exists(disc_exe):
            return False, f"glpi-netdiscovery не найден: {disc_exe}"
        if not os.path.exists(inv_exe):
            return False, f"glpi-netinventory не найден: {inv_exe}"

        if PLATFORM != 'windows':
            if not os.access(disc_exe, os.X_OK):
                return False, f"glpi-netdiscovery не исполняемый: {disc_exe}"
            if not os.access(inv_exe, os.X_OK):
                return False, f"glpi-netinventory не исполняемый: {inv_exe}"

        return True, "GLPI Agent найден и доступен"
    except Exception as e:
        return False, f"Ошибка проверки GLPI Agent: {e}"

def _possible_xml_paths(ip: str, prefer: str) -> Tuple[str, ...]:
    """
    Кандидатные пути к XML для IP; prefer='disc' ставит discovery в начало.
    """
    disc_xml = os.path.join(DISC_DIR, f"{ip}.xml")
    inv_xml = os.path.join(INV_DIR, f"{ip}.xml")
    direct = os.path.join(OUTPUT_DIR, f"{ip}.xml")
    if prefer == "disc":
        return (disc_xml, direct, inv_xml)
    return (inv_xml, direct, disc_xml)

def _cleanup_xml(ip: str):
    """Удаляет старые XML по всем местам для IP."""
    for p in _possible_xml_paths(ip, prefer="inv"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

def get_printer_cache_key(printer_id: int) -> str:
    return f'printer_{printer_id}'

def get_last_inventory_cache_key(printer_id: int) -> str:
    return f'last_inventory_{printer_id}'

def cache_printer_data(printer: Printer, timeout: int = 3600):
    data = {
        'id': printer.id,
        'ip_address': printer.ip_address,
        'serial_number': printer.serial_number,
        'model': printer.model,
        'mac_address': printer.mac_address,
        'organization_id': printer.organization_id,
        'organization_name': printer.organization.name if printer.organization else None,
        'last_match_rule': printer.last_match_rule,
        'last_updated': printer.last_updated.isoformat() if getattr(printer, "last_updated", None) else None,
    }
    inventory_cache.set(get_printer_cache_key(printer.id), data, timeout=timeout)
    return data

def get_cached_printer_data(printer_id: int) -> Optional[dict]:
    return inventory_cache.get(get_printer_cache_key(printer_id))

def invalidate_printer_cache(printer_id: int):
    inventory_cache.delete(get_printer_cache_key(printer_id))
    inventory_cache.delete(get_last_inventory_cache_key(printer_id))

# ──────────────────────────────────────────────────────────────────────────────
# DISCOVERY ДЛЯ КНОПКИ /printers/add/
# ──────────────────────────────────────────────────────────────────────────────

def run_discovery_for_ip(ip: str, community: str = "public") -> Tuple[bool, str]:
    """
    Запускает glpi-netdiscovery для IP и возвращает (ok, xml_path | error).
    Результат кэшируется: 30 минут при успехе, 5 минут при ошибке.
    """
    cache_key = f'discovery_result_{ip}_{community}'
    cached_result = inventory_cache.get(cache_key)
    if cached_result:
        logger.info(f"Using cached discovery result for {ip}")
        return cached_result['success'], cached_result['data']

    disc_exe, _ = _get_glpi_paths()

    # чистим старые файлы
    for p in _possible_xml_paths(ip, prefer="disc"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    cmd = _build_glpi_command(disc_exe, ip, community)

    ok, out = run_glpi_command(cmd)
    if not ok:
        result = {'success': False, 'data': out or "netdiscovery failed"}
        inventory_cache.set(cache_key, result, timeout=300)
        return False, result['data']

    # ищем XML
    for candidate in _possible_xml_paths(ip, prefer="disc"):
        if os.path.exists(candidate):
            result = {'success': True, 'data': candidate}
            inventory_cache.set(cache_key, result, timeout=1800)
            return True, candidate

    result = {'success': False, 'data': f"XML not found for {ip} (save={OUTPUT_DIR})"}
    inventory_cache.set(cache_key, result, timeout=300)
    return False, result['data']

def extract_serial_from_xml(xml_input: Union[str, os.PathLike, bytes]) -> Optional[str]:
    """
    Возвращает содержимое первого тега <SERIAL>.
    Поддерживает путь к файлу, строку или bytes. Для файла кэш по пути+mtime.
    """
    if isinstance(xml_input, (str, os.PathLike)) and os.path.exists(str(xml_input)):
        file_path = str(xml_input)
        file_mtime = os.path.getmtime(file_path)
        cache_key = f'xml_serial_{hash(file_path)}_{file_mtime}'
        cached_serial = inventory_cache.get(cache_key)
        if cached_serial is not None:
            return cached_serial
        try:
            for _, elem in ET.iterparse(file_path, events=("end",)):
                tag = str(elem.tag).split("}", 1)[-1]
                if tag.upper() == "SERIAL":
                    val = (elem.text or "").strip()
                    serial = val or None
                    inventory_cache.set(cache_key, serial, timeout=3600)
                    return serial
            inventory_cache.set(cache_key, None, timeout=3600)
            return None
        except ET.ParseError:
            inventory_cache.set(cache_key, None, timeout=300)
            return None

    try:
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
# ПОЛНЫЙ ИНВЕНТАРЬ
# ──────────────────────────────────────────────────────────────────────────────

def run_inventory_for_printer(printer_id: int, xml_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Полный цикл: (опционально) HTTP-check → discovery → inventory → парсинг → валидация → сохранение.
    Если xml_path задан — discovery/inventory пропускаются.
    Использует кэш для блокировки и результатов.
    """
    start_time = timezone.now()
    printer = None

    # Блокировка (10 минут)
    lock_key = f'inventory_lock_{printer_id}'
    if inventory_cache.get(lock_key):
        logger.warning(f"Inventory already running for printer {printer_id}")
        return False, "Inventory already running"
    inventory_cache.set(lock_key, True, timeout=600)

    try:
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer {printer_id} not found")
            return False, f"Printer {printer_id} not found"

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "inventory_updates",
            {"type": "inventory_start", "printer_id": printer.id},
        )

        ip = printer.ip_address
        serial = printer.serial_number
        community = getattr(printer, "snmp_community", None) or "public"
        logger.info(f"Starting inventory for {ip} (ID: {printer_id})")

        if not xml_path:
            # Проверяем HTTP доступность (опционально)
            if getattr(settings, "HTTP_CHECK", True):
                ok_check, err = send_device_get_request(ip)
                if not ok_check:
                    logger.warning(f"HTTP check failed for {ip}: {err}")

            # Проверяем агент GLPI
            glpi_ok, glpi_msg = _validate_glpi_installation()
            if not glpi_ok:
                InventoryTask.objects.create(
                    printer=printer, status="FAILED", error_message=glpi_msg
                )
                return False, glpi_msg

            disc_exe, inv_exe = _get_glpi_paths()

            final_xml = _possible_xml_paths(ip, prefer="inv")[0]
            _cleanup_xml(ip)

            # 1) Discovery
            disc_cmd = _build_glpi_command(disc_exe, ip, community)
            ok, out = run_glpi_command(disc_cmd)
            if not ok:
                error_msg = f"Discovery failed: {out}"
                InventoryTask.objects.create(
                    printer=printer, status="FAILED", error_message=error_msg
                )
                logger.error(f"Discovery failed for {ip}: {out}")
                return False, error_msg

            # 2) Inventory
            inv_cmd = _build_glpi_command(inv_exe, ip, community)
            ok, out = run_glpi_command(inv_cmd)
            if not ok:
                error_msg = f"Inventory failed: {out}"
                InventoryTask.objects.create(
                    printer=printer, status="FAILED", error_message=error_msg
                )
                logger.error(f"Inventory failed for {ip}: {out}")
                return False, error_msg

            # 3) Поиск XML
            xml_candidates = _possible_xml_paths(ip, prefer="inv")
            xml_path = None
            for candidate in xml_candidates:
                if os.path.exists(candidate):
                    xml_path = candidate
                    break

            if not xml_path:
                msg = f"XML missing for {ip} (expected: {final_xml})"
                InventoryTask.objects.create(printer=printer, status="FAILED", error_message=msg)
                logger.error(msg)
                return False, msg

        # Парсинг XML
        data = xml_to_json(xml_path)
        if not data:
            error_msg = "XML parse error"
            InventoryTask.objects.create(
                printer=printer, status="FAILED", error_message=error_msg
            )
            logger.error(f"XML parse error for {ip}")
            return False, error_msg

        # Проверка счётчиков
        page_counters = data.get("CONTENT", {}).get("DEVICE", {}).get("PAGECOUNTERS", {})
        if not page_counters or not any(
            page_counters.get(tag) for tag in ["TOTAL", "BW_A3", "BW_A4", "COLOR_A3", "COLOR_A4", "COLOR"]
        ):
            error_msg = "No valid page counters in XML"
            logger.warning(f"No valid page counters found in XML for {ip}")
            InventoryTask.objects.create(
                printer=printer, status="FAILED", error_message=error_msg
            )
            async_to_sync(channel_layer.group_send)(
                "inventory_updates",
                {"type": "inventory_update", "printer_id": printer.id, "status": "FAILED", "message": error_msg},
            )
            return False, error_msg

        # Обновление MAC (если пустой)
        mac_address = extract_mac_address(data)
        if mac_address and not printer.mac_address:
            printer.mac_address = mac_address
            printer.save(update_fields=["mac_address"])
            cache_printer_data(printer)
            logger.info(f"Updated MAC address for {ip}: {mac_address}")

        # Валидация (серийник/MAC)
        valid, err, rule = validate_inventory(data, ip, serial, printer.mac_address)
        if not valid:
            error_msg = f"Validation failed: {err}"
            InventoryTask.objects.create(
                printer=printer, status="VALIDATION_ERROR", error_message=err
            )
            logger.error(f"Validation failed for {ip}: {err}")
            return False, error_msg

        # Сохранение счётчиков/расходников
        counters = extract_page_counters(data)
        task = InventoryTask.objects.create(printer=printer, status="SUCCESS", match_rule=rule)
        PageCounter.objects.create(task=task, **counters)

        # Последнее правило/время
        if rule:
            printer.last_match_rule = rule
            update_fields = ["last_match_rule"]
            if hasattr(printer, "last_updated"):
                printer.last_updated = timezone.now()
                update_fields.append("last_updated")
            printer.save(update_fields=update_fields)
            cache_printer_data(printer)

        # Кэш последней инвентаризации (24 ч)
        result_data = {
            'task_id': task.id,
            'timestamp': task.task_timestamp.isoformat(),
            'status': 'SUCCESS',
            'match_rule': rule,
            'counters': counters,
            'duration': (timezone.now() - start_time).total_seconds(),
        }
        inventory_cache.set(get_last_inventory_cache_key(printer_id), result_data, timeout=86400)

        # WS-уведомление
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

        duration = (timezone.now() - start_time).total_seconds()
        logger.info(f"Inventory completed for {ip} in {duration:.2f}s")
        return True, "Success"

    except Exception as e:
        ip_safe = getattr(printer, "ip_address", f"id={printer_id}") if printer else f"id={printer_id}"
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error in inventory for {ip_safe}: {e}", exc_info=True)
        try:
            if printer:
                InventoryTask.objects.create(
                    printer=printer, status="FAILED", error_message=error_msg
                )
        except Exception:
            pass
        return False, error_msg
    finally:
        inventory_cache.delete(lock_key)

# ──────────────────────────────────────────────────────────────────────────────
# ДЕПРЕКЕЙТЕД/СОВМЕСТИМОСТЬ
# ──────────────────────────────────────────────────────────────────────────────

def inventory_daemon():
    logger.warning("inventory_daemon() is deprecated. Use Celery tasks instead.")

    def worker():
        printers = Printer.objects.all()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(run_inventory_for_printer, p.id): p for p in printers}
            for future in concurrent.futures.as_completed(futures):
                printer = futures[future]
                try:
                    ok, msg = future.result()
                    logger.info(f"Inventory for {printer.ip_address}: {'OK' if ok else 'FAIL'} — {msg}")
                except Exception as e:
                    logger.error(f"Error polling {printer.ip_address}: {e}")

    threading.Thread(target=worker, daemon=True).start()

def start_scheduler():
    logger.warning("start_scheduler() is deprecated. Use Celery Beat instead.")
    return

# ──────────────────────────────────────────────────────────────────────────────
# СЕРВИСНЫЕ УТИЛИТЫ
# ──────────────────────────────────────────────────────────────────────────────

def get_cached_printer_statistics() -> Optional[dict]:
    return cache.get('printer_statistics')

def get_printer_inventory_status(printer_id: int) -> dict:
    cache_key = get_last_inventory_cache_key(printer_id)
    cached_data = inventory_cache.get(cache_key)
    if cached_data:
        return cached_data

    try:
        last_task = (
            InventoryTask.objects
            .filter(printer_id=printer_id, status='SUCCESS')
            .order_by('-task_timestamp')
            .first()
        )
        if last_task:
            counter = PageCounter.objects.filter(task=last_task).first()
            result_data = {
                'task_id': last_task.id,
                'timestamp': last_task.task_timestamp.isoformat(),
                'status': last_task.status,
                'match_rule': last_task.match_rule,
                'counters': {
                    'bw_a4': getattr(counter, 'bw_a4', None),
                    'color_a4': getattr(counter, 'color_a4', None),
                    'bw_a3': getattr(counter, 'bw_a3', None),
                    'color_a3': getattr(counter, 'color_a3', None),
                    'total_pages': getattr(counter, 'total_pages', None),
                } if counter else {}
            }
            inventory_cache.set(cache_key, result_data, timeout=3600)
            return result_data
    except Exception as e:
        logger.error(f"Error getting inventory status for printer {printer_id}: {e}")

    return {'task_id': None, 'timestamp': None, 'status': 'NEVER_RUN', 'match_rule': None, 'counters': {}}

def clear_inventory_cache(printer_id: Optional[int] = None):
    if printer_id:
        invalidate_printer_cache(printer_id)
        logger.info(f"Cleared inventory cache for printer {printer_id}")
    else:
        try:
            inventory_cache.clear()
            logger.info("Cleared entire inventory cache")
        except Exception as e:
            logger.error(f"Error clearing inventory cache: {e}")

def warm_printer_cache():
    try:
        printers = Printer.objects.select_related('organization').all()
        cached_count = 0
        for printer in printers:
            cache_printer_data(printer, timeout=7200)
            cached_count += 1
        logger.info(f"Warmed cache for {cached_count} printers")
        return cached_count
    except Exception as e:
        logger.error(f"Error warming printer cache: {e}")
        return 0

def get_redis_health_status() -> dict:
    try:
        test_key = 'health_check'
        test_value = timezone.now().isoformat()

        cache.set(test_key, test_value, timeout=60)
        retrieved_value = cache.get(test_key)
        main_cache_ok = retrieved_value == test_value

        inventory_cache.set(test_key, test_value, timeout=60)
        inventory_retrieved = inventory_cache.get(test_key)
        inventory_cache_ok = inventory_retrieved == test_value

        cache.delete(test_key)
        inventory_cache.delete(test_key)

        return {
            'main_cache': main_cache_ok,
            'inventory_cache': inventory_cache_ok,
            'overall_status': main_cache_ok and inventory_cache_ok,
            'timestamp': timezone.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            'main_cache': False,
            'inventory_cache': False,
            'overall_status': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }

def get_glpi_info() -> dict:
    """
    Диагностика конфигурации GLPI Agent.
    """
    try:
        disc_exe, inv_exe = _get_glpi_paths()
        glpi_ok, glpi_msg = _validate_glpi_installation()

        return {
            "platform": PLATFORM,
            "glpi_path": getattr(settings, "GLPI_PATH", ""),
            "discovery_executable": disc_exe,
            "inventory_executable": inv_exe,
            "discovery_exists": os.path.exists(disc_exe),
            "inventory_exists": os.path.exists(inv_exe),
            "installation_valid": glpi_ok,
            "installation_message": glpi_msg,
            "output_directory": OUTPUT_DIR,
            "use_sudo": getattr(settings, "GLPI_USE_SUDO", False) if PLATFORM in ('linux', 'darwin') else None,
            "glpi_user": getattr(settings, "GLPI_USER", "") if PLATFORM in ('linux', 'darwin') else None,
        }
    except Exception as e:
        return {"platform": PLATFORM, "error": str(e), "installation_valid": False}
