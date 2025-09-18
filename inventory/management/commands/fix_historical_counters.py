import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from datetime import datetime, timezone

from inventory.models import Printer, InventoryTask, PageCounter
from inventory.utils import extract_page_counters


class Command(BaseCommand):
    help = """
    Исправляет исторические данные счетчиков страниц, применяя новую логику определения цветных принтеров.

    Примеры использования:
    python manage.py fix_historical_counters --model "Canon iR-ADV C3530i"
    python manage.py fix_historical_counters --printer-ip 192.168.1.100
    python manage.py fix_historical_counters --printer-serial ABC12345
    python manage.py fix_historical_counters --all --after 2024-01-01
    """

    def add_arguments(self, parser):
        # Фильтры устройств
        parser.add_argument(
            '--model',
            type=str,
            help='Исправить для конкретной модели принтера'
        )
        parser.add_argument(
            '--printer-ip',
            type=str,
            help='Исправить для конкретного принтера по IP'
        )
        parser.add_argument(
            '--printer-serial',
            type=str,
            help='Исправить для конкретного принтера по серийному номеру'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Исправить для всех принтеров (осторожно!)'
        )

        # Фильтры по времени
        parser.add_argument(
            '--after',
            type=str,
            help='Исправить только задачи после указанной даты (YYYY-MM-DD или YYYY-MM-DD HH:MM:SS)'
        )
        parser.add_argument(
            '--before',
            type=str,
            help='Исправить только задачи до указанной даты (YYYY-MM-DD или YYYY-MM-DD HH:MM:SS)'
        )

        # Дополнительные опции
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено, без сохранения'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Ограничить количество обрабатываемых задач'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно исправить даже уже цветные записи'
        )

    def handle(self, *args, **options):
        # Проверяем, что указан хотя бы один фильтр
        if not any([options['model'], options['printer_ip'], options['printer_serial'], options['all']]):
            raise CommandError(
                "Укажите один из фильтров: --model, --printer-ip, --printer-serial или --all"
            )

        # Предупреждение для --all
        if options['all'] and not options['dry_run']:
            confirm = input("Вы уверены, что хотите исправить ВСЕ исторические данные? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("Операция отменена.")
                return

        # Строим queryset принтеров
        printers_qs = Printer.objects.all()

        if options['model']:
            printers_qs = printers_qs.filter(model__icontains=options['model'])
        elif options['printer_ip']:
            printers_qs = printers_qs.filter(ip_address=options['printer_ip'])
        elif options['printer_serial']:
            printers_qs = printers_qs.filter(serial_number=options['printer_serial'])

        printers = list(printers_qs)
        if not printers:
            self.stdout.write(self.style.WARNING("Принтеры не найдены по указанным критериям."))
            return

        self.stdout.write(f"Найдено принтеров: {len(printers)}")
        for p in printers[:10]:  # показываем первые 10
            self.stdout.write(f"  - {p.ip_address} ({p.model}) - {p.serial_number}")
        if len(printers) > 10:
            self.stdout.write(f"  ... и ещё {len(printers) - 10}")

        # Строим queryset задач
        tasks_qs = InventoryTask.objects.filter(
            printer__in=printers,
            status='SUCCESS'
        ).select_related('printer').prefetch_related('pagecounter_set')

        # Фильтры по времени
        if options['after']:
            after_dt = self._parse_datetime(options['after'])
            tasks_qs = tasks_qs.filter(task_timestamp__gte=after_dt)

        if options['before']:
            before_dt = self._parse_datetime(options['before'])
            tasks_qs = tasks_qs.filter(task_timestamp__lte=before_dt)

        if options['limit']:
            tasks_qs = tasks_qs[:options['limit']]

        tasks = list(tasks_qs.order_by('-task_timestamp'))

        if not tasks:
            self.stdout.write(self.style.WARNING("Задачи не найдены по указанным критериям."))
            return

        self.stdout.write(f"Найдено задач для обработки: {len(tasks)}")

        # Обрабатываем задачи
        fixed_count = 0
        skipped_count = 0
        error_count = 0

        with transaction.atomic():
            for task in tasks:
                try:
                    result = self._process_task(task, options['force'])
                    if result == 'fixed':
                        fixed_count += 1
                    elif result == 'skipped':
                        skipped_count += 1

                    if (fixed_count + skipped_count) % 100 == 0:
                        self.stdout.write(f"Обработано: {fixed_count + skipped_count}")

                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"Ошибка при обработке задачи {task.id}: {e}")
                    )

            # Результаты
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(f"Исправлено записей: {fixed_count}")
            self.stdout.write(f"Пропущено записей: {skipped_count}")
            if error_count:
                self.stdout.write(self.style.ERROR(f"Ошибок: {error_count}"))

            if options['dry_run']:
                self.stdout.write(self.style.WARNING("DRY-RUN: изменения НЕ сохранены в базу данных."))
                # Откатываем транзакцию в dry-run режиме
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Изменения сохранены в базу данных."))

    def _parse_datetime(self, date_str):
        """Парсит дату из строки"""
        # Пробуем разные форматы
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        raise CommandError(f"Неверный формат даты: {date_str}")

    def _process_task(self, task, force=False):
        """Обрабатывает одну задачу"""
        # Получаем связанный PageCounter
        try:
            page_counter = task.pagecounter_set.first()
            if not page_counter:
                return 'skipped'
        except:
            return 'skipped'

        # Если не force и уже есть цветные страницы - пропускаем
        if not force and (page_counter.color_a3 or page_counter.color_a4):
            return 'skipped'

        # Пытаемся восстановить оригинальные XML данные из задачи
        # (если они сохранены в error_message или где-то ещё)
        # Пока что работаем с тем, что есть в PageCounter

        # Эмулируем XML структуру для проверки цветных расходников
        fake_xml_data = {
            'CONTENT': {
                'DEVICE': {
                    'PAGECOUNTERS': {
                        'BW_A3': page_counter.bw_a3 or 0,
                        'BW_A4': page_counter.bw_a4 or 0,
                        'COLOR_A3': page_counter.color_a3 or 0,
                        'COLOR_A4': page_counter.color_a4 or 0,
                        'TOTAL': page_counter.total_pages or 0,
                    },
                    'CARTRIDGES': {}
                }
            }
        }

        # Добавляем расходники, если они есть
        if page_counter.toner_cyan:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['TONERCYAN'] = page_counter.toner_cyan
        if page_counter.toner_magenta:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['TONERMAGENTA'] = page_counter.toner_magenta
        if page_counter.toner_yellow:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['TONERYELLOW'] = page_counter.toner_yellow
        if page_counter.drum_cyan:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['DRUMCYAN'] = page_counter.drum_cyan
        if page_counter.drum_magenta:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['DRUMMAGENTA'] = page_counter.drum_magenta
        if page_counter.drum_yellow:
            fake_xml_data['CONTENT']['DEVICE']['CARTRIDGES']['DRUMYELLOW'] = page_counter.drum_yellow

        # Применяем новую логику
        new_counters = extract_page_counters(fake_xml_data)

        # Проверяем, нужно ли что-то менять
        changes_needed = (
                page_counter.bw_a3 != new_counters['bw_a3'] or
                page_counter.bw_a4 != new_counters['bw_a4'] or
                page_counter.color_a3 != new_counters['color_a3'] or
                page_counter.color_a4 != new_counters['color_a4']
        )

        if not changes_needed:
            return 'skipped'

        # Логируем изменения
        self.stdout.write(
            f"Задача {task.id} ({task.printer.ip_address}, {task.task_timestamp.strftime('%Y-%m-%d %H:%M')}): "
            f"ЧБ A4: {page_counter.bw_a4} -> {new_counters['bw_a4']}, "
            f"Цвет A4: {page_counter.color_a4} -> {new_counters['color_a4']}"
        )

        # Обновляем счетчики
        page_counter.bw_a3 = new_counters['bw_a3']
        page_counter.bw_a4 = new_counters['bw_a4']
        page_counter.color_a3 = new_counters['color_a3']
        page_counter.color_a4 = new_counters['color_a4']
        page_counter.save()

        return 'fixed'