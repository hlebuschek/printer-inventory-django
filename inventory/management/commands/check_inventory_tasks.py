# inventory/management/commands/check_inventory_tasks.py

import json
from datetime import timedelta

from celery import current_app
from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import InventoryTask, Printer


class Command(BaseCommand):
    help = "Проверяет состояние задач инвентаризации для принтеров"

    def add_arguments(self, parser):
        parser.add_argument("--printer-id", type=int, help="ID конкретного принтера для проверки")
        parser.add_argument(
            "--hours", type=int, default=2, help="Проверить принтеры без опроса за последние N часов (по умолчанию 2)"
        )
        parser.add_argument("--show-queue", action="store_true", help="Показать задачи в очередях Celery")

    def handle(self, *args, **options):
        printer_id = options.get("printer_id")
        hours = options.get("hours")
        show_queue = options.get("show_queue")

        # Проверка конкретного принтера
        if printer_id:
            self.check_specific_printer(printer_id)
            return

        # Показать очереди Celery
        if show_queue:
            self.show_celery_queues()
            return

        # Найти проблемные принтеры
        self.find_problematic_printers(hours)

    def check_specific_printer(self, printer_id):
        """Детальная проверка конкретного принтера"""
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Принтер {printer_id} не найден"))
            return

        self.stdout.write(self.style.SUCCESS(f"\n=== Принтер {printer.ip_address} (ID: {printer_id}) ==="))
        self.stdout.write(f"Серийный номер: {printer.serial_number}")
        self.stdout.write(f"Модель: {printer.model_display}")
        self.stdout.write(f"Организация: {printer.organization}")
        self.stdout.write(f"Метод опроса: {printer.polling_method}")

        # Последние задачи
        recent_tasks = InventoryTask.objects.filter(printer=printer).order_by("-task_timestamp")[:10]

        if recent_tasks.exists():
            self.stdout.write(self.style.WARNING(f"\nПоследние 10 задач:"))
            for task in recent_tasks:
                status_color = self.style.SUCCESS if task.status == "SUCCESS" else self.style.ERROR
                self.stdout.write(
                    f'  {task.task_timestamp.strftime("%Y-%m-%d %H:%M:%S")} - '
                    f"{status_color(task.status)} - "
                    f'{task.match_rule or "—"}'
                )
                if task.error_message:
                    self.stdout.write(f"    Ошибка: {task.error_message[:100]}")
        else:
            self.stdout.write(self.style.ERROR("\n❌ НЕТ ЗАДАЧ ВООБЩЕ!"))

        # Проверяем активные задачи в Celery
        self.check_celery_tasks_for_printer(printer_id)

    def find_problematic_printers(self, hours):
        """Находит принтеры без успешного опроса за последние N часов"""
        cutoff = timezone.now() - timedelta(hours=hours)

        all_printers = Printer.objects.all().order_by("id")
        total = all_printers.count()

        self.stdout.write(self.style.SUCCESS(f"\n=== Проверка {total} принтеров ==="))
        self.stdout.write(f"Ищем принтеры без успешного опроса за последние {hours} часов...\n")

        problematic = []

        for printer in all_printers:
            last_success = (
                InventoryTask.objects.filter(printer=printer, status="SUCCESS", task_timestamp__gte=cutoff)
                .order_by("-task_timestamp")
                .first()
            )

            if not last_success:
                # Проверяем были ли вообще попытки
                any_task = (
                    InventoryTask.objects.filter(printer=printer, task_timestamp__gte=cutoff)
                    .order_by("-task_timestamp")
                    .first()
                )

                problematic.append({"printer": printer, "last_attempt": any_task, "has_attempts": any_task is not None})

        if not problematic:
            self.stdout.write(self.style.SUCCESS("✓ Все принтеры опрошены успешно!"))
            return

        self.stdout.write(self.style.ERROR(f"\n❌ Найдено {len(problematic)} проблемных принтеров:\n"))

        # Группируем по типу проблемы
        no_attempts = [p for p in problematic if not p["has_attempts"]]
        failed_attempts = [p for p in problematic if p["has_attempts"]]

        if no_attempts:
            self.stdout.write(self.style.ERROR(f"\n🔴 БЕЗ ПОПЫТОК ОПРОСА ({len(no_attempts)}):"))
            for item in no_attempts:
                printer = item["printer"]
                self.stdout.write(
                    f"  ID {printer.id:4d} | {printer.ip_address:15s} | "
                    f'{printer.serial_number:20s} | {printer.organization or "—"}'
                )

        if failed_attempts:
            self.stdout.write(self.style.WARNING(f"\n🟡 НЕУДАЧНЫЕ ПОПЫТКИ ({len(failed_attempts)}):"))
            for item in failed_attempts:
                printer = item["printer"]
                last = item["last_attempt"]
                self.stdout.write(
                    f"  ID {printer.id:4d} | {printer.ip_address:15s} | "
                    f'{last.status:20s} | {last.task_timestamp.strftime("%Y-%m-%d %H:%M")}'
                )
                if last.error_message:
                    self.stdout.write(f"    ↳ {last.error_message[:80]}")

    def check_celery_tasks_for_printer(self, printer_id):
        """Проверяет задачи для принтера в очередях Celery"""
        self.stdout.write(self.style.WARNING("\nПроверка очередей Celery..."))

        try:
            inspect = current_app.control.inspect()

            # Активные задачи
            active = inspect.active()
            if active:
                found = False
                for worker, tasks in active.items():
                    for task in tasks:
                        args = task.get("args", "[]")
                        if str(printer_id) in args:
                            self.stdout.write(self.style.SUCCESS(f'  ✓ Активная задача: {task["name"]} на {worker}'))
                            found = True
                if not found:
                    self.stdout.write("  Нет активных задач")
            else:
                self.stdout.write("  Нет активных задач")

            # Зарезервированные задачи
            reserved = inspect.reserved()
            if reserved:
                found = False
                for worker, tasks in reserved.items():
                    for task in tasks:
                        args = task.get("args", "[]")
                        if str(printer_id) in args:
                            self.stdout.write(self.style.WARNING(f'  ⏳ В очереди: {task["name"]} на {worker}'))
                            found = True
                if not found:
                    self.stdout.write("  Нет задач в очереди")
            else:
                self.stdout.write("  Нет задач в очереди")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Ошибка проверки Celery: {e}"))

    def show_celery_queues(self):
        """Показывает состояние очередей Celery"""
        self.stdout.write(self.style.SUCCESS("\n=== Состояние очередей Celery ===\n"))

        try:
            inspect = current_app.control.inspect()

            # Активные воркеры
            stats = inspect.stats()
            if stats:
                self.stdout.write(self.style.SUCCESS(f"Активных воркеров: {len(stats)}"))
                for worker, stat in stats.items():
                    self.stdout.write(f"  • {worker}")
                    self.stdout.write(f'    Пул: {stat.get("pool", {}).get("max-concurrency", "?")} потоков')
            else:
                self.stdout.write(self.style.ERROR("❌ Нет активных воркеров!"))
                return

            # Активные очереди
            active_queues = inspect.active_queues()
            if active_queues:
                self.stdout.write(self.style.WARNING("\nАктивные очереди:"))
                for worker, queues in active_queues.items():
                    self.stdout.write(f"  {worker}:")
                    for queue in queues:
                        self.stdout.write(f'    • {queue["name"]}')

            # Активные задачи
            active = inspect.active()
            if active:
                total_active = sum(len(tasks) for tasks in active.values())
                self.stdout.write(self.style.WARNING(f"\nВыполняется задач: {total_active}"))
                for worker, tasks in active.items():
                    if tasks:
                        self.stdout.write(f"  {worker}: {len(tasks)} задач")

            # Зарезервированные задачи
            reserved = inspect.reserved()
            if reserved:
                total_reserved = sum(len(tasks) for tasks in reserved.values())
                self.stdout.write(self.style.WARNING(f"\nВ очереди задач: {total_reserved}"))
                for worker, tasks in reserved.items():
                    if tasks:
                        self.stdout.write(f"  {worker}: {len(tasks)} задач")

            # Расписание
            scheduled = inspect.scheduled()
            if scheduled:
                total_scheduled = sum(len(tasks) for tasks in scheduled.values())
                self.stdout.write(self.style.WARNING(f"\nЗапланировано задач: {total_scheduled}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка: {e}"))
