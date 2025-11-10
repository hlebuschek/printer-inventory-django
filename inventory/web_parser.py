# inventory/web_parser.py

import re
import json
import logging
from typing import Optional, Dict, Any, Tuple
from lxml import html
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from django.conf import settings
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import platform

logger = logging.getLogger(__name__)


class SSLAdapter(HTTPAdapter):
    """Адаптер для старых SSL протоколов"""

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        context.check_hostname = False
        context.verify_mode = 0
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


# inventory/web_parser.py

def create_selenium_driver():
    """
    Создает Selenium WebDriver для Microsoft Edge в headless режиме.
    """
    try:
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver.edge.service import Service

        edge_options = EdgeOptions()

        # Headless режим
        edge_options.add_argument('--headless=new')

        # Базовые настройки
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--window-size=1920,1080')

        # SSL и сертификаты
        edge_options.add_argument('--ignore-certificate-errors')
        edge_options.add_argument('--allow-insecure-localhost')
        edge_options.add_argument('--ignore-ssl-errors')

        # User Agent
        edge_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        )

        # Отключаем автоматизацию
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)

        # Определяем путь к драйверу и браузеру
        current_dir = os.path.dirname(os.path.abspath(__file__))

        if platform.system() == 'Darwin':  # macOS
            driver_path = os.path.join(current_dir, 'edgedriver_mac64_m1', 'msedgedriver')
            edge_binary = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'

        elif platform.system() == 'Linux':
            driver_path = os.path.join(current_dir, 'edgedriver_linux64', 'msedgedriver')

            # 🔥 ЯВНО УКАЗЫВАЕМ ПУТЬ К EDGE
            edge_binary = '/usr/bin/microsoft-edge'

            # Проверяем существование
            if not os.path.exists(edge_binary):
                # Пробуем альтернативные пути
                for alt_path in ['/usr/bin/microsoft-edge-stable', '/opt/microsoft/msedge/msedge']:
                    if os.path.exists(alt_path):
                        edge_binary = alt_path
                        break
                else:
                    raise FileNotFoundError(f"Microsoft Edge not found. Tried: {edge_binary}")

        else:
            raise ValueError("Unsupported platform: Only macOS and Linux are supported.")

        # Проверяем драйвер
        if not os.path.exists(driver_path):
            raise FileNotFoundError(f"Driver not found at {driver_path}")

        # Делаем драйвер исполняемым
        os.chmod(driver_path, 0o755)

        # Указываем путь к браузеру
        if os.path.exists(edge_binary):
            edge_options.binary_location = edge_binary
            logger.info(f"Using Edge binary: {edge_binary}")
        else:
            raise FileNotFoundError(f"Edge binary not found: {edge_binary}")

        service = Service(executable_path=driver_path)
        driver = webdriver.Edge(service=service, options=edge_options)
        driver.set_page_load_timeout(30)

        logger.info(f"✓ Edge WebDriver created successfully (headless mode)")
        logger.info(f"Driver: {driver_path}")
        logger.info(f"Browser: {edge_binary}")

        return driver

    except Exception as e:
        logger.error(f"Failed to create Edge WebDriver: {e}", exc_info=True)

        # Подробное сообщение об ошибке
        error_msg = f"Could not create Edge WebDriver: {str(e)}\n"
        error_msg += f"Platform: {platform.system()}\n"

        if platform.system() == 'Linux':
            error_msg += "\nTroubleshooting for Linux:\n"
            error_msg += "1. Check Edge installation: which microsoft-edge\n"
            error_msg += "2. Check driver: ls -la inventory/edgedriver_linux64/msedgedriver\n"
            error_msg += "3. Test manually: /usr/bin/microsoft-edge --version\n"
            error_msg += "4. Check permissions: ls -la /usr/bin/microsoft-edge\n"

        raise RuntimeError(error_msg)


def apply_regex_processing(value: str, regex_pattern: str, regex_replacement: str) -> str:
    """Применяет регулярное выражение для обработки значения"""

    if not regex_pattern:
        return value

    try:
        if regex_replacement:
            processed = re.sub(regex_pattern, regex_replacement, str(value))
        else:
            match = re.search(regex_pattern, str(value))
            if match:
                processed = match.group(1) if match.groups() else match.group(0)
            else:
                processed = value

        return str(processed).upper()
    except Exception as e:
        logger.error(f"Regex processing error: {e}")
        return value


def extract_numeric_value(value: str) -> int:
    """Извлекает числовое значение из строки"""

    cleaned = str(value).replace(' ', '').replace(',', '').split('.')[0]
    numbers = re.findall(r'\d+', cleaned)

    if numbers:
        return int(''.join(numbers))

    return 0


