# inventory/views/web_parser_views.py

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
from ..models import Printer, WebParsingRule
from ..web_parser import create_selenium_driver, export_to_xml, execute_web_parsing
from lxml import html
import json
import os
import logging
from django.db import models

logger = logging.getLogger(__name__)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def web_parser_setup(request, printer_id):
    """Страница настройки веб-парсинга для принтера"""
    printer = get_object_or_404(Printer, pk=printer_id)
    rules = WebParsingRule.objects.filter(printer=printer).order_by('id')

    rules_data = [
        {
            'id': r.id,
            'protocol': r.protocol,
            'url_path': r.url_path,
            'field_name': r.field_name,
            'xpath': r.xpath,
            'regex_pattern': r.regex_pattern,
            'regex_replacement': r.regex_replacement,
            'is_calculated': r.is_calculated,
            'source_rules': r.source_rules,
            'calculation_formula': r.calculation_formula,
            'actions_chain': r.actions_chain
        } for r in rules
    ]

    return render(request, 'inventory/web_parser_setup.html', {
        'printer': printer,
        'rules': rules,
        'rules_data': json.dumps(rules_data)
    })


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def save_web_parsing_rule(request):
    """Сохранение правила веб-парсинга"""
    data = json.loads(request.body)

    rule = WebParsingRule(
        printer_id=data['printer_id'],
        protocol=data['protocol'],
        url_path=data['url_path'],
        field_name=data['field_name'],
        xpath=data.get('xpath', ''),
        regex_pattern=data.get('regex_pattern', ''),
        regex_replacement=data.get('regex_replacement', ''),
        is_calculated=data.get('is_calculated', False),
        source_rules=data.get('source_rules', ''),
        calculation_formula=data.get('calculation_formula', ''),
        actions_chain=data.get('actions_chain', '')
    )
    rule.save()

    return JsonResponse({'success': True, 'id': rule.id})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_web_parsing", raise_exception=True)
def get_rules(request, printer_id):
    """Получение списка правил для принтера"""
    printer = get_object_or_404(Printer, pk=printer_id)
    rules = WebParsingRule.objects.filter(printer=printer).order_by('field_name')

    rules_data = [
        {
            'id': rule.id,
            'field_name': rule.field_name,
            'xpath': rule.xpath,
            'regex': rule.regex_pattern,
            'is_calculated': rule.is_calculated,
            'calculation_formula': rule.calculation_formula,
            'selected_rules': rule.source_rules or '',
        }
        for rule in rules
    ]

    return JsonResponse({'rules': rules_data})


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def test_xpath(request):
    """Тестирование XPath на странице"""
    data = json.loads(request.body)
    html_content = data.get('html')
    xpath_expr = data.get('xpath')

    try:
        tree = html.fromstring(html_content)
        result = tree.xpath(xpath_expr)

        if result:
            if isinstance(result, list):
                result_text = [
                    r.text_content().strip() if hasattr(r, 'text_content') else str(r)
                    for r in result
                ]
                raw_value = result_text[0] if result_text else ''
            else:
                raw_value = result.text_content().strip() if hasattr(result, 'text_content') else str(result)
        else:
            return JsonResponse({
                'success': False,
                'error': 'XPath не вернул результатов'
            }, status=400)

        return JsonResponse({'success': True, 'raw_result': raw_value})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def fetch_page(request):
    """Загрузка веб-страницы принтера"""
    from ..web_parser import create_selenium_driver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC  # <-- Добавьте этот импорт
    from selenium.common.exceptions import TimeoutException
    import time

    data = json.loads(request.body)
    url = data.get('url')
    username = data.get('username', '')
    password = data.get('password', '')

    driver = None
    try:
        driver = create_selenium_driver()

        if username:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            url = urlunparse((
                parsed.scheme,
                f"{username}:{password}@{parsed.netloc}",
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))

        driver.get(url)

        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except:
            pass

        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            time.sleep(1)
        except TimeoutException:
            pass

        page_source = driver.page_source
        final_url = driver.current_url

        return JsonResponse({
            'success': True,
            'content': page_source,
            'url': final_url
        })

    except Exception as e:
        import traceback
        logger.error(f"Error in fetch_page: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.view_web_parsing", raise_exception=True)
