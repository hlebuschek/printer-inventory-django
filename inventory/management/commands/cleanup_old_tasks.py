# inventory/management/commands/cleanup_old_tasks.py
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from datetime import timedelta
from inventory.models import InventoryTask, Printer

class Command(BaseCommand):
    help = """
    Умная очистка старых записей инвентаризации:
    - Последние 30 дней: храним все записи
    - Старше 30 дней: оставляем только последнюю SUCCESS запись за каждый день для каждого принтера
    - Записи старше года сохраняются (для истории)
    
    После очистки запускает VACUUM ANALYZE для освобождения места и обновления статистики.
    """
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, без реального удаления',
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='Сколько дней хранить все записи (по умолчанию 30)',
        )
        parser.add_argument(
            '--archive-days',
            type=int,
            default=365,
            help='До какого возраста архивировать (по умолчанию 365 дней)',
        )
        parser.add_argument(
            '--no-vacuum',
            action='store_true',
            help='Не запускать VACUUM после очистки',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        keep_days = options['keep_days']
        archive_days = options['archive_days']
        no_vacuum = options['no_vacuum']
        
        now = timezone.now()
        
        # Граница "свежих" данных (храним все)
        keep_boundary = now - timedelta(days=keep_days)
        
        # Граница архивных данных (храним по 1 в день)
        archive_boundary = now - timedelta(days=archive_days)
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS("УМНАЯ ОЧИСТКА ДАННЫХ ИНВЕНТАРИЗАЦИИ"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))
        
        self.stdout.write(f"Текущее время: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"Режим: {'DRY-RUN (тестовый)' if dry_run else 'РЕАЛЬНАЯ ОЧИСТКА'}\n")
        
        # === 1. УДАЛЕНИЕ СТАРЫХ ДАННЫХ (старше archive_days) ===
        self.stdout.write(self.style.WARNING(f"\n1️⃣  Удаление записей старше {archive_days} дней"))
        self.stdout.write(f"   (до {archive_boundary.strftime('%Y-%m-%d')})\n")
        
        old_count = InventoryTask.objects.filter(
            task_timestamp__lt=archive_boundary
        ).count()
        
        if old_count > 0:
            self.stdout.write(f"   Найдено записей для удаления: {old_count:,}")
            
            if not dry_run:
                with transaction.atomic():
                    deleted = InventoryTask.objects.filter(
                        task_timestamp__lt=archive_boundary
                    ).delete()
                    self.stdout.write(self.style.SUCCESS(f"   ✓ Удалено: {deleted[0]:,} записей"))
            else:
                self.stdout.write(self.style.WARNING(f"   → Будет удалено: {old_count:,} записей"))
        else:
            self.stdout.write("   ℹ Старых записей не найдено")
        
        # === 2. АРХИВАЦИЯ ДАННЫХ (оставляем по 1 в день) ===
        self.stdout.write(self.style.WARNING(f"\n2️⃣  Архивация записей от {keep_days} до {archive_days} дней назад"))
        self.stdout.write(f"   ({archive_boundary.strftime('%Y-%m-%d')} — {keep_boundary.strftime('%Y-%m-%d')})")
        self.stdout.write("   Оставляем последнюю SUCCESS запись за каждый день для каждого принтера\n")
        
        # Получаем все принтеры
        printers = Printer.objects.all()
        total_deleted = 0
        
        for printer in printers:
            deleted = self._cleanup_printer_archive(
                printer, 
                keep_boundary, 
                archive_boundary, 
                dry_run
            )
            total_deleted += deleted
        
        if total_deleted > 0:
            self.stdout.write(self.style.SUCCESS(f"\n   ✓ Всего {'будет удалено' if dry_run else 'удалено'}: {total_deleted:,} записей"))
        else:
            self.stdout.write("   ℹ Дублирующихся записей не найдено")
        
        # === 3. СТАТИСТИКА ===
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS("СТАТИСТИКА ПОСЛЕ ОЧИСТКИ"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))
        
        total_tasks = InventoryTask.objects.count()
        total_printers = Printer.objects.count()
        
        recent_tasks = InventoryTask.objects.filter(
            task_timestamp__gte=keep_boundary
        ).count()
        
        archive_tasks = InventoryTask.objects.filter(
            task_timestamp__lt=keep_boundary,
            task_timestamp__gte=archive_boundary
        ).count()
        
        self.stdout.write(f"Всего принтеров: {total_printers:,}")
        self.stdout.write(f"Всего записей инвентаризации: {total_tasks:,}")
        self.stdout.write(f"  • Свежие (последние {keep_days} дней): {recent_tasks:,}")
        self.stdout.write(f"  • Архивные ({keep_days}-{archive_days} дней): {archive_tasks:,}")
        
        # Средние значения
        if total_printers > 0:
            avg_per_printer = total_tasks / total_printers
            self.stdout.write(f"\nСреднее записей на принтер: {avg_per_printer:.1f}")
        
        # === 4. VACUUM ===
        if not dry_run and not no_vacuum:
            self.stdout.write(self.style.WARNING(f"\n{'='*70}"))
            self.stdout.write(self.style.WARNING("VACUUM ANALYZE"))
            self.stdout.write(self.style.WARNING(f"{'='*70}\n"))
            self.stdout.write("Освобождаем место и обновляем статистику индексов...\n")
            
            self._run_vacuum()
        elif no_vacuum:
            self.stdout.write(self.style.WARNING("\n⚠️  VACUUM пропущен (--no-vacuum)"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  VACUUM пропущен (dry-run режим)"))
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS("✓ ОЧИСТКА ЗАВЕРШЕНА"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))

    def _cleanup_printer_archive(self, printer, keep_boundary, archive_boundary, dry_run):
        """
        Для одного принтера оставляет только последнюю SUCCESS запись за каждый день
        в диапазоне от archive_boundary до keep_boundary
        """
        deleted_count = 0
        
        # Используем SQL для эффективности (PostgreSQL)
        # Находим ID записей, которые НЕ являются последними за свой день
        with connection.cursor() as cursor:
            sql = """
                WITH daily_last AS (
                    SELECT DISTINCT ON (DATE(task_timestamp))
                        id
                    FROM inventory_inventorytask
                    WHERE printer_id = %s
                        AND status = 'SUCCESS'
                        AND task_timestamp >= %s
                        AND task_timestamp < %s
                    ORDER BY DATE(task_timestamp), task_timestamp DESC
                )
                SELECT id 
                FROM inventory_inventorytask
                WHERE printer_id = %s
                    AND task_timestamp >= %s
                    AND task_timestamp < %s
                    AND id NOT IN (SELECT id FROM daily_last)
            """
            
            cursor.execute(sql, [
                printer.id,
                archive_boundary,
                keep_boundary,
                printer.id,
                archive_boundary,
                keep_boundary,
            ])
            
            ids_to_delete = [row[0] for row in cursor.fetchall()]
            deleted_count = len(ids_to_delete)
            
            if deleted_count > 0 and not dry_run:
                InventoryTask.objects.filter(id__in=ids_to_delete).delete()
        
        return deleted_count

    def _run_vacuum(self):
        """Запускает VACUUM ANALYZE для таблиц инвентаризации"""
        tables = [
            'inventory_inventorytask',
            'inventory_pagecounter',
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                self.stdout.write(f"  • VACUUM ANALYZE {table}...")
                try:
                    # VACUUM нельзя запустить в транзакции
                    old_autocommit = connection.autocommit
                    connection.autocommit = True
                    
                    cursor.execute(f"VACUUM ANALYZE {table}")
                    
                    connection.autocommit = old_autocommit
                    
                    self.stdout.write(self.style.SUCCESS(f"    ✓ Завершено"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ Ошибка: {e}"))
        
        self.stdout.write(self.style.SUCCESS("\n✓ VACUUM завершён успешно"))
