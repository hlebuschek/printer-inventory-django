import requests
import subprocess
import xml.etree.ElementTree as ET

def send_device_get_request(ip_address, timeout=5):
    try:
        url = f"http://{ip_address}/status"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)

def run_glpi_command(command, timeout=300):
    try:
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if result.returncode != 0:
            return False, result.stderr.decode('cp866')
        return True, result.stdout.decode('cp866')
    except Exception as e:
        return False, str(e)

def xml_to_json(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception:
        return None
    def recurse(elem):
        d = {}
        for child in elem:
            val = recurse(child) if list(child) else child.text
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
    dev = data.get('CONTENT', {}).get('DEVICE', {})
    serial = dev.get('INFO', {}).get('SERIAL')
    if not serial:
        return False, "Серийный номер отсутствует"
    if serial != expected_serial:
        return False, f"Несоответствие серийного номера: {serial} != {expected_serial}"
    return True, None

def extract_page_counters(data):
    """
    Разбирает структуру data['CONTENT']['DEVICE']['PAGECOUNTERS']
    и возвращает счётчики страниц:
      - bw_a3, bw_a4: чёрно-белые страницы
      - color_a3, color_a4: цветные страницы
      - total_pages: общий счётчик из <TOTAL>

    Логика:
    1. Извлекаем RAW-значения из тегов.
    2. Если есть явные теги COLOR_A3 или COLOR_A4 (>0), то
       все страницы этого формата считаются цветными:
         color_a3 = COLOR_A3 + BW_A3;
         color_a4 = COLOR_A4 + BW_A4;
       bw_a3 = bw_a4 = 0.
    3. Иначе, если нет A3-данных (ни BW_A3, ни COLOR_A3), то
       счётчик A4 = total_pages (bw или color в зависимости от <COLOR>).  
    4. Иначе, если есть общий <COLOR> (>0), все PRINT_A*_ идут в цветные,
       bw_* = 0;
    5. Иначе используем явные RAW-значения;
    6. Всегда гарантируем, что возвращаемые A4-значения не превышают total_pages.
    """
    pc = data.get('CONTENT', {}).get('DEVICE', {}).get('PAGECOUNTERS', {})

    def to_int(tags):
        for tag in tags:
            val = pc.get(tag)
            if val is None:
                continue
            try:
                return int(val)
            except (ValueError, TypeError):
                continue
        return 0

    # RAW-значения
    bw_a3_raw    = to_int(['BW_A3', 'PRINT_A3'])
    bw_a4_raw    = to_int(['BW_A4', 'PRINT_A4'])
    color_a3_raw = to_int(['COLOR_A3'])
    color_a4_raw = to_int(['COLOR_A4'])
    generic_color= to_int(['COLOR'])
    total_pages  = to_int(['TOTAL'])

    # 2. Если есть per-format цветные теги, объединяем и сбрасываем bw
    if color_a3_raw > 0 or color_a4_raw > 0:
        return {
            'bw_a3': 0,
            'bw_a4': 0,
            'color_a3': min(color_a3_raw + bw_a3_raw, total_pages),
            'color_a4': min(color_a4_raw + bw_a4_raw, total_pages),
            'total_pages': total_pages,
        }

    # 3. Нет A3-данных -> A4 = total_pages
    if bw_a3_raw == 0 and color_a3_raw == 0:
        if generic_color > 0:
            return {
                'bw_a3': 0,
                'bw_a4': 0,
                'color_a3': 0,
                'color_a4': total_pages,
                'total_pages': total_pages,
            }
        else:
            return {
                'bw_a3': 0,
                'bw_a4': total_pages,
                'color_a3': 0,
                'color_a4': 0,
                'total_pages': total_pages,
            }

    # 4. Приоритет общего COLOR
    if generic_color > 0:
        return {
            'bw_a3': 0,
            'bw_a4': 0,
            'color_a3': min(bw_a3_raw, total_pages),
            'color_a4': min(bw_a4_raw, total_pages),
            'total_pages': total_pages,
        }

    # 5. Явные RAW-значения
    return {
        'bw_a3': bw_a3_raw,
        'bw_a4': min(bw_a4_raw, total_pages),
        'color_a3': color_a3_raw,
        'color_a4': min(color_a4_raw, total_pages),
        'total_pages': total_pages,
    }


def extract_consumables(data):
    """Возвращает показания расходников из XML."""
    dev = data.get('CONTENT', {}).get('DEVICE', {})

    def parse(val):
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return str(val)

    tags = [
        'DRUMBLACK', 'DRUMCYAN', 'DRUMMAGENTA', 'DRUMYELLOW',
        'FUSERKIT', 'TONERBLACK', 'TONERCYAN', 'TONERMAGENTA', 'TONERYELLOW',
        'TRANSFERKIT', 'WASTETONER',
    ]

    result = {}
    for t in tags:
        result[t.lower()] = parse(dev.get(t))
    return result