@xframe_options_exempt
def proxy_page(request):
    """Прокси для отображения страницы принтера в iframe"""
    from ..web_parser import create_selenium_driver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    import time
    import hashlib
    from django.core.cache import cache

    url = request.GET.get('url')
    username = request.GET.get('username', '')
    password = request.GET.get('password', '')

    if not url:
        return HttpResponse("URL not provided", status=400)

    # Кеширование
    cache_key = hashlib.md5(f"{url}_{username}".encode()).hexdigest()
    cached_content = cache.get(f'proxy_page_{cache_key}')
    if cached_content:
        response = HttpResponse(
            cached_content,
            content_type='text/html; charset=utf-8'
        )
        # Разрешаем отображение в iframe (декоратор @xframe_options_exempt уже делает это)
        return response

    driver = None
    try:
        driver = create_selenium_driver()

        if username:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            url = urlunparse((
                parsed.scheme,
                f"{username}:{password}@{parsed.netloc}",
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))

        driver.get(url)

        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except:
            pass

        time.sleep(3)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            time.sleep(2)
        except TimeoutException:
            pass

        page_source = driver.page_source
        content = page_source

        base_url = url.rsplit('/', 1)[0] if '/' in url.split('://')[-1] else url
        base_tag = f'<base href="{base_url}/">'

        script_inject = '''
        <script>
        window.console.error = function() {};
        </script>
        '''

        if '<head>' in content.lower():
            content = content.replace('<head>', f'<head>{base_tag}{script_inject}', 1)
            content = content.replace('<HEAD>', f'<HEAD>{base_tag}{script_inject}', 1)
        else:
            content = base_tag + script_inject + content

        cache.set(f'proxy_page_{cache_key}', content, 60)

        response = HttpResponse(
            content,
            content_type='text/html; charset=utf-8'
        )
        # Декоратор @xframe_options_exempt автоматически разрешает отображение в iframe

        return response

    except Exception as e:
        import traceback
        logger.error(f"Error in proxy_page: {traceback.format_exc()}")
        return HttpResponse(f"Error loading page: {str(e)}", status=500)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.access_inventory_app", raise_exception=True)
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def execute_action(request):
    """Выполнение цепочки действий и получение HTML"""
    from ..web_parser import create_selenium_driver, apply_regex_processing
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    import time

    data = json.loads(request.body)
    url = data.get('url')
    actions = data.get('actions', [])
    username = data.get('username', '')
    password = data.get('password', '')

    driver = None
    try:
        driver = create_selenium_driver()

        if username:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            url = urlunparse((
                parsed.scheme,
                f"{username}:{password}@{parsed.netloc}",
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))

        driver.get(url)

        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except:
            pass

        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            time.sleep(1)
        except TimeoutException:
            pass

        action_log = []
        parsed_results = {}

        for action in actions:
            action_type = action.get('type')
            selector = action.get('selector')
            value = action.get('value', '')
            wait = action.get('wait', 1)

            try:
                if action_type == 'click':
                    element = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    element.click()
                    action_log.append(f"✓ Click: {selector}")
                    time.sleep(wait)
                    time.sleep(1)

                    try:
                        WebDriverWait(driver, 5).until(
                            lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
                        )
                    except:
                        pass

                elif action_type == 'send_keys':
                    element = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    element.clear()
                    element.send_keys(value)
                    action_log.append(f"✓ Input: {selector} = {value}")
                    time.sleep(wait)

                elif action_type == 'wait':
                    time.sleep(wait)
                    action_log.append(f"✓ Wait: {wait}s")

                elif action_type == 'parse':
                    xpath_expr = action.get('xpath')
                    regex_pattern = action.get('regex', '')
                    var_name = action.get('var_name', 'parsed_value')

                    time.sleep(1)

                    tree = html.fromstring(driver.page_source)
                    result = tree.xpath(xpath_expr)

                    if result:
                        if isinstance(result, list):
                            raw_value = result[0].text_content().strip() if hasattr(result[0], 'text_content') else str(result[0])
                        else:
                            raw_value = result.text_content().strip() if hasattr(result, 'text_content') else str(result)

                        processed_value = apply_regex_processing(raw_value, regex_pattern, '')
                        parsed_results[var_name] = processed_value
                        action_log.append(f"✓ Parse: {xpath_expr} = {processed_value} (as {var_name})")
                    else:
                        action_log.append(f"✗ Parse: {xpath_expr} - не найдено")
                        parsed_results[var_name] = ''

            except Exception as e:
                action_log.append(f"✗ Error on {action_type}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                    'action_log': action_log
                }, status=400)

        page_source = driver.page_source
        final_url = driver.current_url

        return JsonResponse({
            'success': True,
            'html': page_source,
            'url': final_url,
            'action_log': action_log,
            'parsed_results': parsed_results
        })

    except Exception as e:
        import traceback
        logger.error(f"Error in execute_action: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

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
        'serial_number': printer.serial_number,
        'mac_address': printer.mac_address,
        'counter': getattr(printer, 'counter', 0),
        'counter_a4_bw': getattr(printer, 'counter_a4_bw', 0),
        'counter_a3_bw': getattr(printer, 'counter_a3_bw', 0),
        'counter_a4_color': getattr(printer, 'counter_a4_color', 0),
        'counter_a3_color': getattr(printer, 'counter_a3_color', 0),
    }

    xml_content = export_to_xml(printer, results)

    response = HttpResponse(xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{printer.serial_number}_export.xml"'

    return response


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def save_template(request):
    """Сохранение правил как шаблона"""
    data = json.loads(request.body)

    printer_id = data.get('printer_id')
    template_name = data.get('template_name')
    description = data.get('description', '')
    is_public = data.get('is_public', False)

    printer = get_object_or_404(Printer, pk=printer_id)

    if not printer.device_model:
        return JsonResponse({
            'success': False,
            'error': 'У принтера не указана модель оборудования'
        }, status=400)

    # Получаем все правила принтера
    rules = WebParsingRule.objects.filter(printer=printer)

    if not rules.exists():
        return JsonResponse({
            'success': False,
            'error': 'Нет правил для сохранения'
        }, status=400)

    # Формируем конфигурацию
    rules_config = []
    for rule in rules:
        rule_data = {
            'protocol': rule.protocol,
            'url_path': rule.url_path,
            'field_name': rule.field_name,
            'xpath': rule.xpath,
            'regex_pattern': rule.regex_pattern,
            'regex_replacement': rule.regex_replacement,
            'is_calculated': rule.is_calculated,
            'actions_chain': rule.actions_chain,
        }

        if rule.is_calculated:
            rule_data['source_rules_fields'] = []
            if rule.source_rules:
                source_ids = json.loads(rule.source_rules)
                for sid in source_ids:
                    src_rule = rules.filter(id=sid).first()
                    if src_rule:
                        rule_data['source_rules_fields'].append(src_rule.field_name)

            rule_data['calculation_formula'] = rule.calculation_formula

        rules_config.append(rule_data)

    # Создаем шаблон
    from ..models import WebParsingTemplate

    template = WebParsingTemplate.objects.create(
        name=template_name,
        device_model=printer.device_model,
        description=description,
        rules_config=rules_config,
        created_by=request.user,
        is_public=is_public and request.user.has_perm('inventory.can_create_public_templates')
    )

    return JsonResponse({
        'success': True,
        'template_id': template.id,
        'message': f'Шаблон "{template_name}" сохранен'
    })


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def get_templates(request):
    """Получение доступных шаблонов"""
    from ..models import WebParsingTemplate

    device_model_id = request.GET.get('device_model_id')

    if not device_model_id:
        return JsonResponse({'templates': []})

    # Публичные шаблоны + шаблоны текущего пользователя
    templates = WebParsingTemplate.objects.filter(
        device_model_id=device_model_id
    ).filter(
        models.Q(is_public=True) | models.Q(created_by=request.user)
    ).values(
        'id', 'name', 'description', 'created_at',
        'created_by__username', 'usage_count', 'is_public'
    )

    return JsonResponse({
        'templates': list(templates)
    })


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
def get_all_templates(request):
    """Получение всех доступных шаблонов"""
    from ..models import WebParsingTemplate

    templates = WebParsingTemplate.objects.all().order_by('name').values('id', 'name', 'description')

    return JsonResponse({
        'templates': list(templates)
    })


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def apply_template(request):
    """Применение шаблона к принтеру"""
    from ..models import WebParsingTemplate

    data = json.loads(request.body)
    printer_id = data.get('printer_id')
    template_id = data.get('template_id')
    overwrite = data.get('overwrite', False)

    printer = get_object_or_404(Printer, pk=printer_id)
    template = get_object_or_404(WebParsingTemplate, pk=template_id)

    # Проверяем совместимость
    if printer.device_model_id != template.device_model_id:
        return JsonResponse({
            'success': False,
            'error': f'Шаблон для модели {template.device_model}, а принтер - {printer.device_model}'
        }, status=400)

    # Удаляем старые правила если нужно
    if overwrite:
        WebParsingRule.objects.filter(printer=printer).delete()

    # Применяем правила из шаблона
    rules_config = template.rules_config
    created_rules = {}  # field_name -> rule_id для вычисляемых полей

    # Сначала создаем обычные правила
    for rule_data in rules_config:
        if rule_data.get('is_calculated'):
            continue

        rule = WebParsingRule.objects.create(
            printer=printer,
            protocol=rule_data['protocol'],
            url_path=rule_data['url_path'],
            field_name=rule_data['field_name'],
            xpath=rule_data.get('xpath', ''),
            regex_pattern=rule_data.get('regex_pattern', ''),
            regex_replacement=rule_data.get('regex_replacement', ''),
            actions_chain=rule_data.get('actions_chain', ''),
            is_calculated=False
        )

        created_rules[rule_data['field_name']] = rule.id

    # Потом создаем вычисляемые правила
    for rule_data in rules_config:
        if not rule_data.get('is_calculated'):
            continue

        # Преобразуем field_name в ID
        source_fields = rule_data.get('source_rules_fields', [])
        source_ids = [created_rules[field] for field in source_fields if field in created_rules]

        WebParsingRule.objects.create(
            printer=printer,
            protocol=rule_data['protocol'],
            url_path=rule_data['url_path'],
            field_name=rule_data['field_name'],
            is_calculated=True,
            source_rules=json.dumps(source_ids),
            calculation_formula=rule_data.get('calculation_formula', '')
        )

    # Увеличиваем счетчик использования
    template.usage_count += 1
    template.save(update_fields=['usage_count'])

    return JsonResponse({
        'success': True,
        'message': f'Применено {len(rules_config)} правил из шаблона "{template.name}"'
    })


@login_required
@permission_required("inventory.manage_web_parsing", raise_exception=True)
@require_POST
def delete_template(request, template_id):
    """Удаление шаблона"""
    from ..models import WebParsingTemplate

    template = get_object_or_404(WebParsingTemplate, pk=template_id)

    # Проверяем права
    if not template.created_by == request.user and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'error': 'Вы можете удалять только свои шаблоны'
        }, status=403)

    template.delete()

    return JsonResponse({
        'success': True,
        'message': 'Шаблон удален'
    })
