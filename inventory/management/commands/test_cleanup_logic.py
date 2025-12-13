"""
Тестовая команда для проверки логики очистки инвентаризационных данных
БЕЗ реального удаления данных.

Использование:
    python manage.py test_cleanup_logic
"""

from django.core.management.base import BaseCommand
from django.db.models import Max, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from inventory.models import InventoryTask


class Command(BaseCommand):
    help = 'Тестирует логику очистки старых данных инвентаризации БЕЗ удаления'

    def handle(self, *args, **options):
        cutoff_date = timezone.now() - timedelta(days=90)

        self.stdout.write("=" * 80)
        self.stdout.write(f"Тестирование логики очистки (cutoff: {cutoff_date.date()})")
        self.stdout.write("=" * 80)

        # Общая статистика
        total_tasks = InventoryTask.objects.count()
        old_tasks = InventoryTask.objects.filter(task_timestamp__lt=cutoff_date)
        old_tasks_count = old_tasks.count()
        recent_tasks_count = total_tasks - old_tasks_count

        self.stdout.write(f"\nОбщая статистика:")
        self.stdout.write(f"  Всего записей: {total_tasks:,}")
        self.stdout.write(f"  Записей старше 90 дней: {old_tasks_count:,}")
        self.stdout.write(f"  Записей младше 90 дней: {recent_tasks_count:,}")

        if old_tasks_count == 0:
            self.stdout.write(self.style.WARNING("\n⚠️  Нет данных старше 90 дней для очистки"))
            return

        # Находим записи которые будут сохранены (последняя за день)
        tasks_to_keep = old_tasks.annotate(
            date=TruncDate('task_timestamp')
        ).values(
            'printer_id', 'date'
        ).annotate(
            max_id=Max('id')
        ).values_list('max_id', flat=True)

        kept_count = len(tasks_to_keep)
        deleted_count = old_tasks_count - kept_count

        self.stdout.write(f"\nРезультаты анализа старых данных (>{cutoff_date.date()}):")
        self.stdout.write(self.style.SUCCESS(f"  ✓ Будет сохранено: {kept_count:,} записей (по 1 на день/принтер)"))
        self.stdout.write(self.style.WARNING(f"  ✗ Будет удалено: {deleted_count:,} записей"))

        # Подробная статистика по принтерам
        printer_stats = old_tasks.values('printer_id').annotate(
            total=Count('id')
        ).order_by('-total')[:10]

        # Для каждого топ-принтера показываем детали
        self.stdout.write(f"\nТоп-10 принтеров по количеству старых записей:")
        for i, stat in enumerate(printer_stats, 1):
            printer_id = stat['printer_id']
            total = stat['total']

            # Сколько будет сохранено для этого принтера
            printer_keep = old_tasks.filter(
                printer_id=printer_id
            ).annotate(
                date=TruncDate('task_timestamp')
            ).values('date').count()

            printer_delete = total - printer_keep

            self.stdout.write(
                f"  {i}. Printer ID {printer_id}: "
                f"{total:,} записей → "
                f"сохранить {printer_keep:,}, удалить {printer_delete:,}"
            )

        # Статистика по статусам
        self.stdout.write(f"\nРаспределение по статусам (старые данные):")
        status_stats = old_tasks.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        for stat in status_stats:
            status = stat['status']
            count = stat['count']
            percentage = (count / old_tasks_count) * 100
            self.stdout.write(f"  {status}: {count:,} ({percentage:.1f}%)")

        # Проверка эффективности сжатия
        compression_ratio = (deleted_count / old_tasks_count) * 100 if old_tasks_count > 0 else 0

        self.stdout.write(f"\nЭффективность сжатия:")
        self.stdout.write(f"  Коэффициент сжатия: {compression_ratio:.1f}%")
        self.stdout.write(f"  Размер после очистки: {100 - compression_ratio:.1f}% от исходного")

        # Примерная экономия места
        # Предполагаем ~1KB на запись InventoryTask + PageCounter
        estimated_space_mb = (deleted_count * 1) / 1024  # в MB

        self.stdout.write(f"  Примерная экономия места: ~{estimated_space_mb:.1f} MB")

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✓ Тест завершен. ДАННЫЕ НЕ БЫЛИ УДАЛЕНЫ."))
        self.stdout.write("=" * 80)
