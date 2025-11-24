import re
import shlex
import locale
import platform
import requests
import subprocess
import xml.etree.ElementTree as ET


# ---------- ВСПОМОГАТЕЛЬНОЕ ----------

def normalize_mac(raw):
    """
    Приводит MAC к каноническому виду XX:XX:XX:XX:XX:XX.
    """
    if not raw:
        return None
    hexes = re.sub(r'[^0-9A-Fa-f]', '', str(raw))
    if len(hexes) != 12:
        return None
    return ':'.join(hexes[i:i+2] for i in range(0, 12, 2)).upper()

def mac_equal(a, b):
    na, nb = normalize_mac(a), normalize_mac(b)
    return na is not None and nb is not None and na == nb

def _decode_bytes(b: bytes) -> str:
    """
    Аккуратное декодирование вывода subprocess с учётом ОС/локали.
    Windows: cp866/cp1251/locale/utf-8
    *nix: utf-8/locale/iso-8859-1
    """
    system = platform.system().lower()
    if system == 'windows':
        candidates = ['cp866', 'cp1251', locale.getpreferredencoding(False), 'utf-8']
    else:
        candidates = ['utf-8', locale.getpreferredencoding(False), 'iso-8859-1']

    tried = set()
    for enc in candidates:
        if not enc:
            continue
        key = enc.lower()
        if key in tried:
            continue
        tried.add(key)
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('utf-8', errors='replace')

# ---------- ПАРСИНГ И СЕТЬ ----------

def extract_mac_address(data):
    """
    Извлекает MAC (предпочтение Ethernet/LAN).
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    ports = dev.get('PORTS', {}).get('PORT', [])

    if isinstance(ports, dict):
        ports = [ports]

    for port in ports:
        desc = (port.get('IFDESCR') or port.get('IFNAME') or '').lower()
        mac_raw = port.get('MAC')
        if mac_raw and any(key in desc for key in ('ethernet', 'eth', 'lan', 'gigabit', 'fast')):
            mac = normalize_mac(mac_raw)
            if mac:
                return mac

    mac = normalize_mac(dev.get('INFO', {}).get('MAC'))
    if mac:
        return mac

    for port in ports:
        mac = normalize_mac(port.get('MAC'))
        if mac:
            return mac

    return None

def send_device_get_request(ip_address, timeout=5):
    """
    HTTP GET на /status принтера.
    """
    try:
        url = f"http://{ip_address}/status"
        headers = {"User-Agent": "printer-inventory/1.0"}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)

def run_glpi_command(command, timeout=300):
    """
    Кроссплатформенный запуск внешней команды GLPI.
    Возвращает (ok: bool, stdout|error: str).

    - Windows: shell=True (поддержка .bat), скрываем окно
    - Linux/macOS: shell=False + shlex.split для безопасности
    """
    system = platform.system().lower()

    try:
        if system == 'windows':
            creationflags = 0
            # CREATE_NO_WINDOW доступен только на Windows
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                creationflags=creationflags
            )
        else:
            if isinstance(command, str):
                command_list = shlex.split(command)
            else:
                command_list = command
            result = subprocess.run(
                command_list,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout
            )

        out = _decode_bytes(result.stdout)
        err = _decode_bytes(result.stderr)

        if result.returncode != 0:
            error_msg = err.strip() or out.strip() or f"Command failed with exit code {result.returncode}"
            return False, error_msg

        return True, out.strip()

    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except FileNotFoundError as e:
        return False, f"Executable not found: {e}"
    except PermissionError as e:
        return False, f"Permission denied: {e}"
    except Exception as e:
        return False, f"Command execution error: {e}"

def xml_to_json(xml_path):
    """
    Парсит XML-файл и возвращает вложенный словарь (без атрибутов).
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return {}

    def recurse(elem):
        d = {}
        for child in elem:
            val = recurse(child) if list(child) else (child.text or '')
            tag = child.tag
            if tag in d:
                if isinstance(d[tag], list):
                    d[tag].append(val)
                else:
                    d[tag] = [d[tag], val]
            else:
                d[tag] = val
        return d

    return recurse(root)

# ---------- ВАЛИДАЦИЯ/ИМПОРТ ----------

