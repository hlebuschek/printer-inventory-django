"""
Django management команда для тестирования ОБОИХ полей поиска в GLPI.

Показывает результаты поиска по:
1. Стандартному полю 'serial'
2. Кастомному полю 'serialnumberonlabelfield'

Использование:
    python manage.py test_glpi_fields <serial_number>

Пример:
    python manage.py test_glpi_fields 399921100163
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from integrations.glpi.client import GLPIClient, GLPIAPIError
import requests
import json


class Command(BaseCommand):
    help = 'Тестирование поиска в ОБОИХ полях GLPI (стандартном и кастомном)'

    def add_arguments(self, parser):
        parser.add_argument(
            'serial_number',
            type=str,
            help='Серийный номер принтера для поиска'
        )

    def handle(self, *args, **options):
        serial_number = options['serial_number']

        self.stdout.write("=" * 80)
        self.stdout.write(f"ДЕТАЛЬНОЕ ТЕСТИРОВАНИЕ ПОЛЕЙ GLPI: {serial_number}")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        try:
            with GLPIClient() as client:
                self.stdout.write(self.style.SUCCESS(f"✓ Подключение к GLPI: {client.url}"))
                self.stdout.write(f"  SSL Verification: {client.verify_ssl}")
                self.stdout.write("")

                # ===================================================================
                # ТЕСТ 1: Стандартное поле 'serial'
                # ===================================================================
                self.stdout.write("─" * 80)
                self.stdout.write("ТЕСТ 1: Стандартное поле 'serial' (field ID=5)")
                self.stdout.write("─" * 80)
                self.stdout.write("")

                serial_field_id = getattr(settings, 'GLPI_SERIAL_FIELD_ID', '5')
                query_params = {
                    'criteria[0][field]': serial_field_id,
                    'criteria[0][searchtype]': 'contains',
                    'criteria[0][value]': serial_number,
                    'forcedisplay[0]': '2',   # ID
                    'forcedisplay[1]': '1',   # name
                    'forcedisplay[2]': '5',   # serial
                    'forcedisplay[3]': '23',  # manufacturer
                    'forcedisplay[4]': '31',  # states_name
                }

                self.stdout.write(f"Запрос: {client.url}/search/Printer")
                self.stdout.write(f"Field ID: {serial_field_id}")
                self.stdout.write(f"Значение: {serial_number}")
                self.stdout.write("")

                response = requests.get(
                    f"{client.url}/search/Printer",
                    headers=client._get_headers(with_session=True),
                    params=query_params,
                    timeout=15,
                    verify=client.verify_ssl
                )

                if response.status_code == 200:
                    data = response.json()
                    total_count = data.get('totalcount', 0)
                    items = data.get('data', [])

                    if total_count > 0:
                        self.stdout.write(self.style.SUCCESS(f"✓ Найдено: {total_count}"))
                        self.stdout.write("")
                        for item in items:
                            self._display_printer(item)
                    else:
                        self.stdout.write(self.style.WARNING("⚠ НЕ найдено в стандартном поле"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ Ошибка: HTTP {response.status_code}"))

                self.stdout.write("")

                # ===================================================================
                # ТЕСТ 2: Кастомное поле 'serialnumberonlabelfield'
                # ===================================================================
                self.stdout.write("─" * 80)
                self.stdout.write("ТЕСТ 2: Кастомное поле 'serialnumberonlabelfield' (Plugin Fields)")
                self.stdout.write("─" * 80)
                self.stdout.write("")

                self.stdout.write(f"Запрос: {client.url}/PluginFieldsPrinterx/")
                self.stdout.write(f"Поле: serialnumberonlabelfield")
                self.stdout.write(f"Значение: {serial_number}")
                self.stdout.write("")

                plugin_response = requests.get(
                    f"{client.url}/PluginFieldsPrinterx/",
                    headers=client._get_headers(with_session=True),
                    timeout=15,
                    verify=client.verify_ssl
                )

                if plugin_response.status_code == 200:
                    plugin_data = plugin_response.json()

                    self.stdout.write(f"Получено записей из Plugin Fields: {len(plugin_data)}")
                    self.stdout.write("")

                    # Ищем совпадения
                    found_printer_ids = []
                    for record in plugin_data:
                        label_serial = record.get('serialnumberonlabelfield', '').strip()
                        items_id = record.get('items_id')

                        if label_serial and label_serial.lower() == serial_number.lower():
                            self.stdout.write(f"  ✓ Найдено совпадение: items_id={items_id}, serial={label_serial}")
                            if items_id:
                                found_printer_ids.append(items_id)

                    if found_printer_ids:
                        self.stdout.write("")
                        self.stdout.write(self.style.SUCCESS(f"✓ Найдено принтеров: {len(found_printer_ids)}"))
                        self.stdout.write("")

                        # Получаем полную информацию
                        for printer_id in found_printer_ids:
                            self.stdout.write(f"Получение детальной информации для ID={printer_id}...")

                            printer_resp = requests.get(
                                f"{client.url}/Printer/{printer_id}",
                                headers=client._get_headers(with_session=True),
                                timeout=10,
                                verify=client.verify_ssl
                            )

                            if printer_resp.status_code == 200:
                                printer_data = printer_resp.json()
                                self.stdout.write("")
                                self._display_printer_full(printer_data)
                            else:
                                self.stdout.write(self.style.ERROR(f"  ✗ Ошибка получения: HTTP {printer_resp.status_code}"))
                            self.stdout.write("")

                    else:
                        self.stdout.write(self.style.WARNING("⚠ НЕ найдено в кастомном поле"))

                else:
                    self.stdout.write(self.style.ERROR(f"✗ Ошибка: HTTP {plugin_response.status_code}"))
                    if plugin_response.status_code == 404:
                        self.stdout.write("  Возможно, плагин Fields не установлен в GLPI")

                self.stdout.write("")

                # ===================================================================
                # ИТОГ
                # ===================================================================
                self.stdout.write("─" * 80)
                self.stdout.write("ИТОГИ")
                self.stdout.write("─" * 80)
                self.stdout.write("")
                self.stdout.write("Поиск выполнен по двум источникам:")
                self.stdout.write("  1. Стандартное поле 'serial' (быстрый поиск)")
                self.stdout.write("  2. Кастомное поле 'serialnumberonlabelfield' (полный поиск)")
                self.stdout.write("")
                self.stdout.write("💡 Метод search_printer_by_serial() использует ОБА источника автоматически")

        except GLPIAPIError as e:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"✗ Ошибка GLPI API: {e}"))

        except Exception as e:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"✗ Ошибка выполнения: {e}"))
            import traceback
            traceback.print_exc()

    def _display_printer(self, printer_data):
        """Отображает принтер из search API"""
        printer_id = printer_data.get('2', 'N/A')
        name = printer_data.get('1', 'N/A')
        serial = printer_data.get('5', 'N/A')
        manufacturer = printer_data.get('23', 'N/A')
        state = printer_data.get('31', 'N/A')

        self.stdout.write(f"  ID: {printer_id}")
        self.stdout.write(f"  Название: {name}")
        self.stdout.write(f"  Серийный: {serial}")
        self.stdout.write(f"  Производитель: {manufacturer}")
        self.stdout.write(f"  Состояние: {state}")

    def _display_printer_full(self, printer_data):
        """Отображает принтер из detail API"""
        printer_id = printer_data.get('id', 'N/A')
        name = printer_data.get('name', 'N/A')
        serial = printer_data.get('serial', 'N/A')
        manufacturer = printer_data.get('manufacturers_name', 'N/A')
        state = printer_data.get('states_name', 'N/A')

        self.stdout.write(f"  ID: {printer_id}")
        self.stdout.write(f"  Название: {name}")
        self.stdout.write(f"  Серийный: {serial}")
        self.stdout.write(f"  Производитель: {manufacturer}")
        self.stdout.write(f"  Состояние: {state}")
