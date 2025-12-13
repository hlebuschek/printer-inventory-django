"""
Миграция исторических данных из бэкапной БД в текущую с применением сжатия.

Стратегия:
- Переносит только отсутствующие старые данные
- Применяет сжатие: 1 последняя запись за день для каждого принтера
- Избегает дубликатов

Использование:
    # Анализ (dry-run, без изменений)
    python manage.py migrate_from_backup --db-name backup --dry-run

    # Реальная миграция
    python manage.py migrate_from_backup --db-name backup

    # С ограничением (например, только 2024 год)
    python manage.py migrate_from_backup --db-name backup --year 2024
"""

from django.core.management.base import BaseCommand
from django.db import connections, transaction
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = 'Мигрирует исторические данные из бэкапа с применением сжатия'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-name',
            type=str,
            default='backup',
            help='Имя базы данных с бэкапом (по умолчанию: backup)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Анализ без реальных изменений'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Мигрировать только данные за конкретный год'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Размер batch для вставки (по умолчанию: 1000)'
        )

    def handle(self, *args, **options):
        db_name = options['db_name']
        dry_run = options['dry_run']
        year = options['year']
        batch_size = options['batch_size']

        self.stdout.write("=" * 80)
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 РЕЖИМ АНАЛИЗА (dry-run) - изменения НЕ будут применены"))
        else:
            self.stdout.write(self.style.SUCCESS("🚀 РЕЖИМ МИГРАЦИИ - данные будут перенесены"))
        self.stdout.write("=" * 80)

        # Настройка подключения к бэкапу
        from django.conf import settings
        backup_db_settings = settings.DATABASES['default'].copy()
        backup_db_settings['NAME'] = db_name
        settings.DATABASES['backup_temp'] = backup_db_settings

        try:
            backup_conn = connections['backup_temp']
            current_conn = connections['default']

            # 1. Определяем период отсутствующих данных
            current_cursor = current_conn.cursor()
            current_cursor.execute("""
                SELECT MIN(task_timestamp) FROM inventory_inventorytask
            """)
            current_first = current_cursor.fetchone()[0]

            backup_cursor = backup_conn.cursor()

            if year:
                # Если указан год, берем данные только за этот год
                date_filter = f"AND EXTRACT(YEAR FROM task_timestamp) = {year}"
                self.stdout.write(f"\n📅 Фильтр: только данные за {year} год")
            elif current_first:
                # Иначе берем все данные до первой записи в текущей БД
                date_filter = f"AND task_timestamp < '{current_first}'"
                self.stdout.write(f"\n📅 Период миграции: до {current_first}")
            else:
                # Если текущая БД пустая, берем всё
                date_filter = ""
                self.stdout.write("\n📅 Текущая БД пустая - мигрируем все данные")

            # 2. Находим данные для миграции (уже сжатые)
            self.stdout.write("\n⏳ Анализ данных в бэкапе...")

            backup_cursor.execute(f"""
                WITH daily_last AS (
                    SELECT
                        printer_id,
                        DATE(task_timestamp) as date,
                        MAX(id) as max_id
                    FROM inventory_inventorytask
                    WHERE 1=1 {date_filter}
                    GROUP BY printer_id, DATE(task_timestamp)
                )
                SELECT
                    t.id,
                    t.printer_id,
                    t.task_timestamp,
                    t.status,
                    t.error_message,
                    t.match_rule
                FROM inventory_inventorytask t
                INNER JOIN daily_last dl ON t.id = dl.max_id
                ORDER BY t.task_timestamp
            """)

            tasks_to_migrate = backup_cursor.fetchall()
            total_tasks = len(tasks_to_migrate)

            self.stdout.write(f"  Найдено записей для миграции: {total_tasks:,}")

            if total_tasks == 0:
                self.stdout.write(self.style.WARNING("\n⚠️  Нет данных для миграции"))
                return

            # 3. Группируем по принтерам для статистики
            printers_data = defaultdict(int)
            for task in tasks_to_migrate:
                printers_data[task[1]] += 1

            self.stdout.write(f"  Уникальных принтеров: {len(printers_data):,}")
            self.stdout.write(f"  Среднее записей на принтер: {total_tasks / len(printers_data):.1f}")

            # 4. Получаем связанные PageCounter
            task_ids = [task[0] for task in tasks_to_migrate]
            task_ids_str = ','.join(map(str, task_ids))

            backup_cursor.execute(f"""
                SELECT
                    task_id,
                    bw_a3, bw_a4, color_a3, color_a4, total_pages,
                    drum_black, drum_cyan, drum_magenta, drum_yellow,
                    toner_black, toner_cyan, toner_magenta, toner_yellow,
                    fuser_kit, transfer_kit, waste_toner,
                    recorded_at
                FROM inventory_pagecounter
                WHERE task_id IN ({task_ids_str})
            """)

            counters_data = {row[0]: row[1:] for row in backup_cursor.fetchall()}
            self.stdout.write(f"  Найдено PageCounter: {len(counters_data):,}")

            if dry_run:
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write(self.style.SUCCESS("✓ Анализ завершен (dry-run)"))
                self.stdout.write(f"  Будет перенесено InventoryTask: {total_tasks:,}")
                self.stdout.write(f"  Будет перенесено PageCounter: {len(counters_data):,}")
                self.stdout.write("=" * 80)
                return

            # 5. Создаем mapping старых ID -> новых ID для принтеров
            self.stdout.write("\n🔄 Проверка соответствия принтеров...")

            # Получаем список принтеров из бэкапа
            unique_printer_ids = list(printers_data.keys())
            printer_ids_str = ','.join(map(str, unique_printer_ids))

            backup_cursor.execute(f"""
                SELECT id, ip_address, serial_number
                FROM inventory_printer
                WHERE id IN ({printer_ids_str})
            """)
            backup_printers = {row[0]: (row[1], row[2]) for row in backup_cursor.fetchall()}

            # Находим соответствующие принтеры в текущей БД
            printer_mapping = {}  # old_id -> new_id

            for old_id, (ip, serial) in backup_printers.items():
                current_cursor.execute("""
                    SELECT id FROM inventory_printer
                    WHERE ip_address = %s OR serial_number = %s
                    LIMIT 1
                """, [ip, serial])
                result = current_cursor.fetchone()

                if result:
                    printer_mapping[old_id] = result[0]
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  Принтер {ip} / {serial} не найден в текущей БД (пропускаем)")
                    )

            self.stdout.write(f"  Найдено соответствий: {len(printer_mapping)}/{len(backup_printers)}")

            # 6. Импортируем данные батчами
            self.stdout.write("\n📥 Импорт данных...")

            imported_tasks = 0
            imported_counters = 0
            skipped = 0

            with transaction.atomic():
                batch_tasks = []
                batch_counters = []

                for i, task in enumerate(tasks_to_migrate, 1):
                    old_task_id, old_printer_id, timestamp, status, error_msg, match_rule = task

                    # Пропускаем если принтер не найден
                    if old_printer_id not in printer_mapping:
                        skipped += 1
                        continue

                    new_printer_id = printer_mapping[old_printer_id]

                    # Проверяем дубликат
                    current_cursor.execute("""
                        SELECT id FROM inventory_inventorytask
                        WHERE printer_id = %s AND task_timestamp = %s
                    """, [new_printer_id, timestamp])

                    if current_cursor.fetchone():
                        skipped += 1
                        continue

                    # Вставляем InventoryTask
                    current_cursor.execute("""
                        INSERT INTO inventory_inventorytask
                        (printer_id, task_timestamp, status, error_message, match_rule)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, [new_printer_id, timestamp, status, error_msg, match_rule])

                    new_task_id = current_cursor.fetchone()[0]
                    imported_tasks += 1

                    # Вставляем PageCounter если есть
                    if old_task_id in counters_data:
                        counter_data = counters_data[old_task_id]
                        current_cursor.execute("""
                            INSERT INTO inventory_pagecounter
                            (task_id, bw_a3, bw_a4, color_a3, color_a4, total_pages,
                             drum_black, drum_cyan, drum_magenta, drum_yellow,
                             toner_black, toner_cyan, toner_magenta, toner_yellow,
                             fuser_kit, transfer_kit, waste_toner, recorded_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, [new_task_id] + list(counter_data))
                        imported_counters += 1

                    # Прогресс
                    if i % 100 == 0:
                        percentage = (i / total_tasks) * 100
                        self.stdout.write(f"  Прогресс: {i:,}/{total_tasks:,} ({percentage:.1f}%)")

            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(self.style.SUCCESS("✓ Миграция завершена"))
            self.stdout.write(f"  Импортировано InventoryTask: {imported_tasks:,}")
            self.stdout.write(f"  Импортировано PageCounter: {imported_counters:,}")
            self.stdout.write(f"  Пропущено (дубликаты/не найдены): {skipped:,}")
            self.stdout.write("=" * 80)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Ошибка: {e}"))
            import traceback
            traceback.print_exc()

        finally:
            if 'backup_temp' in settings.DATABASES:
                del settings.DATABASES['backup_temp']
