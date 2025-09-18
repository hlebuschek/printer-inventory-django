import re
import locale
import platform
import requests
import subprocess
import xml.etree.ElementTree as ET


# ---------- ВСПОМОГАТЕЛЬНОЕ ----------

def normalize_mac(raw):
    """
    Приводит MAC к каноническому виду XX:XX:XX:XX:XX:XX.
    Любые разделители/регистры игнорируются. Если не похоже на MAC — вернёт None.
    """
    if not raw:
        return None
    hexes = re.sub(r'[^0-9A-Fa-f]', '', str(raw))
    if len(hexes) != 12:
        return None
    return ':'.join(hexes[i:i+2] for i in range(0, 12, 2)).upper()


def mac_equal(a, b):
    """Безопасное сравнение двух MAC-адресов с нормализацией."""
    na, nb = normalize_mac(a), normalize_mac(b)
    return na is not None and nb is not None and na == nb


def _decode_bytes(b: bytes) -> str:
    """
    Аккуратно декодируем байты с учётом ОС/локали.
    На Windows часто cp866/cp1251, на *nix — локаль/utf-8.
    """
    candidates = [locale.getpreferredencoding(False), 'cp866', 'cp1251', 'utf-8']
    tried = set()
    for enc in candidates:
        if not enc or enc.lower() in tried:
            continue
        tried.add(enc.lower())
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('utf-8', errors='replace')


# ---------- ПАРСИНГ И СЕТЬ ----------

def extract_mac_address(data):
    """
    Извлекает базовый MAC-адрес из XML-структуры data, предпочитая Ethernet-порт.
    Возвращает канонический MAC (XX:XX:XX:XX:XX:XX) или None.
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    ports = dev.get('PORTS', {}).get('PORT', [])

    if isinstance(ports, dict):
        ports = [ports]

    # 1) Предпочтение Ethernet/LAN
    for port in ports:
        desc = (port.get('IFDESCR') or port.get('IFNAME') or '').lower()
        mac_raw = port.get('MAC')
        if mac_raw and any(key in desc for key in ('ethernet', 'eth', 'lan', 'gigabit', 'fast')):
            mac = normalize_mac(mac_raw)
            if mac:
                return mac

    # 2) INFO.MAC
    mac = normalize_mac(dev.get('INFO', {}).get('MAC'))
    if mac:
        return mac

    # 3) Любой первый MAC из PORT
    for port in ports:
        mac = normalize_mac(port.get('MAC'))
        if mac:
            return mac

    return None


def send_device_get_request(ip_address, timeout=5):
    """
    Отправляет HTTP GET на /status принтера.
    Возвращает: (успех: bool, сообщение об ошибке или None).
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
    Выполняет shell-команду для интеграции с GLPI.
    Возвращает: (успех: bool, вывод или сообщение об ошибке).
    Примечание: shell=True оставлен для совместимости со скриптами .bat.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout
        )
        out = _decode_bytes(result.stdout)
        err = _decode_bytes(result.stderr)
        if result.returncode != 0:
            return False, err.strip() or out.strip()
        return True, out.strip()
    except Exception as e:
        return False, str(e)


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
    Проверяет данные устройства из XML с многоуровневой валидацией:
      1) Серийный номер + MAC
      2) Только MAC
      3) Только серийный номер
    Возвращает: (is_valid: bool, error_message|None, match_rule: 'SN_MAC'|'MAC_ONLY'|'SN_ONLY'|None)
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    serial = dev.get('INFO', {}).get('SERIAL')
    serial = (serial.strip() if isinstance(serial, str) else None) or None

    expected_serial = (expected_serial.strip() if isinstance(expected_serial, str) else None) or None

    mac = extract_mac_address(data)
    expected_mac_norm = normalize_mac(expected_mac)

    # 1) Серийник + MAC
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

    # 2) Только MAC
    if expected_mac_norm and mac_equal(mac, expected_mac_norm):
        return True, None, 'MAC_ONLY'

    # 3) Только серийник
    if serial and expected_serial and serial == expected_serial:
        return True, None, 'SN_ONLY'

    # Ничего не подошло
    error_msg = []
    if expected_serial and serial != expected_serial:
        error_msg.append(f"Серийный номер: {serial or '—'} != {expected_serial}")
    if expected_mac_norm and not mac_equal(mac, expected_mac_norm):
        error_msg.append(f"MAC: {mac or '—'} != {expected_mac_norm}")
    return False, "; ".join(error_msg) if error_msg else "Нет совпадений по серийному номеру или MAC", None