def validate_inventory(data, expected_ip, expected_serial, expected_mac=None):
    """
    Многоуровневая валидация по серийнику/MAC.
    Возвращает (is_valid, error|None, match_rule|'SN_MAC'|'MAC_ONLY'|'SN_ONLY'|None).
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    serial = dev.get('INFO', {}).get('SERIAL')
    serial = (serial.strip() if isinstance(serial, str) else None) or None
    expected_serial = (expected_serial.strip() if isinstance(expected_serial, str) else None) or None

    mac = extract_mac_address(data)
    expected_mac_norm = normalize_mac(expected_mac)

    if expected_mac_norm and serial and expected_serial:
        if serial == expected_serial and mac_equal(mac, expected_mac_norm):
            return True, None, 'SN_MAC'
        if mac_equal(mac, expected_mac_norm):
            return True, None, 'MAC_ONLY'
        return (
            False,
            f"Несоответствие: серийный номер ({serial} != {expected_serial}) и MAC ({mac or '—'} != {expected_mac_norm})",
            None,
        )

    if expected_mac_norm and mac_equal(mac, expected_mac_norm):
        return True, None, 'MAC_ONLY'

    if serial and expected_serial and serial == expected_serial:
        return True, None, 'SN_ONLY'

    error_msg = []
    if expected_serial and serial != expected_serial:
        error_msg.append(f"Серийный номер: {serial or '—'} != {expected_serial}")
    if expected_mac_norm and not mac_equal(mac, expected_mac_norm):
        error_msg.append(f"MAC: {mac or '—'} != {expected_mac_norm}")
    return False, "; ".join(error_msg) if error_msg else "Нет совпадений по серийному номеру или MAC", None

def extract_page_counters(data):
    """
    Возвращает:
      - bw_a3, bw_a4, color_a3, color_a4, total_pages
      - drum_*, toner_*, fuser_kit, transfer_kit, waste_toner
    Логика цветности: наличие цветных расходников или цветных счетчиков → цветной.
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    pc = dev.get('PAGECOUNTERS', {}) or {}
    cart = dev.get('CARTRIDGES', {}) or {}

    def to_int(tag_list):
        for tag in tag_list:
            raw = pc.get(tag)
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
        return 0

    bw_a3_raw = to_int(['BW_A3', 'PRINT_A3'])
    bw_a4_raw = to_int(['BW_A4', 'PRINT_A4'])
    color_a3_raw = to_int(['COLOR_A3'])
    color_a4_raw = to_int(['COLOR_A4'])
    generic_color = to_int(['COLOR'])
    total_pages = to_int(['TOTAL'])

    color_supplies = [
        'TONERCYAN', 'TONERMAGENTA', 'TONERYELLOW',
        'DRUMCYAN', 'DRUMMAGENTA', 'DRUMYELLOW',
        'DEVELOPERCYAN', 'DEVELOPERMAGENTA', 'DEVELOPERYELLOW'
    ]
    has_color_supplies = any(cart.get(s) or dev.get(s) for s in color_supplies)
    has_color_counters = color_a3_raw > 0 or color_a4_raw > 0
    has_generic_color = generic_color > 0

    is_color_printer = has_color_supplies or has_color_counters or has_generic_color

    if is_color_printer:
        if color_a3_raw > 0 or color_a4_raw > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(color_a3_raw + bw_a3_raw, total_pages) if total_pages else color_a3_raw + bw_a3_raw
            color_a4 = min(color_a4_raw + bw_a4_raw, total_pages) if total_pages else color_a4_raw + bw_a4_raw
        elif bw_a3_raw == 0 and color_a3_raw == 0:
            if generic_color > 0:
                bw_a3, bw_a4, color_a3, color_a4 = 0, 0, 0, total_pages
            else:
                bw_a3, bw_a4 = 0, 0
                color_a3, color_a4 = bw_a3_raw, bw_a4_raw
                if color_a3 == 0 and color_a4 == 0 and total_pages > 0:
                    color_a4 = total_pages
        elif generic_color > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(bw_a3_raw, total_pages) if total_pages else bw_a3_raw
            color_a4 = min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
        else:
            bw_a3, bw_a4 = 0, 0
            color_a3, color_a4 = bw_a3_raw, bw_a4_raw
            if color_a3 == 0 and color_a4 == 0 and total_pages > 0:
                color_a4 = total_pages
    else:
        if bw_a3_raw == 0 and color_a3_raw == 0:
            if generic_color > 0:
                bw_a3, bw_a4, color_a3, color_a4 = 0, 0, 0, total_pages
            else:
                bw_a3, bw_a4, color_a3, color_a4 = 0, total_pages, 0, 0
        elif generic_color > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(bw_a3_raw, total_pages) if total_pages else bw_a3_raw
            color_a4 = min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
        else:
            bw_a3 = bw_a3_raw
            bw_a4 = min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
            color_a3 = color_a3_raw
            color_a4 = min(color_a4_raw, total_pages) if total_pages else color_a4_raw

    result = {
        'bw_a3': bw_a3,
        'bw_a4': bw_a4,
        'color_a3': color_a3,
        'color_a4': color_a4,
        'total_pages': total_pages,
    }

    supply_tags = {
        'drum_black': ['DRUMBLACK', 'DEVELOPERBLACK'],
        'drum_cyan': ['DRUMCYAN'],
        'drum_magenta': ['DRUMMAGENTA'],
        'drum_yellow': ['DRUMYELLOW'],
        'toner_black': ['TONERBLACK'],
        'toner_cyan': ['TONERCYAN'],
        'toner_magenta': ['TONERMAGENTA'],
        'toner_yellow': ['TONERYELLOW'],
        'fuser_kit': ['FUSERKIT'],
        'transfer_kit': ['TRANSFERKIT'],
        'waste_toner': ['WASTETONER'],
    }
    for field_name, tags in supply_tags.items():
        val = ''
        for tag in tags:
            raw = cart.get(tag) or dev.get(tag)
            if raw:
                # Truncate to 20 characters to fit database field
                val = str(raw)[:20]
                break
        result[field_name] = val or ''

    return result


