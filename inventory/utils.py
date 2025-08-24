import requests
import subprocess
import xml.etree.ElementTree as ET


# --------------------------- HTTP / Shell helpers -----------------------------

def send_device_get_request(ip_address, timeout=5):
    """
    Отправляет HTTP GET запрос на /status принтера.
    Возвращает (ok: bool, error: str|None).
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
    Выполняет shell-команду GLPI discovery/inventory.
    Возвращает (ok: bool, output_or_error: str).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout
        )
        if result.returncode != 0:
            # На Windows часто cp866; если не декодится — fallback на utf-8
            try:
                err = result.stderr.decode('cp866', errors='ignore')
            except Exception:
                err = result.stderr.decode('utf-8', errors='ignore')
            return False, err
        try:
            out = result.stdout.decode('cp866', errors='ignore')
        except Exception:
            out = result.stdout.decode('utf-8', errors='ignore')
        return True, out
    except Exception as e:
        return False, str(e)


# ------------------------------ XML helpers ----------------------------------

def xml_to_json(xml_path):
    """
    Парсит XML-файл и возвращает вложенный словарь. Повторяющиеся теги
    собираются в списки.
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


# --------------------------- Device data helpers -----------------------------

def extract_mac_address(data):
    """
    Возвращает основной MAC в виде XX:XX:XX:XX:XX:XX.
    Предпочитаем MAC у Ethernet-интерфейса; fallback — INFO.MAC или первый PORT.MAC.
    """
    dev = (data.get('CONTENT') or {}).get('DEVICE') or {}
    ports = ((dev.get('PORTS') or {}).get('PORT')) or []

    if isinstance(ports, dict):
        ports = [ports]

    # Предпочтительно: Ethernet
    for port in ports:
        if not isinstance(port, dict):
            continue
        ifdesc = str(port.get('IFDESCR') or '').lower()
        mac = port.get('MAC')
        if 'ethernet' in ifdesc and mac:
            return str(mac).upper()

    # INFO.MAC
    mac = ((dev.get('INFO') or {}).get('MAC'))
    if mac:
        return str(mac).upper()

    # Первый попавшийся MAC из PORT
    for port in ports:
        if not isinstance(port, dict):
            continue
        mac = port.get('MAC')
        if mac:
            return str(mac).upper()

    return None


def validate_inventory(data, expected_ip, expected_serial, expected_mac=None):
    """
    Многоуровневая валидация:
      1) Серийник + MAC (если оба известны и оба совпали)
      2) Только MAC (если известен и совпал)
      3) Только серийник (если совпал)
    Возвращает (ok: bool, error: str|None).
    """
    dev = (data.get('CONTENT') or {}).get('DEVICE') or {}
    info = (dev.get('INFO') or {})
    serial = info.get('SERIAL')
    mac = extract_mac_address(data)

    # 1) SN + MAC
    if expected_mac and expected_serial and serial:
        if serial == expected_serial and mac == expected_mac:
            return True, None
        if mac == expected_mac:
            return True, None
        return False, (
            f"Несоответствие: серийный номер ({serial} != {expected_serial}) "
            f"и MAC ({mac} != {expected_mac})"
        )

    # 2) Только MAC
    if expected_mac and mac == expected_mac:
        return True, None

    # 3) Только SN
    if expected_serial and serial == expected_serial:
        return True, None

    # Ничего не совпало
    parts = []
    if expected_serial and serial != expected_serial:
        parts.append(f"Серийный номер: {serial} != {expected_serial}")
    if expected_mac and mac != expected_mac:
        parts.append(f"MAC: {mac} != {expected_mac}")
    return False, "; ".join(parts) if parts else "Нет совпадений по серийному номеру или MAC"


# --------------------------- Counters & supplies ------------------------------

