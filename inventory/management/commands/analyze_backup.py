"""
Анализ данных в бэкапной БД для понимания объёма и периода данных.

Использование:
    python manage.py analyze_backup --db-name backup
"""

from django.core.management.base import BaseCommand
from django.db import connections
from django.utils import timezone
from datetime import datetime


class Command(BaseCommand):
    help = 'Анализирует данные в бэкапной БД'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-name',
            type=str,
            default='backup',
            help='Имя базы данных с бэкапом (по умолчанию: backup)'
        )

    def handle(self, *args, **options):
        db_name = options['db_name']

        self.stdout.write("=" * 80)
        self.stdout.write(f"Анализ бэкапной базы данных: {db_name}")
        self.stdout.write("=" * 80)

        # Создаём подключение к бэкапной БД
        from django.conf import settings

        # Копируем настройки основной БД, меняем только имя
        backup_db_settings = settings.DATABASES['default'].copy()
        backup_db_settings['NAME'] = db_name

        # Временно добавляем конфигурацию
        settings.DATABASES['backup_temp'] = backup_db_settings

        try:
            connection = connections['backup_temp']
            cursor = connection.cursor()

            # 1. Общая статистика по InventoryTask
            self.stdout.write("\n📊 InventoryTask (история опросов):")

            cursor.execute("SELECT COUNT(*) FROM inventory_inventorytask")
            total_tasks = cursor.fetchone()[0]
            self.stdout.write(f"  Всего записей: {total_tasks:,}")

            cursor.execute("""
                SELECT
                    MIN(task_timestamp) as first_task,
                    MAX(task_timestamp) as last_task
                FROM inventory_inventorytask
            """)
            first_task, last_task = cursor.fetchone()

            if first_task and last_task:
                self.stdout.write(f"  Первый опрос: {first_task}")
                self.stdout.write(f"  Последний опрос: {last_task}")

                # Считаем период в днях
                if isinstance(first_task, str):
                    first_dt = datetime.fromisoformat(first_task.replace('Z', '+00:00'))
                    last_dt = datetime.fromisoformat(last_task.replace('Z', '+00:00'))
                else:
                    first_dt = first_task
                    last_dt = last_task

                period_days = (last_dt - first_dt).days
                self.stdout.write(f"  Период: {period_days} дней")

            # 2. Статистика по статусам
            self.stdout.write("\n📈 Распределение по статусам:")
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM inventory_inventorytask
                GROUP BY status
                ORDER BY count DESC
            """)
            for status, count in cursor.fetchall():
                percentage = (count / total_tasks) * 100
                self.stdout.write(f"  {status}: {count:,} ({percentage:.1f}%)")

            # 3. Количество уникальных принтеров
            cursor.execute("""
                SELECT COUNT(DISTINCT printer_id)
                FROM inventory_inventorytask
            """)
            unique_printers = cursor.fetchone()[0]
            self.stdout.write(f"\n🖨️  Уникальных принтеров: {unique_printers:,}")

            # 4. Средняя частота опросов
            if total_tasks > 0 and period_days > 0:
                avg_per_day = total_tasks / period_days
                self.stdout.write(f"\n⏱️  Средняя частота: {avg_per_day:.0f} опросов/день")

            # 5. Статистика по PageCounter
            cursor.execute("SELECT COUNT(*) FROM inventory_pagecounter")
            total_counters = cursor.fetchone()[0]
            self.stdout.write(f"\n📄 PageCounter (данные опросов):")
            self.stdout.write(f"  Всего записей: {total_counters:,}")

            # 6. Оценка размера данных в текущей БД
            self.stdout.write("\n📊 Статистика текущей БД (inventory_printer):")

            current_cursor = connections['default'].cursor()
            current_cursor.execute("SELECT COUNT(*) FROM inventory_inventorytask")
            current_tasks = current_cursor.fetchone()[0]

            current_cursor.execute("""
                SELECT
                    MIN(task_timestamp) as first_task,
                    MAX(task_timestamp) as last_task
                FROM inventory_inventorytask
            """)
            curr_first, curr_last = current_cursor.fetchone()

            self.stdout.write(f"  Всего записей: {current_tasks:,}")
            if curr_first and curr_last:
                self.stdout.write(f"  Первый опрос: {curr_first}")
                self.stdout.write(f"  Последний опрос: {curr_last}")

            # 7. Определяем какие данные отсутствуют
            if first_task and curr_first:
                if isinstance(first_task, str):
                    backup_first_dt = datetime.fromisoformat(first_task.replace('Z', '+00:00'))
                else:
                    backup_first_dt = first_task

                if isinstance(curr_first, str):
                    current_first_dt = datetime.fromisoformat(curr_first.replace('Z', '+00:00'))
                else:
                    current_first_dt = curr_first

                missing_days = (current_first_dt - backup_first_dt).days

                self.stdout.write("\n🔍 Анализ отсутствующих данных:")
                self.stdout.write(f"  Период отсутствующих данных: ~{missing_days} дней")
                self.stdout.write(f"  С {backup_first_dt.date()} по {current_first_dt.date()}")

                # Оценка объёма отсутствующих данных
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM inventory_inventorytask
                    WHERE task_timestamp < %s
                """, [curr_first])
                missing_tasks = cursor.fetchone()[0]
                self.stdout.write(f"  Записей в бэкапе за этот период: {missing_tasks:,}")

                # После сжатия (1 запись на день на принтер)
                compressed_estimate = missing_days * unique_printers
                self.stdout.write(f"  После сжатия (1/день/принтер): ~{compressed_estimate:,}")

            # 8. Рекомендации
            self.stdout.write("\n💡 Рекомендации:")
            self.stdout.write("  1. Используйте команду 'migrate_from_backup' для переноса данных")
            self.stdout.write("  2. Данные будут автоматически сжаты (1 запись/день/принтер)")
            self.stdout.write("  3. Это сохранит полную историю при минимальном размере")

            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("✓ Анализ завершен"))
            self.stdout.write("=" * 80)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Ошибка: {e}"))
            import traceback
            traceback.print_exc()

        finally:
            # Удаляем временную конфигурацию
            if 'backup_temp' in settings.DATABASES:
                del settings.DATABASES['backup_temp']
