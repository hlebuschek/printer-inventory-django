"""
Тестовая команда для проверки работы отрицательных значений
"""
from django.core.management.base import BaseCommand
from django.db import connection
from monthly_report.models import MonthlyReport
from monthly_report.services import _pair, recompute_group
from datetime import date


class Command(BaseCommand):
    help = 'Тестирует поддержку отрицательных значений в total_prints'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=== ТЕСТ 1: Проверка типа поля в БД ==='))

        # Проверяем тип поля в БД
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'monthly_report_monthlyreport'
                AND column_name = 'total_prints'
            """)
            row = cursor.fetchone()
            if row:
                self.stdout.write(f"Поле total_prints: тип={row[1]}, nullable={row[2]}")

            # Проверяем CHECK constraints
            cursor.execute("""
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'monthly_report_monthlyreport'::regclass
                AND conname LIKE '%total_prints%'
            """)
            constraints = cursor.fetchall()
            if constraints:
                self.stdout.write("Найдены constraints для total_prints:")
                for name, definition in constraints:
                    self.stdout.write(f"  {name}: {definition}")
            else:
                self.stdout.write(self.style.SUCCESS("✓ CHECK constraints для total_prints не найдены (ОК)"))

        self.stdout.write('\n' + self.style.WARNING('=== ТЕСТ 2: Проверка функции _pair ==='))

        # Создаем тестовую запись
        test_report = MonthlyReport(
            month=date(2025, 11, 1),
            organization='TEST',
            branch='TEST',
            city='TEST',
            address='TEST',
            equipment_model='TEST',
            serial_number='TEST123',
            inventory_number='TEST123',
            a4_bw_start=1000,
            a4_bw_end=950,  # Меньше чем start!
        )

        # Проверяем функцию _pair
        result = _pair(test_report, 'a4_bw_start', 'a4_bw_end')
        self.stdout.write(f"_pair(start=1000, end=950) = {result}")

        if result == -50:
            self.stdout.write(self.style.SUCCESS("✓ Функция _pair работает корректно"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Ошибка! Ожидалось -50, получено {result}"))

        self.stdout.write('\n' + self.style.WARNING('=== ТЕСТ 3: Попытка сохранить отрицательное значение ==='))

        try:
            # Пытаемся создать запись с отрицательным total_prints
            test_report.total_prints = -100
            test_report.save()

            # Проверяем что сохранилось
            saved_report = MonthlyReport.objects.get(id=test_report.id)
            self.stdout.write(f"Сохранено: total_prints = {saved_report.total_prints}")

            if saved_report.total_prints == -100:
                self.stdout.write(self.style.SUCCESS("✓ Отрицательное значение успешно сохранено"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Значение изменилось при сохранении: {saved_report.total_prints}"))

            # Удаляем тестовую запись
            test_report.delete()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Ошибка при сохранении: {e}"))

        self.stdout.write('\n' + self.style.WARNING('=== ТЕСТ 4: Проверка recompute_group ==='))

        # Создаем тестовую запись для recompute
        test_report2 = MonthlyReport.objects.create(
            month=date(2025, 11, 1),
            organization='TEST2',
            branch='TEST2',
            city='TEST2',
            address='TEST2',
            equipment_model='TEST2',
            serial_number='TEST_RECOMPUTE',
            inventory_number='TEST_RECOMPUTE',
            a4_bw_start=5000,
            a4_bw_end=4800,  # Меньше!
            a4_color_start=2000,
            a4_color_end=1900,  # Меньше!
        )

        self.stdout.write(f"Создана запись: ID={test_report2.id}, total_prints={test_report2.total_prints}")

        # Вызываем recompute_group
        recompute_group(test_report2.month, test_report2.serial_number, None)

        # Проверяем результат
        test_report2.refresh_from_db()
        expected = (4800 - 5000) + (1900 - 2000)  # -200 + -100 = -300

        self.stdout.write(f"После recompute_group: total_prints = {test_report2.total_prints}")
        self.stdout.write(f"Ожидалось: {expected}")

        if test_report2.total_prints == expected:
            self.stdout.write(self.style.SUCCESS(f"✓ recompute_group работает корректно"))
        else:
            self.stdout.write(self.style.ERROR(f"✗ Ошибка! Ожидалось {expected}, получено {test_report2.total_prints}"))

        # Удаляем тестовую запись
        test_report2.delete()

        self.stdout.write('\n' + self.style.SUCCESS('=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ==='))
