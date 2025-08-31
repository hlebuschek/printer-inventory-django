from django.core.management.base import BaseCommand
from inventory.models import Printer
from inventory.utils import xml_to_json, extract_mac_address, persist_inventory_to_db
import os
import re


class Command(BaseCommand):
    help = 'Импорт данных о принтерах из XML-файла (логика сохранения в utils.py)'

    def add_arguments(self, parser):
        parser.add_argument('xml_path', type=str, help='Путь к XML-файлу')
        parser.add_argument('printer_ip', nargs='?', type=str, help='IP-адрес принтера (необязательно)')

    def handle(self, *args, **options):
        xml_path = options['xml_path']
        printer_ip = options.get('printer_ip')

        if not os.path.exists(xml_path):
            self.stdout.write(self.style.ERROR(f"XML-файл {xml_path} не найден"))
            return

        data = xml_to_json(xml_path)
        if not data:
            self.stdout.write(self.style.ERROR("Ошибка парсинга XML"))
            return

        # Если IP не передан — попробуем вытащить его из имени файла
        if not printer_ip:
            m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', os.path.basename(xml_path))
            if m:
                printer_ip = m.group(1)

        printer = None
        if printer_ip:
            try:
                printer = Printer.objects.get(ip_address=printer_ip)
            except Printer.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Принтер с IP {printer_ip} не найден в БД — пробую найти по MAC."))

        if not printer:
            # Попробуем найти по MAC из XML
            mac = None
            try:
                mac = extract_mac_address(data)
            except Exception:
                pass

            if mac:
                qs = Printer.objects.filter(mac_address__iexact=mac)
                if qs.count() == 1:
                    printer = qs.first()
                    printer_ip = printer.ip_address
                    self.stdout.write(self.style.SUCCESS(f"Определён принтер по MAC {mac}: IP {printer_ip}"))
                elif qs.count() > 1:
                    self.stdout.write(self.style.ERROR(f"Найдено несколько принтеров с MAC {mac} — укажите IP явно."))
                    return

        if not printer:
            self.stdout.write(self.style.ERROR(
                "Не удалось определить принтер. Передайте IP аргументом или убедитесь, что MAC из XML есть в БД."
            ))
            return

        ok, task, err = persist_inventory_to_db(data, printer, allow_mac_update=True)
        if not ok:
            self.stdout.write(self.style.ERROR(f"Импорт не выполнен: {err or 'ошибка'}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Успешно импортировано из XML (IP: {printer_ip})"
        ))
