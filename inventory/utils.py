import requests
import subprocess
import xml.etree.ElementTree as ET


def extract_mac_address(data):
    """
    Извлекает основной MAC-адрес из XML, предпочитая Ethernet интерфейс.
    Возвращает MAC в формате XX:XX:XX:XX:XX:XX или None, если не найден.
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    ports = dev.get('PORTS', {}).get('PORT', [])

    # Если PORT является словарем (один порт), преобразуем в список
    if isinstance(ports, dict):
        ports = [ports]

    # Поиск Ethernet порта
    for port in ports:
        ifdesc = port.get('IFDESCR', '').lower()
        if 'ethernet' in ifdesc and port.get('MAC'):
            return port['MAC'].upper()

    # Если Ethernet не найден, берём первый MAC из INFO
    mac = dev.get('INFO', {}).get('MAC')
    if mac:
        return mac.upper()

    # Если нет MAC в INFO, берём первый MAC из PORT
    for port in ports:
        if port.get('MAC'):
            return port['MAC'].upper()

    return None


def send_device_get_request(ip_address, timeout=5):
    """
    Отправляет HTTP GET запрос на /status принтера.
    Возвращает кортеж: (успех: bool, сообщение об ошибке или None).
    """
    try:
        url = f"http://{ip_address}/status"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)


def run_glpi_command(command, timeout=300):
    """
    Выполняет shell-команду для интеграции с GLPI.
    Возвращает кортеж: (успех: bool, вывод или сообщение об ошибке).
    """
    try:
        result = subprocess.run(
            command, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout
        )
        if result.returncode != 0:
            return False, result.stderr.decode('cp866')
        return True, result.stdout.decode('cp866')
    except Exception as e:
        return False, str(e)


def xml_to_json(xml_path):
    """
    Парсит XML-файл по пути xml_path и возвращает вложенный словарь.
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


def validate_inventory(data, expected_ip, expected_serial, expected_mac=None):
    """
    Проверяет данные устройства из XML с многоуровневой валидацией:
    1. Серийный номер + MAC (если MAC известен).
    2. Только MAC (если MAC известен).
    3. Только серийный номер.
    Возвращает (bool, сообщение об ошибке или None).
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    serial = dev.get('INFO', {}).get('SERIAL')
    mac = extract_mac_address(data)

    if not serial:
        return False, "Серийный номер отсутствует"

    # Уровень 1: Проверка серийного номера и MAC
    if expected_mac:
        if serial == expected_serial and mac == expected_mac:
            return True, None
        # Уровень 2: Проверка только MAC
        if mac == expected_mac:
            return True, None
        # Уровень 3: Проверка только серийного номера
        if serial == expected_serial:
            return True, None
        return False, f"Несоответствие: серийный номер ({serial} != {expected_serial}) и MAC ({mac} != {expected_mac})"

    # Если MAC неизвестен, проверяем только серийный номер
    if serial == expected_serial:
        return True, None
    return False, f"Несоответствие серийного номера: {serial} != {expected_serial}"


def extract_page_counters(data):
    """
    Разбирает структуру data['CONTENT']['DEVICE'] и возвращает словарь с полями:
      - bw_a3, bw_a4: чёрно-белые страницы (int)
      - color_a3, color_a4: цветные страницы (int)
      - total_pages: общий счётчик (int)
      - drum_black, drum_cyan, drum_magenta, drum_yellow: уровни драмов (str)
      - toner_black, toner_cyan, toner_magenta, toner_yellow: уровни тонеров (str)
      - fuser_kit, transfer_kit, waste_toner: статусы узлов (str)
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    pc = dev.get('PAGECOUNTERS', {})

    def to_int(tags):
        """Преобразует первое найденное значение из списка тегов в int, иначе 0"""
        for tag in tags:
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

    if color_a3_raw > 0 or color_a4_raw > 0:
        bw_a3, bw_a4 = 0, 0
        color_a3 = min(color_a3_raw + bw_a3_raw, total_pages)
        color_a4 = min(color_a4_raw + bw_a4_raw, total_pages)
    elif bw_a3_raw == 0 and color_a3_raw == 0:
        if generic_color > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3, color_a4 = 0, total_pages
        else:
            bw_a3, bw_a4 = 0, total_pages
            color_a3, color_a4 = 0, 0
    elif generic_color > 0:
        bw_a3, bw_a4 = 0, 0
        color_a3 = min(bw_a3_raw, total_pages)
        color_a4 = min(bw_a4_raw, total_pages)
    else:
        bw_a3, bw_a4 = bw_a3_raw, min(bw_a4_raw, total_pages)
        color_a3, color_a4 = color_a3_raw, min(color_a4_raw, total_pages)

    result = {
        'bw_a3': bw_a3,
        'bw_a4': bw_a4,
        'color_a3': color_a3,
        'color_a4': color_a4,
        'total_pages': total_pages,
    }

    cart = dev.get('CARTRIDGES', {})
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
                val = raw
                break
        result[field_name] = val or ''

    return result