def validate_against_history(printer, new_counters):
    """
    Валидирует новые счетчики против истории принтера.

    Проверяет:
    1. Если принтер раньше отдавал A3, а сейчас не отдает - считаем невалидными
    2. Если принтер раньше отдавал цветные счетчики, а сейчас не отдает - считаем невалидными
    3. Общая логичность данных (счетчики не уменьшились значительно без объяснения)

    Returns:
        tuple: (is_valid: bool, error_message: str, validation_rule: str)
    """
    from .models import InventoryTask, PageCounter
    from django.db.models import Q

    # Получаем последние 5 успешных записей для анализа паттерна
    recent_tasks = InventoryTask.objects.filter(
        printer=printer,
        status='SUCCESS'
    ).order_by('-task_timestamp')[:5]

    if not recent_tasks.exists():
        # Нет истории - принимаем данные
        return True, None, None

    recent_counters = PageCounter.objects.filter(
        task__in=recent_tasks
    ).order_by('-task__task_timestamp')

    if not recent_counters.exists():
        return True, None, None

    # Анализируем исторические паттерны
    historical_patterns = {
        'had_a3': False,
        'had_color': False,
        'had_a3_count': 0,
        'had_color_count': 0,
        'total_records': 0
    }

    for counter in recent_counters:
        historical_patterns['total_records'] += 1

        # Проверяем наличие A3 счетчиков
        if (counter.bw_a3 and counter.bw_a3 > 0) or (counter.color_a3 and counter.color_a3 > 0):
            historical_patterns['had_a3'] = True
            historical_patterns['had_a3_count'] += 1

        # Проверяем наличие цветных счетчиков
        if (counter.color_a3 and counter.color_a3 > 0) or (counter.color_a4 and counter.color_a4 > 0):
            historical_patterns['had_color'] = True
            historical_patterns['had_color_count'] += 1

    # Пороги для определения "стабильного" паттерна
    a3_threshold = 0.6  # 60% записей должны содержать A3
    color_threshold = 0.6  # 60% записей должны содержать цвет

    # Определяем стабильные паттерны
    stable_a3 = (historical_patterns['had_a3_count'] / historical_patterns['total_records']) >= a3_threshold
    stable_color = (historical_patterns['had_color_count'] / historical_patterns['total_records']) >= color_threshold

    # Проверяем новые данные против паттернов
    validation_errors = []

    # 1. Проверка A3 счетчиков
    new_has_a3 = (new_counters.get('bw_a3', 0) > 0) or (new_counters.get('color_a3', 0) > 0)
    if stable_a3 and not new_has_a3:
        validation_errors.append(
            f"Принтер исторически отдавал A3 счетчики ({historical_patterns['had_a3_count']}/{historical_patterns['total_records']} записей), "
            f"но в текущем опросе A3 данные отсутствуют"
        )

    # 2. Проверка цветных счетчиков
    new_has_color = (new_counters.get('color_a3', 0) > 0) or (new_counters.get('color_a4', 0) > 0)
    if stable_color and not new_has_color:
        validation_errors.append(
            f"Принтер исторически отдавал цветные счетчики ({historical_patterns['had_color_count']}/{historical_patterns['total_records']} записей), "
            f"но в текущем опросе цветные данные отсутствуют"
        )

    # 3. Проверка на значительное уменьшение счетчиков (возможная перезагрузка/сброс)
    # 4. Проверка на аномальное увеличение счетчиков (защита от глюков Kyocera)
    if recent_counters.exists():
        latest = recent_counters.first()
        latest_task = latest.task

        # Получаем время последнего опроса
        from django.utils import timezone
        from datetime import timedelta
        from django.conf import settings

        time_window_hours = getattr(settings, 'ANOMALY_CHECK_TIME_WINDOW_HOURS', 2)
        time_since_last_poll = timezone.now() - latest_task.task_timestamp
        is_recent_poll = time_since_last_poll < timedelta(hours=time_window_hours)

        # Проверяем основные счетчики
        counters_to_check = [
            ('bw_a4', 'ЧБ A4'),
            ('color_a4', 'Цветные A4'),
            ('total_pages', 'Общий счетчик')
        ]

        for field, name in counters_to_check:
            old_value = getattr(latest, field, None) or 0
            new_value = new_counters.get(field, 0) or 0

            # Проверка на уменьшение (более чем на 10%)
            if old_value > 100 and new_value < (old_value * 0.9):
                validation_errors.append(
                    f"{name}: значительное уменьшение с {old_value} до {new_value} "
                    f"(возможен сброс счетчика или ошибка SNMP)"
                )

            # 🛡️ ЗАЩИТА ОТ АНОМАЛЬНЫХ СКАЧКОВ (Kyocera bug)
            # Если принтер недавно опрашивался и счетчик резко вырос - это подозрительно
            if is_recent_poll and old_value > 0:
                increase = new_value - old_value
                increase_ratio = new_value / old_value if old_value > 0 else 0

                # Получаем пороги из настроек
                huge_jump_threshold = getattr(settings, 'ANOMALY_HUGE_JUMP_THRESHOLD', 100000)
                suspicious_ratio = getattr(settings, 'ANOMALY_SUSPICIOUS_RATIO', 1.5)
                ratio_min_increase = getattr(settings, 'ANOMALY_RATIO_MIN_INCREASE', 50000)

                # Критерии аномалии:
                # 1. Увеличение более чем на ANOMALY_HUGE_JUMP_THRESHOLD страниц за короткое время
                # 2. ИЛИ увеличение более чем в ANOMALY_SUSPICIOUS_RATIO раз и абсолютное увеличение > ANOMALY_RATIO_MIN_INCREASE
                is_huge_jump = increase > huge_jump_threshold
                is_suspicious_ratio = increase_ratio > suspicious_ratio and increase > ratio_min_increase

                if is_huge_jump or is_suspicious_ratio:
                    hours = int(time_since_last_poll.total_seconds() / 3600)
                    minutes = int((time_since_last_poll.total_seconds() % 3600) / 60)
                    time_str = f"{hours}ч {minutes}мин" if hours > 0 else f"{minutes}мин"

                    validation_errors.append(
                        f"{name}: аномальный скачок счетчика с {old_value} до {new_value} "
                        f"(+{increase} страниц за {time_str}). "
                        f"Возможно, это глюк принтера Kyocera. Данные отклонены."
                    )

    if validation_errors:
        return False, "; ".join(validation_errors), "HISTORICAL_INCONSISTENCY"

    return True, None, None