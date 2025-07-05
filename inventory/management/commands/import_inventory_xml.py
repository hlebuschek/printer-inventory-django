from django.core.management.base import BaseCommand
from inventory.models import Printer, InventoryTask, PageCounter
from inventory.utils import xml_to_json, validate_inventory, extract_page_counters, extract_mac_address
from inventory.services import run_inventory_for_printer
import os

class Command(BaseCommand):
    help = 'Импорт данных о принтерах из XML-файла для тестирования, используя продакшен-логику'

    def add_arguments(self, parser):
        parser.add_argument('xml_path', type=str, help='Путь к XML-файлу')
        parser.add_argument('printer_ip', type=str, help='IP-адрес принтера')

    def handle(self, *args, **options):
        xml_path = options['xml_path']
        printer_ip = options['printer_ip']

        # Проверка существования файла
        if not os.path.exists(xml_path):
            self.stdout.write(self.style.ERROR(f"XML-файл {xml_path} не найден"))
            return

        # Проверка существования принтера
        try:
            printer = Printer.objects.get(ip_address=printer_ip)
        except Printer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Принтер с IP {printer_ip} не найден"))
            return

        # Парсинг XML
        data = xml_to_json(xml_path)
        if not data:
            self.stdout.write(self.style.ERROR("Ошибка парсинга XML"))
            return

        # Обновление MAC-адреса, если не установлен
        mac_address = extract_mac_address(data)
        if mac_address and not printer.mac_address:
            printer.mac_address = mac_address
            printer.save()

        # Валидация
        valid, err = validate_inventory(data, printer_ip, printer.serial_number, printer.mac_address)
        if not valid:
            self.stdout.write(self.style.ERROR(f"Ошибка валидации: {err}"))
            InventoryTask.objects.create(
                printer=printer,
                status='VALIDATION_ERROR',
                error_message=err,
            )
            return

        # Сохранение данных
        try:
            counters = extract_page_counters(data)
            task = InventoryTask.objects.create(printer=printer, status='SUCCESS')
            PageCounter.objects.create(task=task, **counters)
            self.stdout.write(self.style.SUCCESS("Успешно импортированы данные из XML"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка сохранения данных: {str(e)}"))
            InventoryTask.objects.create(
                printer=printer,
                status='FAILED',
                error_message=str(e),
            )