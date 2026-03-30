# inventory/views/web_parser_views.py

import ipaddress
import json
import logging
from urllib.parse import urlparse

from lxml import html

from django.contrib.auth.decorators import login_required, permission_required
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from ..models import Printer, WebParsingRule

logger = logging.getLogger(__name__)


def _validate_printer_url(url: str) -> tuple[bool, str]:
    """
    Валидирует URL для веб-парсинга принтеров.
    Разрешает только http/https и запрещает приватные/зарезервированные IP.
    """
    if not url:
        return False, "URL не указан"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Некорректный URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"Недопустимый протокол: {parsed.scheme}. Разрешены только http и https"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL не содержит hostname"

    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback or ip.is_link_local or ip.is_multicast:
            return False, f"Запрещённый IP-адрес: {hostname}"
        # Разрешаем приватные IP (принтеры в локальной сети) но блокируем metadata endpoints
        if ip == ipaddress.ip_address("169.254.169.254"):
            return False, "Запрещённый IP-адрес: cloud metadata endpoint"
    except ValueError:
        # hostname, не IP — блокируем DNS rebinding к localhost
        if hostname in ("localhost", "metadata.google.internal"):
            return False, f"Запрещённый hostname: {hostname}"

    return True, ""


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def save_web_parsing_rule(request):
    """Сохранение, обновление или удаление правила веб-парсинга"""
    data = json.loads(request.body)

    # Проверка на удаление
    if data.get("delete"):
        edit_id = data.get("edit_id")
        if edit_id:
            try:
                rule = WebParsingRule.objects.get(id=edit_id)
                rule.delete()
                return JsonResponse({"success": True, "message": "Правило удалено"})
            except WebParsingRule.DoesNotExist:
                return JsonResponse({"success": False, "error": "Правило не найдено"}, status=404)
        return JsonResponse({"success": False, "error": "Не указан ID правила для удаления"}, status=400)

    # Проверка на редактирование
    edit_id = data.get("edit_id")
    if edit_id and edit_id != 0:
        # Обновление существующего правила
        try:
            rule = WebParsingRule.objects.get(id=edit_id)
        except WebParsingRule.DoesNotExist:
            return JsonResponse({"success": False, "error": "Правило не найдено"}, status=404)
    else:
        # Создание нового правила
        rule = WebParsingRule(printer_id=data["printer_id"])

    # Обновление полей
    rule.protocol = data.get("protocol", "http")
    rule.url_path = data.get("url_path", "/")
    rule.field_name = data["field_name"]
    rule.xpath = data.get("xpath", "")
    rule.regex_pattern = data.get("regex", "")
    rule.regex_replacement = data.get("regex_replacement", "")
    rule.is_calculated = data.get("is_calculated", False)
    # Фронтенд отправляет selected_rules, сохраняем в source_rules
    rule.source_rules = data.get("selected_rules", data.get("source_rules", ""))
    rule.calculation_formula = data.get("calculation_formula", "")
    # actions может быть массивом, преобразуем в JSON строку
    actions = data.get("actions", data.get("actions_chain", ""))
    if isinstance(actions, list):
        rule.actions_chain = json.dumps(actions)
    elif isinstance(actions, str):
        rule.actions_chain = actions
    else:
        rule.actions_chain = ""

    rule.save()

    return JsonResponse({"success": True, "id": rule.id})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_web_parsing", raise_exception=True)
