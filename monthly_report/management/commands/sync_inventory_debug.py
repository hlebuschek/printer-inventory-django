# monthly_report/management/commands/sync_inventory_debug.py
from django.core.management.base import BaseCommand
from django.apps import apps
from datetime import date
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Диагностика синхронизации с inventory приложением'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            default=None,
            help='Месяц в формате YYYY-MM (по умолчанию текущий)'
        )
        parser.add_argument(
            '--serial',
            type=str,
            default=None,
            help='Конкретный серийный номер для проверки'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Выполнить синхронизацию'
        )

    def handle(self, *args, **options):
        # Настраиваем логирование
        logging.basicConfig(level=logging.DEBUG)

        # Определяем месяц
        if options['month']:
            year, month = map(int, options['month'].split('-'))
            month_date = date(year, month, 1)
        else:
            today = date.today()
            month_date = today.replace(day=1)

        self.stdout.write(f"Диагностика синхронизации за {month_date}")

        # Проверяем доступность моделей
        try:
            from monthly_report.models import MonthlyReport
            Printer = apps.get_model('inventory', 'Printer')
            PageCounter = apps.get_model('inventory', 'PageCounter')
            InventoryTask = apps.get_model('inventory', 'InventoryTask')
            self.stdout.write(self.style.SUCCESS("✓ Все модели доступны"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Ошибка доступа к моделям: {e}"))
            return

        # Проверяем структуру полей MonthlyReport
        report_fields = [f.name for f in MonthlyReport._meta.fields]
        auto_fields = [f for f in report_fields if f.endswith('_auto')]
        self.stdout.write(f"Поля *_auto в MonthlyReport: {auto_fields}")

        # Проверяем типы полей
        for field_name in auto_fields:
            field = MonthlyReport._meta.get_field(field_name)
            self.stdout.write(f"  {field_name}: {field.__class__.__name__}")

        # Статистика записей
        reports_count = MonthlyReport.objects.filter(month=month_date).count()
        reports_with_serials = MonthlyReport.objects.filter(
            month=month_date
        ).exclude(serial_number__isnull=True).exclude(serial_number__exact='').count()

        self.stdout.write(f"Записей MonthlyReport за месяц: {reports_count}")
        self.stdout.write(f"Из них с серийными номерами: {reports_with_serials}")

        # Проверяем данные в inventory
        if options['serial']:
            serials = [options['serial']]
        else:
            serials = list(
                MonthlyReport.objects.filter(month=month_date)
                .exclude(serial_number__isnull=True)
                .exclude(serial_number__exact='')
                .values_list('serial_number', flat=True)
                .distinct()[:5]  # Берем первые 5 для примера
            )

        self.stdout.write(f"Проверяем серийники: {serials}")

        for serial in serials:
            self.stdout.write(f"\n--- Серийник: {serial} ---")

            # Поиск принтера
            printer = Printer.objects.filter(serial_number__iexact=serial).first()
            if not printer:
                self.stdout.write(self.style.WARNING(f"  Принтер не найден в inventory"))
                continue

            self.stdout.write(f"  ✓ Принтер найден: {printer.ip_address}")

            # Поиск задач
            tasks = InventoryTask.objects.filter(printer=printer).order_by('-task_timestamp')[:3]
            self.stdout.write(f"  Задач найдено: {tasks.count()}")

            for task in tasks:
                self.stdout.write(f"    {task.task_timestamp} - {task.status}")

                # Счетчики для этой задачи
                counters = PageCounter.objects.filter(task=task).first()
                if counters:
                    self.stdout.write(f"      Счетчики: A4 ЧБ={counters.bw_a4}, A4 Цвет={counters.color_a4}, "
                                      f"A3 ЧБ={counters.bw_a3}, A3 Цвет={counters.color_a3}")
                else:
                    self.stdout.write(f"      Счетчики отсутствуют")

            # Текущие данные в MonthlyReport
            reports = MonthlyReport.objects.filter(
                month=month_date, serial_number__iexact=serial
            )
            self.stdout.write(f"  Записей MonthlyReport: {reports.count()}")

            for report in reports:
                self.stdout.write(f"    ID={report.id}: "
                                  f"A4_ЧБ={report.a4_bw_start}-{report.a4_bw_end}({report.a4_bw_end_auto}), "
                                  f"A4_Цвет={report.a4_color_start}-{report.a4_color_end}({report.a4_color_end_auto})")

        # Выполняем синхронизацию если запрошено
        if options['sync']:
            self.stdout.write(f"\nЗапуск синхронизации...")
            try:
                from monthly_report.services_inventory_sync import sync_month_from_inventory
                result = sync_month_from_inventory(month_date, only_empty=True)
                self.stdout.write(self.style.SUCCESS(f"Синхронизация завершена: {result}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка синхронизации: {e}"))