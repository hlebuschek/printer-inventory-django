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
    pc = data.get('CONTENT', {}).get('DEVICE', {}).get('PAGECOUNTERS', {})
    def to_int(v):
        try:
            return int(v)
        except:
            return None
    total = to_int(pc.get('TOTAL')) or 0
    bw_a3 = to_int(pc.get('BW_A3') or pc.get('PRINT_A3'))
    bw_a4 = to_int(pc.get('BW_A4') or pc.get('PRINT_A4'))
    color_a3 = to_int(pc.get('COLOR_A3'))
    color_a4 = to_int(pc.get('COLOR_A4'))
    generic_color = to_int(pc.get('COLOR'))
    result = {'bw_a3': None, 'bw_a4': None, 'color_a3': None, 'color_a4': None, 'total_pages': total}
    if bw_a3 is not None and bw_a4 is not None and color_a3 is not None and color_a4 is not None:
        result['color_a4'] = color_a4 + bw_a4
        result['color_a3'] = color_a3 + bw_a3
        return result
    if bw_a3 is not None and (color_a3 is None or color_a3 == 0) and bw_a4 is None:
        result['bw_a3'] = bw_a3
        result['bw_a4'] = max(0, total - bw_a3)
        return result
    if bw_a3 is None and generic_color and generic_color > 0:
        result['color_a4'] = total
        return result
    if bw_a3 is None:
        result['bw_a4'] = total
        return result
    if bw_a3 is not None:
        result['bw_a3'] = bw_a3
    if bw_a4 is not None:
        result['bw_a4'] = bw_a4
    if color_a3 is not None:
        result['color_a3'] = color_a3
    if color_a4 is not None:
        result['color_a4'] = color_a4
    return result