def get_rules(request, printer_id):
    """Получение списка правил для принтера"""
    printer = get_object_or_404(Printer, pk=printer_id)
    rules = WebParsingRule.objects.filter(printer=printer).order_by("field_name")

    rules_data = [
        {
            "id": rule.id,
            "field_name": rule.field_name,
            "xpath": rule.xpath,
            "regex": rule.regex_pattern,
            "is_calculated": rule.is_calculated,
            "calculation_formula": rule.calculation_formula,
            "selected_rules": rule.source_rules or "",
        }
        for rule in rules
    ]

    return JsonResponse({"rules": rules_data})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def test_xpath(request):
    """Тестирование XPath на странице"""
    data = json.loads(request.body)
    html_content = data.get("html")
    xpath_expr = data.get("xpath")

    try:
        tree = html.fromstring(html_content)
        result = tree.xpath(xpath_expr)

        if result:
            if isinstance(result, list):
                result_text = [r.text_content().strip() if hasattr(r, "text_content") else str(r) for r in result]
                raw_value = result_text[0] if result_text else ""
            else:
                raw_value = result.text_content().strip() if hasattr(result, "text_content") else str(result)
        else:
            return JsonResponse({"success": False, "error": "XPath не вернул результатов"}, status=400)

        return JsonResponse({"success": True, "raw_result": raw_value})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def fetch_page(request):
    """Загрузка веб-страницы принтера"""
    import time

    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC  # <-- Добавьте этот импорт
    from selenium.webdriver.support.ui import WebDriverWait

    from ..web_parser import create_selenium_driver

    data = json.loads(request.body)
    url = data.get("url")
    username = data.get("username", "")
    password = data.get("password", "")

    # Валидация URL (защита от SSRF)
    is_valid, error_msg = _validate_printer_url(url)
    if not is_valid:
        return JsonResponse({"success": False, "error": error_msg}, status=400)

    driver = None
    try:
        driver = create_selenium_driver()

        if username:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(url)
            url = urlunparse(
                (
                    parsed.scheme,
                    f"{username}:{password}@{parsed.netloc}",
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

        driver.get(url)

        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except Exception:
            pass

        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            time.sleep(1)
        except TimeoutException:
            pass

        page_source = driver.page_source
        final_url = driver.current_url

        # Сохраняем credentials в сессии для proxy_page (чтобы не передавать через GET)
        if username:
            request.session["_proxy_auth"] = {"url": final_url, "username": username, "password": password}
        else:
            request.session.pop("_proxy_auth", None)

        return JsonResponse({"success": True, "content": page_source, "url": final_url})

    except Exception as e:
        logger.error(f"Error in fetch_page: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "Ошибка загрузки страницы"}, status=400)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_web_parsing", raise_exception=True)
def proxy_page(request):
    """Прокси для отображения страницы принтера в iframe (быстрая версия через requests)"""
    import hashlib

    import requests
    import urllib3
    from requests.adapters import HTTPAdapter
    from requests.auth import HTTPBasicAuth
    from urllib3.util.ssl_ import create_urllib3_context

    from django.core.cache import cache

    # Отключаем предупреждения SSL
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Адаптер для старых SSL протоколов
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = create_urllib3_context()
            context.set_ciphers("DEFAULT@SECLEVEL=1")
            context.check_hostname = False
            context.verify_mode = 0
            kwargs["ssl_context"] = context
            return super().init_poolmanager(*args, **kwargs)

    url = request.GET.get("url")
    # Credentials читаем из сессии (сохраняются при fetch_page), не из GET-параметров
    username = ""
    password = ""
    proxy_auth = request.session.get("_proxy_auth")
    if proxy_auth and isinstance(proxy_auth, dict):
        from urllib.parse import urlparse

        # Проверяем что credentials относятся к тому же хосту
        stored_host = urlparse(proxy_auth.get("url", "")).netloc
        request_host = urlparse(url or "").netloc
        if stored_host and stored_host == request_host:
            username = proxy_auth.get("username", "")
            password = proxy_auth.get("password", "")

    if not url:
        return HttpResponse("URL not provided", status=400)

    # Валидация URL (защита от SSRF)
    is_valid, error_msg = _validate_printer_url(url)
    if not is_valid:
        return HttpResponse(f"Invalid URL: {error_msg}", status=400)

    logger.info(f"proxy_page called with URL: {url}")

    # Кеширование (5 минут)
    cache_key = hashlib.md5(f"{url}_{username}".encode()).hexdigest()
    cached_content = cache.get(f"proxy_page_{cache_key}")
    if cached_content:
        response = HttpResponse(cached_content, content_type="text/html; charset=utf-8")
        # КРИТИЧНО: Разрешаем отображение в iframe
        response["X-Frame-Options"] = "ALLOWALL"
        # Устанавливаем максимально разрешающий CSP для iframe
        response["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; connect-src *; frame-src *;"
        )
        return response

    try:
        # Создаём сессию с SSL адаптером
        session = requests.Session()
        session.mount("https://", SSLAdapter())
        session.mount("http://", SSLAdapter())

        # Аутентификация
        auth = None
        if username:
            auth = HTTPBasicAuth(username, password)

        # Загружаем страницу
        resp = session.get(
            url,
            timeout=10,
            verify=False,
            auth=auth,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": url.rsplit("/", 1)[0] + "/" if "/" in url.split("://")[-1] else url + "/",
            },
            allow_redirects=True,
        )

        # Получаем контент
        content = resp.content
        content_type = resp.headers.get("Content-Type", "text/html")

        # Модифицируем HTML для работы в iframe
        if "text/html" in content_type:
            try:
                content = content.decode("utf-8", errors="ignore")

                # Удаляем meta теги X-Frame-Options из HTML принтера (если есть)
                import re

                content = re.sub(
                    r'<meta\s+http-equiv=["\']?X-Frame-Options["\']?\s+content=["\']?[^"\']*["\']?\s*/?>',
                    "",
                    content,
                    flags=re.IGNORECASE,
                )

                # Добавляем base tag для корректной загрузки ресурсов
                base_url = url.rsplit("/", 1)[0] if "/" in url.split("://")[-1] else url
                base_tag = f'<base href="{base_url}/">'

                # Скрипт для подавления ошибок в консоли
                script_inject = "<script>window.console.error = function() {};</script>"

                if "<head>" in content:
                    content = content.replace("<head>", f"<head>{base_tag}{script_inject}", 1)
                elif "<HEAD>" in content:
                    content = content.replace("<HEAD>", f"<HEAD>{base_tag}{script_inject}", 1)
                else:
                    content = base_tag + script_inject + content

                content = content.encode("utf-8")
            except Exception:
                pass

        # Кешируем на 5 минут
        cache.set(f"proxy_page_{cache_key}", content, 300)

        response = HttpResponse(content, content_type=content_type)
        # КРИТИЧНО: Разрешаем отображение в iframe
        response["X-Frame-Options"] = "ALLOWALL"
        # Устанавливаем максимально разрешающий CSP для iframe
        response["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; connect-src *; frame-src *;"
        )
        return response

    except Exception as e:
        import traceback

        logger.error(f"Error in proxy_page: {traceback.format_exc()}")
        return HttpResponse(f"Error loading page: {str(e)}", status=500)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def execute_action(request):
    """Выполнение цепочки действий и получение HTML"""
    import time

    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    from ..web_parser import apply_regex_processing, create_selenium_driver

    data = json.loads(request.body)
    url = data.get("url")
    actions = data.get("actions", [])
    username = data.get("username", "")
    password = data.get("password", "")

    # Валидация URL (защита от SSRF)
    is_valid, error_msg = _validate_printer_url(url)
    if not is_valid:
        return JsonResponse({"success": False, "error": error_msg}, status=400)

    driver = None
    try:
        driver = create_selenium_driver()

        if username:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(url)
            url = urlunparse(
                (
                    parsed.scheme,
                    f"{username}:{password}@{parsed.netloc}",
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

        driver.get(url)

        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except Exception:
            pass

        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            time.sleep(1)
        except TimeoutException:
            pass

        action_log = []
        parsed_results = {}

        def get_selector_type(selector):
            """Определяет тип селектора: XPath или CSS"""
            if not selector:
                return By.CSS_SELECTOR
            # XPath обычно начинается с / или // или содержит специфичные символы
            if selector.startswith("/") or selector.startswith("("):
                return By.XPATH
            # Проверка на XPath функции и оси
            xpath_indicators = [
                "[",
                "@",
                "contains(",
                "text()",
                "following-sibling",
                "preceding-sibling",
                "ancestor",
                "descendant",
                "parent",
                "child",
            ]
            if any(indicator in selector for indicator in xpath_indicators):
                return By.XPATH
            return By.CSS_SELECTOR

        from html import escape as html_escape

        for action in actions:
            action_type = action.get("type")
            selector = action.get("selector")
            value = action.get("value", "")
            wait = action.get("wait", 1)

            # Экранируем пользовательские значения для защиты от XSS (v-html на фронте)
            safe_selector = html_escape(str(selector)) if selector else ""
            safe_value = html_escape(str(value)) if value else ""

            try:
                if action_type == "click":
                    selector_type = get_selector_type(selector)
                    element = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((selector_type, selector)))
                    element.click()
                    action_log.append(f"✓ Click: {safe_selector}")
                    time.sleep(wait)
                    time.sleep(1)

                    try:
                        WebDriverWait(driver, 5).until(
                            lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
                        )
                    except Exception:
                        pass

                elif action_type == "send_keys":
                    selector_type = get_selector_type(selector)
                    element = WebDriverWait(driver, 15).until(EC.presence_of_element_located((selector_type, selector)))
                    element.clear()
                    element.send_keys(value)
                    action_log.append(f"✓ Input: {safe_selector} = {safe_value}")
                    time.sleep(wait)

                elif action_type == "wait":
                    time.sleep(wait)
                    action_log.append(f"✓ Wait: {wait}s")

                elif action_type == "parse":
                    xpath_expr = action.get("xpath")
                    regex_pattern = action.get("regex", "")
                    var_name = action.get("var_name", "parsed_value")
                    safe_xpath = html_escape(str(xpath_expr)) if xpath_expr else ""
                    safe_var = html_escape(str(var_name)) if var_name else ""

                    time.sleep(1)

                    tree = html.fromstring(driver.page_source)
                    result = tree.xpath(xpath_expr)

                    if result:
                        if isinstance(result, list):
                            raw_value = (
                                result[0].text_content().strip()
                                if hasattr(result[0], "text_content")
                                else str(result[0])
                            )
                        else:
                            raw_value = (
                                result.text_content().strip() if hasattr(result, "text_content") else str(result)
                            )

                        processed_value = apply_regex_processing(raw_value, regex_pattern, "")
                        parsed_results[var_name] = processed_value
                        safe_processed = html_escape(str(processed_value))
                        action_log.append(f"✓ Parse: {safe_xpath} = {safe_processed} (as {safe_var})")
                    else:
                        action_log.append(f"✗ Parse: {safe_xpath} - не найдено")
                        parsed_results[var_name] = ""

            except Exception as e:
                safe_error = html_escape(str(e))
                action_log.append(f"✗ Error on {action_type}: {safe_error}")
                return JsonResponse({"success": False, "error": str(e), "action_log": action_log}, status=400)

        page_source = driver.page_source
        final_url = driver.current_url

        return JsonResponse(
            {
                "success": True,
                "html": page_source,
                "url": final_url,
                "action_log": action_log,
                "parsed_results": parsed_results,
            }
        )

    except Exception as e:
        import traceback

        logger.error(f"Error in execute_action: {traceback.format_exc()}")
        return JsonResponse({"success": False, "error": str(e)}, status=400)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.view_printer", raise_exception=True)
def export_printer_xml(request, printer_id):
    """Экспорт данных принтера в XML формат для GLPI"""
    from ..web_parser import export_to_xml

    printer = get_object_or_404(Printer, pk=printer_id)

    results = {
        "serial_number": printer.serial_number,
        "mac_address": printer.mac_address,
        "counter": getattr(printer, "counter", 0),
        "counter_a4_bw": getattr(printer, "counter_a4_bw", 0),
        "counter_a3_bw": getattr(printer, "counter_a3_bw", 0),
        "counter_a4_color": getattr(printer, "counter_a4_color", 0),
        "counter_a3_color": getattr(printer, "counter_a3_color", 0),
    }

    xml_content = export_to_xml(printer, results)

    response = HttpResponse(xml_content, content_type="application/xml")
    response["Content-Disposition"] = f'attachment; filename="{printer.serial_number}_export.xml"'

    return response


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def save_template(request):
    """Сохранение правил как шаблона"""
    data = json.loads(request.body)

    printer_id = data.get("printer_id")
    template_name = data.get("template_name")
    description = data.get("description", "")
    is_public = data.get("is_public", False)

    printer = get_object_or_404(Printer, pk=printer_id)

    if not printer.device_model:
        return JsonResponse({"success": False, "error": "У принтера не указана модель оборудования"}, status=400)

    # Получаем все правила принтера
    rules = WebParsingRule.objects.filter(printer=printer)

    if not rules.exists():
        return JsonResponse({"success": False, "error": "Нет правил для сохранения"}, status=400)

    # Формируем конфигурацию
    rules_config = []
    for rule in rules:
        rule_data = {
            "protocol": rule.protocol,
            "url_path": rule.url_path,
            "field_name": rule.field_name,
            "xpath": rule.xpath,
            "regex_pattern": rule.regex_pattern,
            "regex_replacement": rule.regex_replacement,
            "is_calculated": rule.is_calculated,
            "actions_chain": rule.actions_chain,
        }

        if rule.is_calculated:
            rule_data["source_rules_fields"] = []
            if rule.source_rules:
                source_ids = json.loads(rule.source_rules)
                for sid in source_ids:
                    src_rule = rules.filter(id=sid).first()
                    if src_rule:
                        rule_data["source_rules_fields"].append(src_rule.field_name)

            rule_data["calculation_formula"] = rule.calculation_formula

        rules_config.append(rule_data)

    # Создаем шаблон
    from ..models import WebParsingTemplate

    template = WebParsingTemplate.objects.create(
        name=template_name,
        device_model=printer.device_model,
        description=description,
        rules_config=rules_config,
        created_by=request.user,
        is_public=is_public and request.user.has_perm("inventory.can_create_public_templates"),
    )

    return JsonResponse({"success": True, "template_id": template.id, "message": f'Шаблон "{template_name}" сохранен'})


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def get_templates(request):
    """Получение доступных шаблонов"""
    from ..models import WebParsingTemplate

    device_model_id = request.GET.get("device_model_id")

    if not device_model_id:
        return JsonResponse({"templates": []})

    # Публичные шаблоны + шаблоны текущего пользователя
    templates = (
        WebParsingTemplate.objects.filter(device_model_id=device_model_id)
        .filter(models.Q(is_public=True) | models.Q(created_by=request.user))
        .values("id", "name", "description", "created_at", "created_by__username", "usage_count", "is_public")
    )

    return JsonResponse({"templates": list(templates)})


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def get_all_templates(request):
    """Получение всех доступных шаблонов"""
    from ..models import WebParsingTemplate

    templates = WebParsingTemplate.objects.all().order_by("name").values("id", "name", "description")

    return JsonResponse({"templates": list(templates)})


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def apply_template(request):
    """Применение шаблона к принтеру"""
    from ..models import WebParsingTemplate

    data = json.loads(request.body)
    printer_id = data.get("printer_id")
    template_id = data.get("template_id")
    overwrite = data.get("overwrite", False)

    printer = get_object_or_404(Printer, pk=printer_id)
    template = get_object_or_404(WebParsingTemplate, pk=template_id)

    # Проверяем совместимость
    if printer.device_model_id != template.device_model_id:
        return JsonResponse(
            {
                "success": False,
                "error": f"Шаблон для модели {template.device_model}, а принтер - {printer.device_model}",
            },
            status=400,
        )

    # Удаляем старые правила если нужно
    if overwrite:
        WebParsingRule.objects.filter(printer=printer).delete()

    # Применяем правила из шаблона
    rules_config = template.rules_config
    created_rules = {}  # field_name -> rule_id для вычисляемых полей

    # Сначала создаем обычные правила
    for rule_data in rules_config:
        if rule_data.get("is_calculated"):
            continue

        rule = WebParsingRule.objects.create(
            printer=printer,
            protocol=rule_data["protocol"],
            url_path=rule_data["url_path"],
            field_name=rule_data["field_name"],
            xpath=rule_data.get("xpath", ""),
            regex_pattern=rule_data.get("regex_pattern", ""),
            regex_replacement=rule_data.get("regex_replacement", ""),
            actions_chain=rule_data.get("actions_chain", ""),
            is_calculated=False,
        )

        created_rules[rule_data["field_name"]] = rule.id

    # Потом создаем вычисляемые правила
    for rule_data in rules_config:
        if not rule_data.get("is_calculated"):
            continue

        # Преобразуем field_name в ID
        source_fields = rule_data.get("source_rules_fields", [])
        source_ids = [created_rules[field] for field in source_fields if field in created_rules]

        WebParsingRule.objects.create(
            printer=printer,
            protocol=rule_data["protocol"],
            url_path=rule_data["url_path"],
            field_name=rule_data["field_name"],
            is_calculated=True,
            source_rules=json.dumps(source_ids),
            calculation_formula=rule_data.get("calculation_formula", ""),
        )

    # Увеличиваем счетчик использования
    template.usage_count += 1
    template.save(update_fields=["usage_count"])

    return JsonResponse(
        {"success": True, "message": f'Применено {len(rules_config)} правил из шаблона "{template.name}"'}
    )


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_http_methods(["DELETE"])
def delete_template(request, template_id):
    """Удаление шаблона"""
    from ..models import WebParsingTemplate

    template = get_object_or_404(WebParsingTemplate, pk=template_id)

    # Проверяем права
    if not template.created_by == request.user and not request.user.is_superuser:
        return JsonResponse({"success": False, "error": "Вы можете удалять только свои шаблоны"}, status=403)

    template.delete()

    return JsonResponse({"success": True, "message": "Шаблон удален"})
