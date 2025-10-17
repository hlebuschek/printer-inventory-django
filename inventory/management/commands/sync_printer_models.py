# inventory/management/commands/sync_printer_models.py
"""
Management команда для синхронизации названий моделей принтеров
между contracts.ContractDevice и inventory.Printer по серийным номерам.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Count
from django.db.models.functions import Lower
from contracts.models import ContractDevice
from inventory.models import Printer


class Command(BaseCommand):
    help = 'Синхронизирует названия моделей принтеров из contracts в inventory по серийным номерам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать изменения без применения',
        )
        parser.add_argument(
            '--organization',
            type=str,
            help='Синхронизировать только для указанной организации',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Обновить даже если модель уже заполнена',
        )
        parser.add_argument(
            '--show-duplicates',
            action='store_true',
            help='Показать дубликаты серийных номеров в contracts',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        organization = options.get('organization')
        force = options['force']
        show_duplicates = options['show_duplicates']

        self.stdout.write(self.style.MIGRATE_HEADING('🔄 Синхронизация моделей принтеров'))
        self.stdout.write('-' * 80)

        # Проверка дубликатов серийников в contracts
        if show_duplicates:
            self._show_duplicates()
            return

        # Фильтруем устройства по организации если указана
        devices_qs = ContractDevice.objects.select_related('model__manufacturer', 'organization')

        if organization:
            devices_qs = devices_qs.filter(organization__name__iexact=organization)
            self.stdout.write(f"📌 Фильтр по организации: {organization}")

        # Получаем устройства с заполненным серийником
        devices = devices_qs.exclude(
            Q(serial_number__isnull=True) | Q(serial_number='')
        )

        total_devices = devices.count()
        self.stdout.write(f"📊 Найдено устройств в contracts с серийниками: {total_devices}")

        if total_devices == 0:
            self.stdout.write(self.style.WARNING('⚠️  Нет устройств для синхронизации'))
            return

        # Счётчики
        matched = 0
        updated = 0
        skipped = 0
        errors = 0
        changes = []

        # Обрабатываем каждое устройство
        for device in devices:
            try:
                # Ищем принтер по серийнику (без учёта регистра)
                printers = Printer.objects.annotate(
                    sn_lower=Lower('serial_number')
                ).filter(
                    sn_lower=device.serial_number.lower()
                )

                if not printers.exists():
                    continue

                matched += 1

                # Если найдено несколько принтеров с одним серийником - предупреждение
                if printers.count() > 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  Найдено {printers.count()} принтеров с SN: {device.serial_number}"
                        )
                    )

                # Правильное название модели из contracts (только модель, без производителя)
                correct_model = device.model.name  # Например: "LaserJet Pro M404dn"

                # Обновляем все найденные принтеры
                for printer in printers:
                    # Пропускаем если модель уже правильная
                    if printer.model == correct_model:
                        skipped += 1
                        continue

                    # Пропускаем если модель уже заполнена и не указан --force
                    if printer.model and not force:
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"⏭️  Пропущено (модель уже заполнена, используйте --force): "
                                f"SN:{device.serial_number} | "
                                f"Старое: '{printer.model}' → Новое: '{correct_model}'"
                            )
                        )
                        continue

                    # Сохраняем информацию об изменении
                    change_info = {
                        'printer_ip': printer.ip_address,
                        'serial_number': device.serial_number,
                        'old_model': printer.model or '(пусто)',
                        'new_model': correct_model,
                        'organization': device.organization.name,
                    }
                    changes.append(change_info)

                    # Применяем изменение если не dry-run
                    if not dry_run:
                        printer.model = correct_model
                        printer.save(update_fields=['model'])

                    updated += 1

                    # Выводим информацию об изменении
                    style = self.style.SUCCESS if not dry_run else self.style.WARNING
                    prefix = "✅" if not dry_run else "🔍"
                    self.stdout.write(
                        style(
                            f"{prefix} {printer.ip_address} | SN:{device.serial_number} | "
                            f"{device.organization.name}\n"
                            f"   Было: '{change_info['old_model']}'\n"
                            f"   Стало: '{correct_model}'"
                        )
                    )

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Ошибка при обработке SN:{device.serial_number}: {str(e)}"
                    )
                )

        # Итоговая статистика
        self.stdout.write('-' * 80)
        self.stdout.write(self.style.MIGRATE_HEADING('📈 Результаты синхронизации:'))
        self.stdout.write(f"  Устройств в contracts: {total_devices}")
        self.stdout.write(f"  Совпадений по серийникам: {matched}")
        self.stdout.write(self.style.SUCCESS(f"  Обновлено: {updated}"))
        self.stdout.write(self.style.WARNING(f"  Пропущено: {skipped}"))
        if errors:
            self.stdout.write(self.style.ERROR(f"  Ошибок: {errors}"))

        if dry_run and changes:
            self.stdout.write('\n' + self.style.WARNING(
                '⚠️  Режим тестирования (--dry-run). '
                'Для применения изменений запустите без этого флага.'
            ))

        # Сохраняем отчёт в файл если были изменения
        if changes and not dry_run:
            self._save_report(changes)

    def _show_duplicates(self):
        """Показывает дубликаты серийных номеров в contracts"""
        self.stdout.write(self.style.MIGRATE_HEADING('🔍 Проверка дубликатов серийных номеров'))
        self.stdout.write('-' * 80)

        # Находим дубликаты (без учёта регистра)
        from django.db.models import Count
        from django.db.models.functions import Lower

        duplicates = (
            ContractDevice.objects
            .exclude(Q(serial_number__isnull=True) | Q(serial_number=''))
            .annotate(sn_lower=Lower('serial_number'))
            .values('sn_lower')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
            .order_by('-count')
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('✅ Дубликатов не найдено'))
            return

        self.stdout.write(
            self.style.WARNING(f'⚠️  Найдено дубликатов: {duplicates.count()}')
        )

        for dup in duplicates:
            sn = dup['sn_lower']
            count = dup['count']

            devices = ContractDevice.objects.annotate(
                sn_lower=Lower('serial_number')
            ).filter(sn_lower=sn).select_related('organization', 'model')

            self.stdout.write(f"\n📦 Серийник: {sn.upper()} ({count} записей)")
            for device in devices:
                self.stdout.write(
                    f"   • {device.organization.name} | {device.model} | "
                    f"{device.city.name} | {device.address}"
                )

    def _save_report(self, changes):
        """Сохраняет отчёт об изменениях в файл"""
        import csv
        from datetime import datetime

        filename = f'sync_models_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=['printer_ip', 'serial_number', 'old_model', 'new_model', 'organization']
                )
                writer.writeheader()
                writer.writerows(changes)

            self.stdout.write(
                self.style.SUCCESS(f'\n💾 Отчёт сохранён: {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка сохранения отчёта: {str(e)}')
            )