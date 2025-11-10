# inventory/management/commands/check_skipped_printers.py

from django.core.management.base import BaseCommand
from inventory.models import Printer, InventoryTask
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Проверяет почему принтеры не опрашиваются'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)

        # Находим не опрошенные принтеры
        tasks_24h = InventoryTask.objects.filter(task_timestamp__gte=cutoff)
        polled_ids = set(tasks_24h.values_list('printer_id', flat=True).distinct())

        all_printers = Printer.objects.all()
        skipped = []

        for printer in all_printers:
            if printer.id not in polled_ids:
                skipped.append(printer)

        self.stdout.write(self.style.ERROR(f'\n❌ Найдено {len(skipped)} пропущенных принтеров\n'))

        # Проверяем что у них общего
        for printer in skipped[:10]:
            self.stdout.write(f'\nПринтер ID {printer.id} - {printer.ip_address}')
            self.stdout.write(f'  Серийный номер: {printer.serial_number}')
            self.stdout.write(f'  Модель: {printer.model_display}')
            self.stdout.write(f'  Организация: {printer.organization}')
            self.stdout.write(f'  Метод опроса: {printer.polling_method}')

            # Последняя задача вообще
            last_task = InventoryTask.objects.filter(printer=printer).order_by('-task_timestamp').first()
            if last_task:
                self.stdout.write(f'  Последняя задача: {last_task.task_timestamp} - {last_task.status}')
                if last_task.error_message:
                    self.stdout.write(f'  Ошибка: {last_task.error_message[:200]}')
            else:
                self.stdout.write(self.style.ERROR('  ❌ НЕТ ЗАДАЧ ВООБЩЕ!'))

            # Проверяем query прямо сейчас
            try:
                test_query = Printer.objects.filter(id=printer.id).first()
                if test_query:
                    self.stdout.write(self.style.SUCCESS('  ✓ Принтер в БД доступен'))
                else:
                    self.stdout.write(self.style.ERROR('  ❌ Принтер НЕ найден в запросе!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ Ошибка запроса: {e}'))