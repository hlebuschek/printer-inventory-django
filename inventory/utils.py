import requests
import subprocess
import xml.etree.ElementTree as ET


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
            # Если у узла есть вложенные элементы, рекурсивно обрабатываем
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


def validate_inventory(data, expected_ip, expected_serial):
    """
    Проверяет данные устройства из XML:
      - наличие и совпадение серийного номера.
    Возвращает (bool, сообщение об ошибке или None).
    """
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    serial = dev.get('INFO', {}).get('SERIAL')
    if not serial:
        return False, "Серийный номер отсутствует"
    if serial != expected_serial:
        return False, f"Несоответствие серийного номера: {serial} != {expected_serial}"
    return True, None


def extract_page_counters(data):
    """
    Разбирает структуру data['CONTENT']['DEVICE'] и возвращает словарь с полями:
      - bw_a3, bw_a4: чёрно-белые страницы (int)
      - color_a3, color_a4: цветные страницы (int)
      - total_pages: общий счётчик (int)
      - drum_black, drum_cyan, drum_magenta, drum_yellow: уровни драмов (str)
      - toner_black, toner_cyan, toner_magenta, toner_yellow: уровни тонеров (str)
      - fuser_kit, transfer_kit, waste_toner: статусы узлов (str)
    Логика подсчёта страниц:
      см. комментарии в коде.
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

    # 1) Если есть per-format теги цветных страниц, объединяем их с BW и сбрасываем BW
    if color_a3_raw > 0 or color_a4_raw > 0:
        bw_a3, bw_a4 = 0, 0
        color_a3 = min(color_a3_raw + bw_a3_raw, total_pages)
        color_a4 = min(color_a4_raw + bw_a4_raw, total_pages)
    # 2) Если нет данных по A3, все страницы в A4 (цветные или черно-белые)
    elif bw_a3_raw == 0 and color_a3_raw == 0:
        if generic_color > 0:
            bw_a3, bw_a4 = 0, 0
            color_a3, color_a4 = 0, total_pages
        else:
            bw_a3, bw_a4 = 0, total_pages
            color_a3, color_a4 = 0, 0
    # 3) Если общий COLOR > 0, считаем все PRINT_A*_ как цветные
    elif generic_color > 0:
        bw_a3, bw_a4 = 0, 0
        color_a3 = min(bw_a3_raw, total_pages)
        color_a4 = min(bw_a4_raw, total_pages)
    # 4) Иначе используем RAW-значения, не превышая total_pages
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

    # Добавляем уровни расходников и статусы из раздела CARTRIDGES
    cart = dev.get('CARTRIDGES', {})
    for key in ['DRUMBLACK', 'DRUMCYAN', 'DRUMMAGENTA', 'DRUMYELLOW',
                'TONERBLACK', 'TONERCYAN', 'TONERMAGENTA', 'TONERYELLOW',
                'FUSERKIT', 'TRANSFERKIT', 'WASTETONER']:
        result[key.lower()] = cart.get(key, '')

    return result