def extract_page_counters(data):
    """
    Собирает счётчики и уровни расходников.

    Правила:
      • Если в XML НЕТ упоминаний A3 (ни BW_A3/PRINT_A3, ни COLOR_A3),
        то A3 = 0, а A4 = TOTAL (если TOTAL присутствует).
      • Если НЕТ упоминаний цветных страниц (COLOR/COLOR_A3/COLOR_A4 со значением > 0)
        И НЕТ цветных расходников (C/M/Y), то считаем всё ч/б.
      • Если цвет определяется только расходниками (цветных счётчиков нет),
        то все страницы считаем цветными (и при отсутствии A3 — кладём всё в A4).

    Возвращает словарь:
      bw_a3, bw_a4, color_a3, color_a4, total_pages (int)
      + уровни: toner_*, drum_*, fuser_kit, transfer_kit, waste_toner (str)
    """
    dev = (data.get('CONTENT') or {}).get('DEVICE') or {}
    pc = dev.get('PAGECOUNTERS') or {}

    # --- helpers внутри функции ---
    def _to_int(val):
        try:
            return int(str(val).strip())
        except Exception:
            return None

    def first_int(*tags):
        for t in tags:
            if t in pc:
                v = _to_int(pc.get(t))
                if v is not None:
                    return v
        return None

    # --- извлечение чисел/наличия ---
    total      = first_int('TOTAL')
    bw_a3_raw  = first_int('BW_A3', 'PRINT_A3')
    bw_a4_raw  = first_int('BW_A4', 'PRINT_A4')
    color_a3_r = first_int('COLOR_A3')
    color_a4_r = first_int('COLOR_A4')
    color_gen  = first_int('COLOR')

    has_a3_mention = any(k in pc for k in ('BW_A3', 'PRINT_A3', 'COLOR_A3'))

    # подсказка цветности: по счётчикам (>0) или по расходникам
    color_by_counters = any((x or 0) > 0 for x in (color_a3_r, color_a4_r, color_gen))
    color_by_supplies = _detect_color_by_supplies_flat(dev)
    color_hint = color_by_counters or color_by_supplies

    # База значений
    bw_a3 = bw_a4 = color_a3 = color_a4 = 0

    # --- правило A3 ---
    if not has_a3_mention:
        # A3 отсутствует → всё в A4 по TOTAL (если есть)
        if total is not None:
            base_a4_total = total
        else:
            # fallback: что удалось вытащить
            base_a4_total = (bw_a4_raw or 0) + (color_a4_r or 0)
    else:
        base_a4_total = None  # не используется в этом режиме

    # --- правило цветности ---
    if not color_hint:
        # Цвета нет → всё ч/б
        if not has_a3_mention:
            bw_a3, color_a3 = 0, 0
            bw_a4, color_a4 = base_a4_total, 0
        else:
            bw_a3 = bw_a3_raw or 0
            bw_a4 = bw_a4_raw or 0
            color_a3 = 0
            color_a4 = 0
    else:
        # Цвет есть
        if (color_a3_r and color_a3_r > 0) or (color_a4_r and color_a4_r > 0):
            # Есть явные color-счётчики → используем как есть + ч/б как есть
            bw_a3 = bw_a3_raw or 0
            bw_a4 = bw_a4_raw or 0
            color_a3 = color_a3_r or 0
            color_a4 = color_a4_r or 0
        elif (color_gen and color_gen > 0):
            # Есть общий COLOR, но без разбиения → положим в A4
            if not has_a3_mention:
                bw_a3, color_a3 = 0, 0
                bw_a4, color_a4 = 0, base_a4_total
            else:
                bw_a3 = bw_a3_raw or 0
                bw_a4 = bw_a4_raw or 0
                color_a3 = 0
                color_a4 = color_gen or 0
        else:
            # Цвет определяется только расходниками → считаем всё цветным
            if not has_a3_mention:
                bw_a3, color_a3 = 0, 0
                bw_a4, color_a4 = 0, base_a4_total
            else:
                # Переносим имеющиеся ч/б-счётчики в цвет
                color_a3 = bw_a3_raw or 0
                color_a4 = bw_a4_raw or 0
                bw_a3 = 0
                bw_a4 = 0

    # нормализация и ограничение по TOTAL
    total_pages = total or 0
    s = bw_a3 + bw_a4 + color_a3 + color_a4
    if total is not None and s > total_pages:
        # урежем с приоритетом: color_a4, bw_a4, color_a3, bw_a3
        excess = s - total_pages
        for key in ('color_a4', 'bw_a4', 'color_a3', 'bw_a3'):
            if excess <= 0:
                break
            cur = locals()[key]
            if cur > 0:
                take = min(cur, excess)
                locals()[key] = cur - take
                excess -= take
        bw_a3 = locals()['bw_a3']
        bw_a4 = locals()['bw_a4']
        color_a3 = locals()['color_a3']
        color_a4 = locals()['color_a4']

    # --- уровни расходников / узлов (плоские теги) ---
    result = {
        'bw_a3': bw_a3,
        'bw_a4': bw_a4,
        'color_a3': color_a3,
        'color_a4': color_a4,
        'total_pages': total_pages,
    }

    cart = dev.get('CARTRIDGES', {}) or {}

    supply_tags = {
        'drum_black':   ['DRUMBLACK', 'DEVELOPERBLACK'],
        'drum_cyan':    ['DRUMCYAN'],
        'drum_magenta': ['DRUMMAGENTA'],
        'drum_yellow':  ['DRUMYELLOW'],
        'toner_black':  ['TONERBLACK'],
        'toner_cyan':   ['TONERCYAN'],
        'toner_magenta':['TONERMAGENTA'],
        'toner_yellow': ['TONERYELLOW'],
        'fuser_kit':    ['FUSERKIT'],
        'transfer_kit': ['TRANSFERKIT'],
        'waste_toner':  ['WASTETONER'],
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


# ------------------------------ internals ------------------------------------

def _detect_color_by_supplies_flat(dev):
    """
    True, если по плоским тегам CARTRIDGES видно наличие C/M/Y.
    Держим проверку простой и совместимой с текущими XML.
    """
    cart = dev.get('CARTRIDGES', {}) or {}
    if not isinstance(cart, dict):
        return False

    flat_color_keys = (
        'TONERCYAN', 'TONERMAGENTA', 'TONERYELLOW',
        'DRUMCYAN', 'DRUMMAGENTA', 'DRUMYELLOW',
        'DEVELOPERCYAN', 'DEVELOPERMAGENTA', 'DEVELOPERYELLOW'
    )
    return any(k in cart for k in flat_color_keys)
