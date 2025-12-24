"""
Management команда для массовой синхронизации устройств с GLPI.

Примеры использования:
  python manage.py sync_glpi                    # Все устройства
  python manage.py sync_glpi --limit 10         # Первые 10 устройств
  python manage.py sync_glpi --force            # Принудительная проверка (игнорирует кэш)
  python manage.py sync_glpi --with-serial      # Только устройства с серийниками
  python manage.py sync_glpi --device-ids 1 2 3 # Конкретные устройства
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from contracts.models import ContractDevice
from integrations.glpi.services import check_device_in_glpi
import time


class Command(BaseCommand):
    help = 'Массовая синхронизация устройств с GLPI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Ограничить количество проверяемых устройств'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительная проверка (игнорировать кэш 1 час)'
        )
        parser.add_argument(
            '--with-serial',
            action='store_true',
            help='Проверять только устройства с серийными номерами'
        )
        parser.add_argument(
            '--device-ids',
            nargs='+',
            type=int,
            help='ID конкретных устройств для проверки'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Задержка между запросами в секундах (по умолчанию 0.5)'
        )

    def handle(self, *args, **options):
        # Получаем устройства для проверки
        if options['device_ids']:
            devices = ContractDevice.objects.filter(id__in=options['device_ids'])
            self.stdout.write(f"Выбрано устройств по ID: {devices.count()}")
        else:
            devices = ContractDevice.objects.all()

            if options['with_serial']:
                devices = devices.exclude(Q(serial_number='') | Q(serial_number__isnull=True))
                self.stdout.write(f"Фильтр: только устройства с серийниками")

            if options['limit']:
                devices = devices[:options['limit']]
                self.stdout.write(f"Ограничение: {options['limit']} устройств")

        total = devices.count()

        if total == 0:
            self.stdout.write(self.style.WARNING('Нет устройств для проверки'))
            return

        self.stdout.write(f"\nВсего устройств к проверке: {total}")
        self.stdout.write(f"Задержка между запросами: {options['delay']}с")

        if options['force']:
            self.stdout.write(self.style.WARNING('Режим: принудительная проверка (игнорируется кэш)'))

        # Статистика
        stats = {
            'found_single': 0,
            'found_multiple': 0,
            'not_found': 0,
            'errors': 0,
            'skipped': 0
        }

        self.stdout.write("\n" + "="*70)
        self.stdout.write("Начинаем синхронизацию...")
        self.stdout.write("="*70 + "\n")

        start_time = time.time()

        for index, device in enumerate(devices, 1):
            # Пропускаем устройства без серийника
            if not device.serial_number:
                stats['skipped'] += 1
                self.stdout.write(
                    f"[{index}/{total}] ПРОПУЩЕН: {device} (нет серийника)"
                )
                continue

            # Проверяем устройство
            try:
                sync = check_device_in_glpi(
                    device,
                    user=None,
                    force_check=options['force']
                )

                # Обновляем статистику
                if sync.status == 'FOUND_SINGLE':
                    stats['found_single'] += 1
                    status_style = self.style.SUCCESS
                    status_msg = f"✓ Найден (ID: {sync.glpi_ids[0] if sync.glpi_ids else '?'})"
                    if sync.glpi_state_name:
                        status_msg += f" | Состояние: {sync.glpi_state_name}"
                elif sync.status == 'FOUND_MULTIPLE':
                    stats['found_multiple'] += 1
                    status_style = self.style.WARNING
                    status_msg = f"⚠ Конфликт: {len(sync.glpi_ids)} карточек"
                elif sync.status == 'NOT_FOUND':
                    stats['not_found'] += 1
                    status_style = self.style.WARNING
                    status_msg = "✗ Не найден"
                else:
                    stats['errors'] += 1
                    status_style = self.style.ERROR
                    status_msg = f"✗ Ошибка: {sync.error_message}"

                self.stdout.write(
                    f"[{index}/{total}] {device.serial_number:20} | {status_style(status_msg)}"
                )

            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    f"[{index}/{total}] {device.serial_number:20} | "
                    f"{self.style.ERROR(f'✗ Исключение: {e}')}"
                )

            # Задержка между запросами
            if index < total:
                time.sleep(options['delay'])

        # Итоговая статистика
        elapsed = time.time() - start_time

        self.stdout.write("\n" + "="*70)
        self.stdout.write("ИТОГИ СИНХРОНИЗАЦИИ")
        self.stdout.write("="*70)
        self.stdout.write(f"Проверено устройств:     {total - stats['skipped']}")
        self.stdout.write(self.style.SUCCESS(f"✓ Найдено (1 карточка):  {stats['found_single']}"))
        self.stdout.write(self.style.WARNING(f"⚠ Конфликтов:            {stats['found_multiple']}"))
        self.stdout.write(self.style.WARNING(f"✗ Не найдено:            {stats['not_found']}"))
        self.stdout.write(self.style.ERROR(f"✗ Ошибок:                {stats['errors']}"))

        if stats['skipped'] > 0:
            self.stdout.write(f"⊘ Пропущено:             {stats['skipped']}")

        self.stdout.write(f"\nВремя выполнения:        {elapsed:.1f}с")
        self.stdout.write("="*70 + "\n")

        # Подсказки
        if stats['found_multiple'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ Обнаружено {stats['found_multiple']} конфликтов (несколько карточек на серийник)."
                )
            )
            self.stdout.write("   Проверьте данные в GLPI и удалите дубликаты.\n")

        if stats['not_found'] > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n✗ {stats['not_found']} устройств не найдено в GLPI."
                )
            )
            self.stdout.write("   Возможно, серийники указаны некорректно или устройства не добавлены в GLPI.\n")
