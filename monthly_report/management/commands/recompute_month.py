"""
Management команда для пересчета total_prints в месячных отчетах
"""
from django.core.management.base import BaseCommand
from datetime import date
from monthly_report.services import recompute_month
from monthly_report.models import MonthlyReport


class Command(BaseCommand):
    help = 'Пересчитать total_prints для указанного месяца'

    def add_arguments(self, parser):
        parser.add_argument(
            'month',
            type=str,
            help='Месяц в формате YYYY-MM (например, 2025-11)'
        )

    def handle(self, *args, **options):
        month_str = options['month']

        try:
            year, month = month_str.split('-')
            year = int(year)
            month = int(month)
            month_date = date(year, month, 1)
        except (ValueError, TypeError) as e:
            self.stdout.write(
                self.style.ERROR(f'Неверный формат месяца: {month_str}. Используйте YYYY-MM')
            )
            return

        # Проверяем что есть данные за этот месяц
        count = MonthlyReport.objects.filter(month=month_date).count()
        if count == 0:
            self.stdout.write(
                self.style.WARNING(f'Нет данных за {month_str}')
            )
            return

        self.stdout.write(f'Найдено {count} записей за {month_str}')
        self.stdout.write('Начинаю пересчет...')

        # Показываем примеры ДО пересчета
        sample_before = list(MonthlyReport.objects.filter(month=month_date)[:5].values(
            'id', 'serial_number', 'a4_bw_start', 'a4_bw_end', 'total_prints'
        ))
        self.stdout.write('\nПример записей ДО пересчета:')
        for record in sample_before:
            self.stdout.write(
                f"  ID {record['id']}: start={record['a4_bw_start']}, "
                f"end={record['a4_bw_end']}, total={record['total_prints']}"
            )

        # Пересчитываем
        try:
            recompute_month(month_date)
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Пересчет завершен успешно')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при пересчете: {e}')
            )
            raise

        # Показываем примеры ПОСЛЕ пересчета
        sample_after = list(MonthlyReport.objects.filter(
            id__in=[r['id'] for r in sample_before]
        ).values(
            'id', 'serial_number', 'a4_bw_start', 'a4_bw_end', 'total_prints'
        ))
        self.stdout.write('\nПример записей ПОСЛЕ пересчета:')
        for record in sample_after:
            self.stdout.write(
                f"  ID {record['id']}: start={record['a4_bw_start']}, "
                f"end={record['a4_bw_end']}, total={record['total_prints']}"
            )

        # Показываем статистику по отрицательным значениям
        negative_count = MonthlyReport.objects.filter(
            month=month_date,
            total_prints__lt=0
        ).count()

        if negative_count > 0:
            self.stdout.write(
                self.style.WARNING(f'\n⚠ Найдено {negative_count} записей с отрицательными значениями')
            )
            # Показываем примеры отрицательных
            negative_samples = MonthlyReport.objects.filter(
                month=month_date,
                total_prints__lt=0
            )[:10].values(
                'id', 'serial_number', 'equipment_model',
                'a4_bw_start', 'a4_bw_end', 'a3_bw_start', 'a3_bw_end',
                'total_prints'
            )

            self.stdout.write('\nПримеры записей с отрицательным total_prints:')
            for rec in negative_samples:
                self.stdout.write(
                    f"  ID {rec['id']} ({rec['equipment_model']}): "
                    f"A4_BW {rec['a4_bw_start']}→{rec['a4_bw_end']}, "
                    f"A3_BW {rec['a3_bw_start']}→{rec['a3_bw_end']}, "
                    f"total={rec['total_prints']}"
                )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✓ Отрицательных значений не найдено')
            )