def normalize_mac_address(mac: str) -> Optional[str]:
    """Нормализует MAC-адрес к формату XX:XX:XX:XX:XX:XX"""

    mac_clean = re.sub(r'[:\-\s]', '', str(mac).upper())

    if re.match(r'^[0-9A-F]{12}$', mac_clean):
        return ':'.join([mac_clean[i:i + 2] for i in range(0, 12, 2)])

    return None


def safe_eval_formula(formula: str, context: Dict[str, int]) -> int:
    """Безопасно вычисляет математическую формулу"""

    import ast
    import operator

    try:
        # Заменяем переменные на их значения
        formula_str = formula
        for var_name, var_value in context.items():
            formula_str = formula_str.replace(var_name, str(var_value))

        # Проверяем что остались только допустимые символы
        allowed_chars = set('0123456789+-*/(). ')
        if not all(c in allowed_chars for c in formula_str):
            raise ValueError(f"Недопустимые символы в формуле: {formula_str}")

        # Парсим формулу в AST
        tree = ast.parse(formula_str, mode='eval')

        # Разрешенные операции
        allowed_nodes = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
            ast.UAdd, ast.USub
        )

        # Проверяем что все узлы разрешены
        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                raise ValueError(f"Недопустимая операция: {type(node).__name__}")

        # Безопасно вычисляем
        result = eval(compile(tree, '', 'eval'), {"__builtins__": {}}, {})
        return int(result)

    except Exception as e:
        raise ValueError(f"Ошибка вычисления формулы '{formula}': {str(e)}")


def execute_web_parsing(printer, rules: list) -> Tuple[bool, Dict[str, Any], str]:
    """
    Выполняет веб-парсинг принтера по заданным правилам.

    Returns:
        (success, results_dict, error_message)
    """

    if not rules:
        return False, {}, "Нет правил парсинга"

    results = {}
    errors = []
    rule_results = {}  # Для вычисляемых полей

    driver = None

    try:
        driver = create_selenium_driver()

        # Группируем правила по URL
        rules_by_url = {}
        for rule in rules:
            url = f"{rule.protocol}://{printer.ip_address}{rule.url_path}"
            if url not in rules_by_url:
                rules_by_url[url] = []
            rules_by_url[url].append(rule)

        # Обрабатываем каждый URL
        for url, url_rules in rules_by_url.items():
            try:
                # Аутентификация если нужна
                if printer.web_username:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(url)
                    url = urlunparse((
                        parsed.scheme,
                        f"{printer.web_username}:{printer.web_password}@{parsed.netloc}",
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment
                    ))

                driver.get(url)

                # Обрабатываем правила для этого URL
                for rule in url_rules:
                    if rule.is_calculated:
                        continue  # Вычисляемые поля обработаем позже

                    try:
                        # Выполняем цепочку действий если есть
                        if rule.actions_chain:
                            actions = json.loads(rule.actions_chain)
                            for action in actions:
                                execute_action(driver, action)

                        # Парсим значение
                        tree = html.fromstring(driver.page_source)
                        result = tree.xpath(rule.xpath)

                        if result:
                            if isinstance(result, list):
                                raw_value = result[0].text_content().strip() if hasattr(result[0],
                                                                                        'text_content') else str(
                                    result[0])
                            else:
                                raw_value = result.text_content().strip() if hasattr(result, 'text_content') else str(
                                    result)

                            # Применяем regex
                            processed_value = apply_regex_processing(
                                raw_value,
                                rule.regex_pattern,
                                rule.regex_replacement
                            )

                            # Обработка в зависимости от типа поля
                            if rule.field_name == 'mac_address':
                                final_value = normalize_mac_address(processed_value)
                                results[rule.field_name] = final_value
                            elif rule.field_name == 'serial_number':
                                results[rule.field_name] = processed_value
                            else:
                                # Для счетчиков извлекаем числовое значение
                                numeric_value = extract_numeric_value(processed_value)
                                rule_results[rule.id] = numeric_value
                                results[rule.field_name] = numeric_value

                    except Exception as e:
                        errors.append(f"Ошибка парсинга {rule.field_name}: {str(e)}")
                        logger.error(f"Parsing error for {rule.field_name}: {e}", exc_info=True)

            except Exception as e:
                errors.append(f"Ошибка загрузки {url}: {str(e)}")
                logger.error(f"URL loading error {url}: {e}", exc_info=True)

        # Обрабатываем вычисляемые поля
        for rule in rules:
            if not rule.is_calculated:
                continue

            try:
                source_rule_ids = json.loads(rule.source_rules) if rule.source_rules else []
                formula = rule.calculation_formula

                if not source_rule_ids or not formula:
                    errors.append(f"Вычисляемое поле {rule.field_name} не имеет источников или формулы")
                    continue

                # Создаем контекст для вычисления
                context = {}
                for rule_id in source_rule_ids:
                    if rule_id in rule_results:
                        context[f'rule_{rule_id}'] = rule_results[rule_id]
                    else:
                        errors.append(f"Правило {rule_id} не имеет результата для формулы {rule.field_name}")

                if len(context) != len(source_rule_ids):
                    continue

                # Вычисляем формулу
                result_value = safe_eval_formula(formula, context)
                results[rule.field_name] = result_value

            except Exception as e:
                errors.append(f"Ошибка вычисления {rule.field_name}: {str(e)}")
                logger.error(f"Calculation error for {rule.field_name}: {e}", exc_info=True)

    finally:
        if driver:
            driver.quit()

    if not results:
        return False, {}, "; ".join(errors) if errors else "Нет результатов"

    return True, results, "; ".join(errors) if errors else ""


