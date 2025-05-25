# File: inventory/management/commands/import_flask_db.py

import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from inventory.models import Printer, InventoryTask, PageCounter

class Command(BaseCommand):
    help = "Импорт данных из старой Flask-базы (с сохранением правильных связей)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--db',
            default='printer_test.db',
            help="Имя файла SQLite (от корня проекта) с данными Flask"
        )

    def handle(self, *args, **options):
        db_file = Path(settings.BASE_DIR) / options['db']
        if not db_file.exists():
            self.stderr.write(self.style.ERROR(f"❌ Файл не найден: {db_file}"))
            return

        conn = sqlite3.connect(db_file)
        cur = conn.cursor()

        # 1) Импорт принтеров и построение маппинга old_id -> Printer instance
        cur.execute("SELECT id, ip_address, serial_number, model, snmp_community FROM printers")
        printers = cur.fetchall()
        self.stdout.write(f"Найдено принтеров: {len(printers)}")

        printer_map = {}
        for old_id, ip, serial, model, community in printers:
            printer, created = Printer.objects.update_or_create(
                ip_address=ip,
                defaults={
                    'serial_number': serial,
                    'model': model,
                    'snmp_community': community,
                }
            )
            printer_map[old_id] = printer
            if created:
                self.stdout.write(f"  + Добавлен принтер {ip}")

        # 2) Импорт задач и построение маппинга old_task_id -> new InventoryTask
        # Сначала определяем, какое поле содержит временную метку
        cur.execute("PRAGMA table_info(inventory_tasks)")
        cols = [r[1] for r in cur.fetchall()]
        ts_col = next((c for c in ('timestamp','task_timestamp','created_at','created') if c in cols), None)

        select_fields = "id, printer_id, status, error_message"
        if ts_col:
            select_fields += f", {ts_col}"
        cur.execute(f"SELECT {select_fields} FROM inventory_tasks")
        tasks = cur.fetchall()
        self.stdout.write(f"Найдено задач: {len(tasks)}")

        task_map = {}
        for row in tasks:
            if ts_col:
                old_id, old_printer_id, status, err_msg, ts = row
            else:
                old_id, old_printer_id, status, err_msg = row
                ts = None

            printer = printer_map.get(old_printer_id)
            if not printer:
                continue

            task = InventoryTask.objects.create(
                printer=printer,
                status=status,
                error_message=err_msg or '',
                task_timestamp=ts  # если None, auto_now_add подставит текущее время
            )
            task_map[old_id] = task

        # 3) Импорт счётчиков, связывая по вновь созданным задачам
        cur.execute("SELECT task_id, bw_a4, color_a4, bw_a3, color_a3, total_pages FROM page_counters")
        counters = cur.fetchall()
        self.stdout.write(f"Найдено записей счётчиков: {len(counters)}")

        for old_task_id, bw4, c4, bw3, c3, total in counters:
            task = task_map.get(old_task_id)
            if not task:
                continue
            PageCounter.objects.create(
                task=task,
                bw_a4=bw4,
                color_a4=c4,
                bw_a3=bw3,
                color_a3=c3,
                total_pages=total
            )

        conn.close()
        self.stdout.write(self.style.SUCCESS("✅ Импорт завершён успешно."))
