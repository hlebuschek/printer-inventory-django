# inventory/views/web_parser_views.py

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import Printer, WebParsingRule
from ..web_parser import create_selenium_driver
from lxml import html
import json
from django.core.cache import cache
import hashlib
from django.http import HttpResponse

@login_required
@permission_required("inventory.change_printer", raise_exception=True)
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
@permission_required("inventory.change_printer", raise_exception=True)
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
@permission_required("inventory.change_printer", raise_exception=True)
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
                result_text = [r.text_content().strip() if hasattr(r, 'text_content') else str(r) for r in result]
                raw_value = result_text[0] if result_text else ''
            else:
                raw_value = result.text_content().strip() if hasattr(result, 'text_content') else str(result)
        else:
            return JsonResponse({'success': False, 'error': 'XPath не вернул результатов'}, status=400)

        return JsonResponse({'success': True, 'raw_result': raw_value})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@permission_required("inventory.change_printer", raise_exception=True)
@require_POST
def fetch_page(request):
    """Загрузка веб-страницы принтера"""
    from ..web_parser import create_selenium_driver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
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

        # Шаг 1: Ждем document.readyState === 'complete'
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        # Шаг 2: Ждем завершения jQuery AJAX (если есть jQuery)
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except:
            pass

        # Шаг 3: Даем дополнительное время на рендеринг
        time.sleep(2)

        # Шаг 4: Проверяем наличие таблицы с данными (специфично для Flask приложения)
        try:
            # Ждем появления строк таблицы (tbody tr)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            # Дополнительное ожидание для полной загрузки всех строк
            time.sleep(1)
        except TimeoutException:
            # Если таблица не появилась, но страница загрузилась - продолжаем
            pass

        # Шаг 5: Ждем что body содержит контент
        try:
            WebDriverWait(driver, 5).until(
                lambda d: len(d.find_element(By.TAG_NAME, 'body').text.strip()) > 100
            )
        except:
            pass

        # Финальная пауза для стабильности
        time.sleep(1)

        page_source = driver.page_source
        final_url = driver.current_url
        # Отладочная информация
        print(f"=== DEBUG fetch_page ===")
        print(f"URL: {final_url}")
        print(f"Page title: {driver.title}")
        print(f"Body length: {len(page_source)}")

        # Проверяем наличие таблицы в HTML
        if 'tbody' in page_source:
            print("✓ Table body found in HTML")
        else:
            print("✗ Table body NOT found in HTML")

        # Проверяем JavaScript ошибки
        js_errors = driver.execute_script("return window.jsErrors || []")
        if js_errors:
            print(f"JavaScript errors: {js_errors}")
        print("======================")

        return JsonResponse({
            'success': True,
            'content': page_source,
            'url': final_url
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in fetch_page: {error_details}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.change_printer", raise_exception=True)
def proxy_page(request):
    """Прокси для отображения страницы принтера в iframe с кешированием"""
    from django.http import HttpResponse
    from ..web_parser import create_selenium_driver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException
    import time

    url = request.GET.get('url')
    username = request.GET.get('username', '')
    password = request.GET.get('password', '')

    if not url:
        return HttpResponse("URL not provided", status=400)

    # Создаем ключ кеша
    import hashlib
    cache_key = hashlib.md5(f"{url}_{username}".encode()).hexdigest()

    # Проверяем кеш (кешируем на 60 секунд)
    from django.core.cache import cache
    cached_content = cache.get(f'proxy_page_{cache_key}')
    if cached_content:
        return HttpResponse(
            cached_content,
            content_type='text/html; charset=utf-8',
            headers={
                'X-Frame-Options': 'ALLOWALL',
                'Content-Security-Policy': ''
            }
        )

    driver = None
    try:
        driver = create_selenium_driver()

        # Аутентификация если нужна
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

        # Умное ожидание загрузки страницы
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        # Ждем завершения jQuery AJAX
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return typeof jQuery === "undefined" || jQuery.active === 0')
            )
        except:
            pass

        time.sleep(3)  # Увеличили паузу

        # Ждем появления таблицы если это главная страница
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            time.sleep(2)  # Дополнительная пауза после загрузки таблицы
        except TimeoutException:
            pass

        # Получаем HTML после выполнения JavaScript
        page_source = driver.page_source

        # Модифицируем HTML для работы в iframe
        content = page_source

        # Добавляем base tag для корректной загрузки ресурсов
        base_url = url.rsplit('/', 1)[0] if '/' in url.split('://')[-1] else url
        base_tag = f'<base href="{base_url}/">'

        # Убираем сообщение об ошибке из HTML
        content = content.replace('Ошибка загрузки принтеров', 'Загрузка данных...')

        # Скрываем console.error в iframe
        script_inject = '''
        <script>
        // Перехватываем console.error чтобы не показывать в iframe
        window.console.error = function() {};
        </script>
        '''

        if '<head>' in content.lower():
            content = content.replace('<head>', f'<head>{base_tag}{script_inject}', 1)
            content = content.replace('<HEAD>', f'<HEAD>{base_tag}{script_inject}', 1)
        else:
            content = base_tag + script_inject + content

        # Сохраняем в кеш на 60 секунд
        cache.set(f'proxy_page_{cache_key}', content, 60)

        http_response = HttpResponse(
            content,
            content_type='text/html; charset=utf-8'
        )

        # Разрешаем отображение в iframe
        http_response['X-Frame-Options'] = 'ALLOWALL'
        http_response['Content-Security-Policy'] = ''

        return http_response

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in proxy_page: {error_details}")
        return HttpResponse(f"Error loading page: {str(e)}", status=500)

    finally:
        if driver:
            driver.quit()


@login_required
@permission_required("inventory.change_printer", raise_exception=True)
@require_POST
def execute_action(request):
    """Выполнение цепочки действий и получение HTML"""
    from ..web_parser import create_selenium_driver
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

        # Аутентификация если нужна
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

        # Умное ожидание загрузки страницы
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

        # Ждем появления таблицы если это главная страница
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr"))
            )
            time.sleep(1)
        except TimeoutException:
            pass

        # Выполняем действия по очереди
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

                    # После клика ждем загрузки нового контента
                    time.sleep(1)

                    # Ждем завершения AJAX после клика
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

                    # Даем время на рендеринг
                    time.sleep(1)

                    tree = html.fromstring(driver.page_source)
                    result = tree.xpath(xpath_expr)

                    if result:
                        if isinstance(result, list):
                            raw_value = result[0].text_content().strip() if hasattr(result[0], 'text_content') else str(
                                result[0])
                        else:
                            raw_value = result.text_content().strip() if hasattr(result, 'text_content') else str(
                                result)

                        # Применяем regex если есть
                        from ..web_parser import apply_regex_processing
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

        # Получаем финальный HTML
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
        error_details = traceback.format_exc()
        print(f"Error in execute_action: {error_details}")
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

    # Собираем результаты из текущих значений принтера
    results = {
        'serial_number': printer.serial_number,
        'mac_address': printer.mac_address,
        'counter': printer.counter,
        'counter_a4_bw': printer.counter_a4_bw,
        'counter_a3_bw': printer.counter_a3_bw,
        'counter_a4_color': printer.counter_a4_color,
        'counter_a3_color': printer.counter_a3_color,
    }

    # Генерируем XML
    xml_content = export_to_xml(printer, results)

    # Возвращаем как файл для скачивания
    response = HttpResponse(xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{printer.serial_number}_export.xml"'

    return response