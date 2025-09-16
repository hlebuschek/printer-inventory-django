# contracts/management/commands/link_devices_by_serial.py
"""
Команда для проверки и установки связей между устройствами по серийному номеру.

Проходит по всем устройствам из договоров (ContractDevice) и пытается найти
соответствующие принтеры для опроса (Printer) по совпадению серийных номеров.

Примеры использования:

# Анализ без изменений (dry-run)
python manage.py link_devices_by_serial --dry-run

# Установка связей для несвязанных устройств
python manage.py link_devices_by_serial

# Принудительное пересвязывание всех устройств с детальным выводом
python manage.py link_devices_by_serial --force-relink --show-details

# Обработка только устройств определенной организации
python manage.py link_devices_by_serial --filter-org "Мой офис" --dry-run

# Обработка устройств с определенным паттерном серийника
python manage.py link_devices_by_serial --serial-contains "HP" --show-details

# Полный анализ с детальным выводом без сохранения
python manage.py link_devices_by_serial --dry-run --show-details --force-relink
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from contracts.models import ContractDevice
from inventory.models import Printer


class Command(BaseCommand):
    help = (
        "Проверяет и устанавливает связи между ContractDevice и Printer по серийному номеру.\n"
        "Проходит по всем устройствам договора и пытается найти соответствующие принтеры для опроса."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать результаты анализа, не сохранять изменения",
        )
        parser.add_argument(
            "--force-relink",
            action="store_true",
            help="Переустановить связи даже для уже связанных устройств",
        )
        parser.add_argument(
            "--show-details",
            action="store_true",
            help="Показать детальную информацию по каждому устройству",
        )
        parser.add_argument(
            "--filter-org",
            type=str,
            help="Фильтровать только устройства определенной организации (по имени)",
        )
        parser.add_argument(
            "--serial-contains",
            type=str,
            help="Фильтровать только устройства с серийниками, содержащими указанную подстроку",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        force_relink = opts["force_relink"]
        show_details = opts["show_details"]
        filter_org = opts["filter_org"]
        serial_contains = opts["serial_contains"]

        self.stdout.write(
            self.style.SUCCESS("=== Анализ связей устройств по серийным номерам ===")
        )

        # Строим queryset устройств для обработки
        contract_devices = ContractDevice.objects.select_related('organization', 'printer')

        # Фильтры
        if not force_relink:
            contract_devices = contract_devices.filter(printer__isnull=True)

        if filter_org:
            contract_devices = contract_devices.filter(
                organization__name__icontains=filter_org
            )

        if serial_contains:
            contract_devices = contract_devices.filter(
                serial_number__icontains=serial_contains
            )

        # Исключаем устройства без серийного номера
        contract_devices = contract_devices.exclude(
            Q(serial_number__isnull=True) | Q(serial_number="")
        )

        total_devices = contract_devices.count()

        if total_devices == 0:
            self.stdout.write(
                self.style.WARNING("Не найдено устройств для обработки с заданными фильтрами.")
            )
            return

        self.stdout.write(f"Найдено устройств для анализа: {total_devices}")

        if filter_org:
            self.stdout.write(f"Фильтр по организации: {filter_org}")
        if serial_contains:
            self.stdout.write(f"Фильтр по серийному номеру содержит: {serial_contains}")
        if not force_relink:
            self.stdout.write("Обрабатываются только устройства без существующих связей")
        else:
            self.stdout.write("Режим принудительного пересвязывания включен")

        # Счетчики результатов
        stats = {
            'linked': 0,  # Успешно связано
            'already_linked': 0,  # Уже были связаны
            'relinked': 0,  # Пересвязано (при force_relink)
            'not_found': 0,  # Принтер не найден
            'multiple_found': 0,  # Найдено несколько принтеров
            'all_occupied': 0,  # Все найденные принтеры заняты
            'no_serial': 0,  # Нет серийного номера
        }

        problems = {
            'duplicates': [],  # Дубли серийников в принтерах
            'conflicts': [],  # Конфликты связей
            'multiple_contracts': [],  # Несколько устройств договора с одним серийником
        }

        # Предварительно собираем все принтеры для анализа дублей
        all_printers = Printer.objects.exclude(
            Q(serial_number__isnull=True) | Q(serial_number="")
        )

        # Группируем принтеры по серийным номерам (регистронезависимо)
        printers_by_serial = {}
        for printer in all_printers:
            serial_key = printer.serial_number.strip().lower()
            if serial_key not in printers_by_serial:
                printers_by_serial[serial_key] = []
            printers_by_serial[serial_key].append(printer)

        # Находим дубли принтеров
        printer_duplicates = {
            serial: printers for serial, printers in printers_by_serial.items()
            if len(printers) > 1
        }

        if printer_duplicates:
            self.stdout.write(
                self.style.WARNING(f"Обнаружено {len(printer_duplicates)} серийных номеров с дублями принтеров:")
            )
            for serial, printers in printer_duplicates.items():
                problems['duplicates'].append({
                    'serial': serial,
                    'printers': [f"ID:{p.id} IP:{p.ip_address}" for p in printers]
                })
                if show_details:
                    printer_list = ", ".join([f"ID:{p.id}({p.ip_address})" for p in printers])
                    self.stdout.write(f"  {serial}: {printer_list}")

        # Проверяем дубли в устройствах договора
        contract_serials = {}
        for device in contract_devices:
            if not device.serial_number:
                continue
            serial_key = device.serial_number.strip().lower()
            if serial_key not in contract_serials:
                contract_serials[serial_key] = []
            contract_serials[serial_key].append(device)

        contract_duplicates = {
            serial: devices for serial, devices in contract_serials.items()
            if len(devices) > 1
        }

        if contract_duplicates:
            self.stdout.write(
                self.style.WARNING(f"Обнаружено {len(contract_duplicates)} серийных номеров с дублями в договорах:")
            )
            for serial, devices in contract_duplicates.items():
                problems['multiple_contracts'].append({
                    'serial': serial,
                    'devices': [f"ID:{d.id} {d.organization}" for d in devices]
                })
                if show_details:
                    device_list = ", ".join([f"ID:{d.id}({d.organization})" for d in devices])
                    self.stdout.write(f"  {serial}: {device_list}")

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Начинаем обработку устройств...")

        to_update = []

        # Предварительно собираем все уже связанные принтеры для проверки конфликтов
        used_printers = {}
        for device in ContractDevice.objects.filter(printer__isnull=False).select_related('printer'):
            used_printers[device.printer_id] = device

        # Основной цикл обработки
        for device in contract_devices:
            if not device.serial_number or not device.serial_number.strip():
                stats['no_serial'] += 1
                continue

            serial_key = device.serial_number.strip().lower()

            # Проверяем текущее состояние связи
            if device.printer_id and not force_relink:
                stats['already_linked'] += 1
                if show_details:
                    self.stdout.write(
                        f"  SKIP: {device.serial_number} уже связан с принтером ID:{device.printer_id}"
                    )
                continue

            # Ищем принтеры с таким же серийным номером
            matching_printers = printers_by_serial.get(serial_key, [])

            if len(matching_printers) == 0:
                stats['not_found'] += 1
                if show_details:
                    self.stdout.write(
                        f"  NOT_FOUND: {device.serial_number} (ID:{device.id}) - принтер не найден"
                    )
                continue

            elif len(matching_printers) > 1:
                stats['multiple_found'] += 1
                if show_details:
                    printer_info = ", ".join([f"ID:{p.id}({p.ip_address})" for p in matching_printers])
                    self.stdout.write(
                        f"  MULTIPLE: {device.serial_number} (ID:{device.id}) - найдено принтеров: {printer_info}"
                    )
                # Берем первый принтер, но отмечаем как проблему
                problems['conflicts'].append({
                    'serial': device.serial_number,
                    'device_id': device.id,
                    'printers': [f"ID:{p.id}({p.ip_address})" for p in matching_printers],
                    'action': 'used_first'
                })

            # Ищем свободный принтер из найденных
            chosen_printer = None
            for printer in matching_printers:
                # Проверяем, не занят ли принтер другим устройством
                existing_device = used_printers.get(printer.id)

                if existing_device and existing_device.id != device.id:
                    # Принтер уже занят другим устройством
                    problems['conflicts'].append({
                        'serial': device.serial_number,
                        'device_id': device.id,
                        'printer_id': printer.id,
                        'conflict_device_id': existing_device.id,
                        'action': 'printer_already_linked'
                    })
                    if show_details:
                        self.stdout.write(
                            f"  CONFLICT: принтер ID:{printer.id}({printer.ip_address}) уже связан с устройством ID:{existing_device.id}"
                        )
                    continue

                # Найден свободный принтер
                chosen_printer = printer
                break

            if not chosen_printer:
                # Все найденные принтеры заняты
                stats['all_occupied'] += 1
                if show_details:
                    self.stdout.write(
                        f"  ALL_OCCUPIED: {device.serial_number} (ID:{device.id}) - все найденные принтеры уже заняты"
                    )
                continue

            # Устанавливаем связь
            old_printer_id = device.printer_id

            # Если у устройства уже была связь, освобождаем старый принтер
            if old_printer_id and old_printer_id in used_printers:
                del used_printers[old_printer_id]

            device.printer = chosen_printer
            # Резервируем принтер в нашем локальном реестре
            used_printers[chosen_printer.id] = device

            if force_relink and old_printer_id:
                stats['relinked'] += 1
                action = "RELINK"
            else:
                stats['linked'] += 1
                action = "LINK"

            to_update.append(device)

            if show_details:
                self.stdout.write(
                    f"  {action}: {device.serial_number} (устройство ID:{device.id}) -> принтер ID:{chosen_printer.id}({chosen_printer.ip_address})"
                )

        # Сохранение изменений
        if not dry_run and to_update:
            self.stdout.write(f"\nСохраняем изменения для {len(to_update)} устройств...")
            try:
                with transaction.atomic():
                    # Используем поштучное сохранение для избежания конфликтов уникальности
                    saved_count = 0
                    errors_count = 0

                    for device in to_update:
                        try:
                            device.save(update_fields=['printer'])
                            saved_count += 1
                        except Exception as e:
                            errors_count += 1
                            if show_details:
                                self.stdout.write(
                                    f"  ERROR: Не удалось сохранить устройство ID:{device.id} - {e}"
                                )

                    if errors_count > 0:
                        self.stdout.write(
                            self.style.WARNING(f"Сохранено: {saved_count}, ошибок: {errors_count}")
                        )
                    else:
                        self.stdout.write(self.style.SUCCESS("Все изменения успешно сохранены!"))

            except Exception as e:
                raise CommandError(f"Критическая ошибка при сохранении: {e}")
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(f"\nDRY-RUN: {len(to_update)} устройств будет обновлено при реальном запуске")
            )

        # Итоговая статистика
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("ИТОГОВАЯ СТАТИСТИКА:"))
        self.stdout.write(f"  Всего обработано устройств: {total_devices}")
        self.stdout.write(f"  Успешно связано: {stats['linked']}")
        if force_relink:
            self.stdout.write(f"  Пересвязано: {stats['relinked']}")
        self.stdout.write(f"  Уже были связаны: {stats['already_linked']}")
        self.stdout.write(f"  Принтер не найден: {stats['not_found']}")
        self.stdout.write(f"  Найдено несколько принтеров: {stats['multiple_found']}")
        self.stdout.write(f"  Все найденные принтеры заняты: {stats['all_occupied']}")
        self.stdout.write(f"  Без серийного номера: {stats['no_serial']}")

        # Детали проблем
        if problems['duplicates']:
            self.stdout.write(f"\n{self.style.WARNING('ПРОБЛЕМЫ С ДУБЛЯМИ ПРИНТЕРОВ:')}")
            for dup in problems['duplicates'][:10]:  # показываем первые 10
                self.stdout.write(f"  {dup['serial']}: {', '.join(dup['printers'])}")
            if len(problems['duplicates']) > 10:
                self.stdout.write(f"  ... и ещё {len(problems['duplicates']) - 10}")

        if problems['multiple_contracts']:
            self.stdout.write(f"\n{self.style.WARNING('ДУБЛИ В УСТРОЙСТВАХ ДОГОВОРА:')}")
            for dup in problems['multiple_contracts'][:10]:
                self.stdout.write(f"  {dup['serial']}: {', '.join(dup['devices'])}")

        if problems['conflicts']:
            self.stdout.write(f"\n{self.style.WARNING('КОНФЛИКТЫ СВЯЗЕЙ:')}")
            for conf in problems['conflicts'][:10]:
                if conf['action'] == 'printer_already_linked':
                    self.stdout.write(
                        f"  Принтер ID:{conf['printer_id']} уже связан с устройством ID:{conf['conflict_device_id']}"
                    )

        if dry_run:
            self.stdout.write(f"\n{self.style.SUCCESS('Для применения изменений запустите команду без --dry-run')}")
        else:
            self.stdout.write(f"\n{self.style.SUCCESS('Обработка завершена!')}")

        # Рекомендации
        if stats['multiple_found'] > 0 or stats['all_occupied'] > 0:
            self.stdout.write(f"\n{self.style.WARNING('РЕКОМЕНДАЦИИ:')}")

        if stats['multiple_found'] > 0:
            self.stdout.write("  Проверьте дубли принтеров в БД - возможно, есть устройства с одинаковыми серийниками")

        if stats['all_occupied'] > 0:
            self.stdout.write("  Некоторые принтеры уже связаны с другими устройствами")
            self.stdout.write("  Используйте --force-relink для принудительного пересвязывания")
            self.stdout.write("  Или проверьте дубли серийников в устройствах договора")

        if stats['not_found'] > 0:
            self.stdout.write("  Устройства без соответствующих принтеров не будут опрашиваться автоматически")
            self.stdout.write("  Рассмотрите возможность добавления недостающих принтеров в систему опроса")