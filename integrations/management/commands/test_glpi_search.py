"""
Django management команда для тестирования поиска принтеров в GLPI.

Использование:
    python manage.py test_glpi_search <serial_number>

Пример:
    python manage.py test_glpi_search 399921100163
"""

from django.core.management.base import BaseCommand
from integrations.glpi.client import GLPIClient, GLPIAPIError
import json


class Command(BaseCommand):
    help = 'Тестирование поиска принтера в GLPI по серийному номеру'

    def add_arguments(self, parser):
        parser.add_argument(
            'serial_number',
            type=str,
            help='Серийный номер принтера для поиска'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Показывать детальную информацию'
        )

    def handle(self, *args, **options):
        serial_number = options['serial_number']
        verbose = options.get('verbose', False)

        self.stdout.write("=" * 80)
        self.stdout.write(f"Тестирование поиска принтера: {serial_number}")
        self.stdout.write("=" * 80)
        self.stdout.write("")

        try:
            # Создаём клиент GLPI
            with GLPIClient() as client:
                # Показываем информацию о подключении
                self.stdout.write(self.style.SUCCESS(f"✓ Подключение к GLPI: {client.url}"))

                if client.session_token:
                    token_preview = client.session_token[:20] + "..." if len(client.session_token) > 20 else client.session_token
                    self.stdout.write(f"  Session Token: {token_preview}")

                self.stdout.write(f"  SSL Verification: {client.verify_ssl}")
                self.stdout.write("")

                # Выполняем поиск
                self.stdout.write("Выполняется поиск...")
                status, items, error = client.search_printer_by_serial(serial_number)

                # Показываем результаты
                self.stdout.write("")
                self.stdout.write("─" * 80)
                self.stdout.write("РЕЗУЛЬТАТЫ ПОИСКА")
                self.stdout.write("─" * 80)
                self.stdout.write("")

                if status == 'ERROR':
                    self.stdout.write(self.style.ERROR(f"✗ Ошибка: {error}"))
                    return

                elif status == 'NOT_FOUND':
                    self.stdout.write(self.style.WARNING(f"⚠ Принтер с серийным номером '{serial_number}' НЕ найден в GLPI"))
                    self.stdout.write("")
                    self.stdout.write("Возможные причины:")
                    self.stdout.write("  • Серийный номер указан неверно")
                    self.stdout.write("  • Принтер не добавлен в GLPI")
                    self.stdout.write("  • Поиск ведётся только по стандартному полю 'serial'")
                    self.stdout.write("")

                elif status == 'FOUND_SINGLE':
                    self.stdout.write(self.style.SUCCESS(f"✓ Найден 1 принтер"))
                    self.stdout.write("")
                    self._display_printer(items[0], verbose)

                elif status == 'FOUND_MULTIPLE':
                    self.stdout.write(self.style.WARNING(f"⚠ Найдено {len(items)} принтеров (конфликт!)"))
                    self.stdout.write("")
                    for i, item in enumerate(items, 1):
                        self.stdout.write(f"Принтер #{i}:")
                        self._display_printer(item, verbose)
                        self.stdout.write("")

                # Статистика
                self.stdout.write("─" * 80)
                self.stdout.write("СТАТИСТИКА")
                self.stdout.write("─" * 80)
                self.stdout.write(f"Статус: {status}")
                self.stdout.write(f"Найдено: {len(items)}")
                if error:
                    self.stdout.write(f"Ошибка: {error}")

        except GLPIAPIError as e:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"✗ Ошибка GLPI API: {e}"))

        except Exception as e:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"✗ Ошибка выполнения: {e}"))

            if verbose:
                import traceback
                self.stdout.write("")
                self.stdout.write("Traceback:")
                traceback.print_exc()

    def _display_printer(self, printer_data, verbose=False):
        """Отображает информацию о принтере"""

        # Извлекаем данные (формат зависит от способа получения)
        printer_id = printer_data.get('2') or printer_data.get('id')
        name = printer_data.get('1') or printer_data.get('name', 'N/A')
        serial = printer_data.get('5') or printer_data.get('serial', 'N/A')
        manufacturer = printer_data.get('23') or printer_data.get('manufacturers_name', 'N/A')
        state = printer_data.get('31') or printer_data.get('states_name', 'N/A')

        self.stdout.write(f"  ID: {printer_id}")
        self.stdout.write(f"  Название: {name}")
        self.stdout.write(f"  Серийный номер: {serial}")
        self.stdout.write(f"  Производитель: {manufacturer}")
        self.stdout.write(f"  Состояние: {state}")

        if verbose:
            self.stdout.write("")
            self.stdout.write("  Полные данные:")
            self.stdout.write(json.dumps(printer_data, indent=4, ensure_ascii=False))
