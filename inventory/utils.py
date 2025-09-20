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
                val = str(raw)
                break
        result[field_name] = val or ''

    return result