def extract_page_counters(data):
    """
    Разбирает структуру data['CONTENT']['DEVICE'] и возвращает словарь:
      - bw_a3, bw_a4 (int)
      - color_a3, color_a4 (int)
      - total_pages (int)
      - drum_*, toner_* (str)
      - fuser_kit, transfer_kit, waste_toner (str: OK|WARNING|'')

    Новая логика: если есть цветные расходники (тонеры/барабаны C/M/Y),
    то принтер считается цветным и все страницы идут в цветные счетчики.
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

    # Получаем базовые счетчики
    bw_a3_raw = to_int(['BW_A3', 'PRINT_A3'])
    bw_a4_raw = to_int(['BW_A4', 'PRINT_A4'])
    color_a3_raw = to_int(['COLOR_A3'])
    color_a4_raw = to_int(['COLOR_A4'])
    generic_color = to_int(['COLOR'])
    total_pages = to_int(['TOTAL'])

    # === НОВАЯ ЛОГИКА: определяем цветной ли принтер ===

    # 1. Проверяем наличие цветных расходников
    color_supplies = [
        'TONERCYAN', 'TONERMAGENTA', 'TONERYELLOW',
        'DRUMCYAN', 'DRUMMAGENTA', 'DRUMYELLOW',
        'DEVELOPERCYAN', 'DEVELOPERMAGENTA', 'DEVELOPERYELLOW'
    ]

    has_color_supplies = False
    for supply in color_supplies:
        # Проверяем и в CARTRIDGES, и в DEVICE (разные принтеры по-разному структурируют XML)
        if cart.get(supply) or dev.get(supply):
            has_color_supplies = True
            break

    # 2. Проверяем наличие цветных счетчиков страниц
    has_color_counters = color_a3_raw > 0 or color_a4_raw > 0

    # 3. Проверяем generic color счетчик
    has_generic_color = generic_color > 0

    # Принтер цветной, если ЛЮБОЕ из условий выполняется
    is_color_printer = has_color_supplies or has_color_counters or has_generic_color

    if is_color_printer:
        # Применяем старую логику для цветных принтеров
        if color_a3_raw > 0 or color_a4_raw > 0:
            # Есть детальные цветные счетчики
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(color_a3_raw + bw_a3_raw, total_pages) if total_pages else color_a3_raw + bw_a3_raw
            color_a4 = min(color_a4_raw + bw_a4_raw, total_pages) if total_pages else color_a4_raw + bw_a4_raw
        elif bw_a3_raw == 0 and color_a3_raw == 0:
            # Нет A3 счетчиков вообще
            if generic_color > 0:
                bw_a3, bw_a4 = 0, 0
                color_a3, color_a4 = 0, total_pages
            else:
                # Есть только цветные расходники, но нет цветных страниц
                # Все имеющиеся страницы считаем цветными
                bw_a3, bw_a4 = 0, 0
                color_a3 = bw_a3_raw
                color_a4 = bw_a4_raw
                # Если нет детализации по форматам, используем total
                if color_a3 == 0 and color_a4 == 0 and total_pages > 0:
                    color_a4 = total_pages
        elif generic_color > 0:
            # Есть A3 счетчики и generic color
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(bw_a3_raw, total_pages) if total_pages else bw_a3_raw
            color_a4 = min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
        else:
            # Есть только цветные расходники
            bw_a3, bw_a4 = 0, 0
            color_a3 = bw_a3_raw
            color_a4 = bw_a4_raw
            # Если нет детализации по форматам, используем total
            if color_a3 == 0 and color_a4 == 0 and total_pages > 0:
                color_a4 = total_pages
    else:
        # === ЛОГИКА для ч/б принтеров ===
        # Здесь мы уже знаем, что нет ни цветных расходников, ни цветных счетчиков
        if bw_a3_raw == 0 and color_a3_raw == 0:
            if generic_color > 0:
                bw_a3, bw_a4 = 0, 0
                color_a3, color_a4 = 0, total_pages
            else:
                bw_a3, bw_a4 = 0, total_pages
                color_a3, color_a4 = 0, 0
        elif generic_color > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3 = min(bw_a3_raw, total_pages) if total_pages else bw_a3_raw
            color_a4 = min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
        else:
            bw_a3, bw_a4 = bw_a3_raw, min(bw_a4_raw, total_pages) if total_pages else bw_a4_raw
            color_a3, color_a4 = color_a3_raw, min(color_a4_raw, total_pages) if total_pages else color_a4_raw

    result = {
        'bw_a3': bw_a3,
        'bw_a4': bw_a4,
        'color_a3': color_a3,
        'color_a4': color_a4,
        'total_pages': total_pages,
    }

    # Извлечение расходников остается без изменений
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
