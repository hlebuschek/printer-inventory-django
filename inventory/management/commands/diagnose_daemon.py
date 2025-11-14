from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inventory.models import Printer, InventoryTask


class Command(BaseCommand):
    help = 'Диагностика работы демона инвентаризации'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Диагностика демона инвентаризации ===\n'))

        # 1. Проверяем общее количество принтеров
        total_printers = Printer.objects.count()
        self.stdout.write(f'Всего принтеров в БД: {total_printers}')

        # 2. Проверяем задачи за последние 24 часа
        cutoff_24h = timezone.now() - timedelta(hours=24)

        tasks_24h = InventoryTask.objects.filter(
            task_timestamp__gte=cutoff_24h
        )

        unique_printers_24h = tasks_24h.values('printer').distinct().count()

        self.stdout.write(f'\nЗа последние 24 часа:')
        self.stdout.write(f'  Всего задач: {tasks_24h.count()}')
        self.stdout.write(f'  Уникальных принтеров: {unique_printers_24h}')

        # 3. Принтеры БЕЗ опроса за 24 часа
        not_polled = total_printers - unique_printers_24h
        if not_polled > 0:
            self.stdout.write(self.style.ERROR(
                f'\n❌ НЕ ОПРОШЕНО за 24 часа: {not_polled} принтеров'
            ))

            # Найдем их
            polled_ids = tasks_24h.values_list('printer_id', flat=True).distinct()
            not_polled_printers = Printer.objects.exclude(id__in=polled_ids)[:20]

            self.stdout.write('\nПримеры не опрошенных принтеров:')
            for p in not_polled_printers:
                last_task = InventoryTask.objects.filter(printer=p).order_by('-task_timestamp').first()
                last_date = last_task.task_timestamp if last_task else None
                self.stdout.write(
                    f'  ID {p.id:4d} | {p.ip_address:15s} | '
                    f'Последний опрос: {last_date or "НИКОГДА"}'
                )
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ Все принтеры опрошены за 24 часа'
            ))

        # 4. Проверяем частоту опросов
        cutoff_2h = timezone.now() - timedelta(hours=2)
        tasks_2h = InventoryTask.objects.filter(
            task_timestamp__gte=cutoff_2h
        )

        self.stdout.write(f'\nЗа последние 2 часа:')
        self.stdout.write(f'  Задач: {tasks_2h.count()}')
        self.stdout.write(f'  Ожидалось: ~{total_printers * 2} (если опрос каждый час)')

        if tasks_2h.count() < total_printers:
            self.stdout.write(self.style.WARNING(
                f'  ⚠️  Опрос идет слишком медленно или демон не запускается'
            ))

        # 5. Статистика успешности
        success_rate = tasks_24h.filter(
            status='SUCCESS').count() / tasks_24h.count() * 100 if tasks_24h.count() > 0 else 0
        self.stdout.write(f'\nУспешность опросов за 24ч: {success_rate:.1f}%')