def execute_action(driver, action: dict):
    """Выполняет действие в браузере"""

    import time

    action_type = action.get('type')
    selector = action.get('selector')
    value = action.get('value', '')
    wait = action.get('wait', 1)

    if action_type == 'click':
        element = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        element.click()
        time.sleep(wait)

    elif action_type == 'send_keys':
        element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        element.clear()
        element.send_keys(value)
        time.sleep(wait)

    elif action_type == 'wait':
        time.sleep(wait)


def export_to_xml(printer, results: Dict[str, Any]) -> str:
    """Экспортирует результаты в XML формат совместимый с GLPI"""

    root = ET.Element('REQUEST')

    # DEVICEID
    device_id = ET.SubElement(root, 'DEVICEID')
    device_id.text = results.get('serial_number', 'unknown')

    # QUERY
    query = ET.SubElement(root, 'QUERY')
    query.text = 'WEBQUERY'

    # CONTENT
    content = ET.SubElement(root, 'CONTENT')

    # DEVICE
    device = ET.SubElement(content, 'DEVICE')

    # INFO
    info = ET.SubElement(device, 'INFO')

    model_elem = ET.SubElement(info, 'MODEL')
    model_elem.text = printer.model_display or ''

    name_elem = ET.SubElement(info, 'NAME')
    name_elem.text = printer.model_display or ''

    serial_elem = ET.SubElement(info, 'SERIAL')
    serial_elem.text = results.get('serial_number', printer.serial_number) or ''

    mac_elem = ET.SubElement(info, 'MAC')
    mac_elem.text = results.get('mac_address', printer.mac_address) or ''

    manufacturer_elem = ET.SubElement(info, 'MANUFACTURER')
    if printer.device_model and printer.device_model.manufacturer:
        manufacturer_elem.text = printer.device_model.manufacturer.name
    else:
        manufacturer_elem.text = 'Unknown'

    type_elem = ET.SubElement(info, 'TYPE')
    type_elem.text = 'PRINTER'

    # IPS
    ips_elem = ET.SubElement(info, 'IPS')
    ip_elem = ET.SubElement(ips_elem, 'IP')
    clean_ip = printer.ip_address.replace('http://', '').replace('https://', '').split(':')[0].split('/')[0]
    ip_elem.text = clean_ip

    # PAGECOUNTERS
    pagecounters = ET.SubElement(device, 'PAGECOUNTERS')

    total_elem = ET.SubElement(pagecounters, 'TOTAL')
    total_elem.text = str(results.get('counter', 0))

    bw_a4_elem = ET.SubElement(pagecounters, 'BW_A4')
    bw_a4_elem.text = str(results.get('counter_a4_bw', 0))

    bw_a3_elem = ET.SubElement(pagecounters, 'BW_A3')
    bw_a3_elem.text = str(results.get('counter_a3_bw', 0))

    color_a4_elem = ET.SubElement(pagecounters, 'COLOR_A4')
    color_a4_elem.text = str(results.get('counter_a4_color', 0))

    color_a3_elem = ET.SubElement(pagecounters, 'COLOR_A3')
    color_a3_elem.text = str(results.get('counter_a3_color', 0))

    # CARTRIDGES (расходники)
    if any(k.startswith(('toner_', 'drum_')) for k in results.keys()):
        cartridges = ET.SubElement(device, 'CARTRIDGES')

        for color in ['black', 'cyan', 'magenta', 'yellow']:
            toner_key = f'toner_{color}'
            drum_key = f'drum_{color}'

            if toner_key in results:
                toner_elem = ET.SubElement(cartridges, f'TONER{color.upper()}')
                toner_elem.text = str(results[toner_key])

            if drum_key in results:
                drum_elem = ET.SubElement(cartridges, f'DRUM{color.upper()}')
                drum_elem.text = str(results[drum_key])

    # MODULEVERSION
    moduleversion = ET.SubElement(content, 'MODULEVERSION')
    moduleversion.text = '6.8'

    # PROCESSNUMBER
    processnumber = ET.SubElement(content, 'PROCESSNUMBER')
    processnumber.text = '1'

    # Форматируем XML
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ')

    # Убираем лишние строки
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    pretty_xml = '\n'.join(lines[1:])

    return pretty_xml