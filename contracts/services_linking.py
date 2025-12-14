"""
Сервис автоматического связывания устройств между inventory и contracts по серийному номеру.

Используется для синхронизации данных между двумя приложениями:
- inventory.Printer (принтеры для опроса)
- contracts.ContractDevice (устройства в договорах)
"""

import logging
from typing import Optional, Tuple, List
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)


def link_device_by_serial(serial_number: str, force_relink: bool = False) -> Tuple[bool, str]:
    """
    Связать устройство договора с принтером по серийному номеру.

    Args:
        serial_number: Серийный номер устройства
        force_relink: Принудительно пересвязать, даже если уже связано

    Returns:
        (success, message): Кортеж с результатом и описанием
    """
    from contracts.models import ContractDevice
    from inventory.models import Printer

    if not serial_number or not serial_number.strip():
        return False, "Пустой серийный номер"

    serial_key = serial_number.strip().lower()

    # Ищем устройства договора с таким серийником
    contract_devices = ContractDevice.objects.filter(
        serial_number__iexact=serial_number
    ).exclude(
        Q(serial_number__isnull=True) | Q(serial_number="")
    )

    if not force_relink:
        # Только несвязанные устройства
        contract_devices = contract_devices.filter(printer__isnull=True)

    if not contract_devices.exists():
        if force_relink:
            return False, f"Устройств с серийником {serial_number} не найдено"
        else:
            return False, f"Несвязанных устройств с серийником {serial_number} не найдено"

    # Ищем принтеры с таким же серийным номером
    matching_printers = Printer.objects.filter(
        serial_number__iexact=serial_number
    ).exclude(
        Q(serial_number__isnull=True) | Q(serial_number="")
    )

    printer_count = matching_printers.count()

    if printer_count == 0:
        return False, f"Принтер с серийником {serial_number} не найден в inventory"

    if printer_count > 1:
        logger.warning(
            f"Найдено {printer_count} принтеров с серийником {serial_number}: "
            f"{[f'ID:{p.id}({p.ip_address})' for p in matching_printers]}"
        )

    # Берем первый принтер
    printer = matching_printers.first()

    # Проверяем, не занят ли принтер другим устройством
    existing_link = ContractDevice.objects.filter(printer=printer).exclude(
        serial_number__iexact=serial_number
    ).first()

    if existing_link and not force_relink:
        return False, (
            f"Принтер ID:{printer.id}({printer.ip_address}) уже связан "
            f"с другим устройством ID:{existing_link.id} (серийник: {existing_link.serial_number})"
        )

    # Связываем все устройства с этим серийником
    linked_count = 0
    errors = []

    with transaction.atomic():
        for device in contract_devices:
            try:
                old_printer_id = device.printer_id
                device.printer = printer
                device.save(update_fields=['printer'])
                linked_count += 1

                action = "пересвязано" if old_printer_id else "связано"
                logger.info(
                    f"Устройство ID:{device.id} ({device.organization}) {action} "
                    f"с принтером ID:{printer.id}({printer.ip_address}) по серийнику {serial_number}"
                )

            except Exception as e:
                errors.append(f"ID:{device.id} - {e}")
                logger.error(f"Ошибка связывания устройства ID:{device.id}: {e}")

    if errors:
        return False, f"Связано {linked_count}, ошибок: {len(errors)} - {'; '.join(errors[:3])}"

    device_word = "устройств" if linked_count > 1 else "устройство"
    return True, f"Связано {linked_count} {device_word} с принтером ID:{printer.id}({printer.ip_address})"


def link_all_unlinked_devices(max_devices: Optional[int] = None) -> dict:
    """
    Связать все несвязанные устройства с принтерами по серийным номерам.

    Args:
        max_devices: Максимальное количество устройств для обработки (None = без ограничений)

    Returns:
        dict: Статистика обработки
    """
    from contracts.models import ContractDevice
    from inventory.models import Printer

    logger.info("Запуск автоматического связывания устройств...")

    # Получаем несвязанные устройства с серийными номерами
    unlinked_devices = ContractDevice.objects.filter(
        printer__isnull=True
    ).exclude(
        Q(serial_number__isnull=True) | Q(serial_number="")
    ).select_related('organization')

    if max_devices:
        unlinked_devices = unlinked_devices[:max_devices]

    total_devices = unlinked_devices.count()

    if total_devices == 0:
        logger.info("Нет несвязанных устройств для обработки")
        return {
            'total_devices': 0,
            'linked': 0,
            'not_found': 0,
            'multiple_found': 0,
            'conflicts': 0,
            'errors': 0,
        }

    logger.info(f"Найдено {total_devices} несвязанных устройств")

    # Собираем все принтеры для быстрого поиска
    all_printers = Printer.objects.exclude(
        Q(serial_number__isnull=True) | Q(serial_number="")
    )

    printers_by_serial = {}
    for printer in all_printers:
        serial_key = printer.serial_number.strip().lower()
        if serial_key not in printers_by_serial:
            printers_by_serial[serial_key] = []
        printers_by_serial[serial_key].append(printer)

    # Проверяем какие принтеры уже заняты
    used_printers = {}
    for device in ContractDevice.objects.filter(printer__isnull=False).select_related('printer'):
        used_printers[device.printer_id] = device

    # Статистика
    stats = {
        'total_devices': total_devices,
        'linked': 0,
        'not_found': 0,
        'multiple_found': 0,
        'conflicts': 0,
        'errors': 0,
    }

    to_update = []

    # Обработка устройств
    for device in unlinked_devices:
        serial_key = device.serial_number.strip().lower()

        # Ищем принтеры
        matching_printers = printers_by_serial.get(serial_key, [])

        if len(matching_printers) == 0:
            stats['not_found'] += 1
            continue

        if len(matching_printers) > 1:
            stats['multiple_found'] += 1
            logger.warning(
                f"Найдено {len(matching_printers)} принтеров для серийника {device.serial_number}"
            )

        # Ищем свободный принтер
        chosen_printer = None
        for printer in matching_printers:
            existing_device = used_printers.get(printer.id)

            if existing_device and existing_device.id != device.id:
                # Принтер занят
                stats['conflicts'] += 1
                continue

            chosen_printer = printer
            break

        if not chosen_printer:
            stats['conflicts'] += 1
            continue

        # Устанавливаем связь
        device.printer = chosen_printer
        used_printers[chosen_printer.id] = device
        to_update.append(device)

    # Сохраняем изменения
    if to_update:
        logger.info(f"Сохранение связей для {len(to_update)} устройств...")

        with transaction.atomic():
            for device in to_update:
                try:
                    device.save(update_fields=['printer'])
                    stats['linked'] += 1

                    logger.info(
                        f"Связано: устройство ID:{device.id} ({device.organization}) -> "
                        f"принтер ID:{device.printer.id}({device.printer.ip_address})"
                    )

                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Ошибка сохранения устройства ID:{device.id}: {e}")

    logger.info(
        f"Автоматическое связывание завершено: "
        f"связано {stats['linked']}/{stats['total_devices']}, "
        f"не найдено {stats['not_found']}, "
        f"конфликтов {stats['conflicts']}, "
        f"ошибок {stats['errors']}"
    )

    return stats


def find_matching_devices_for_printer(printer_id: int) -> List[dict]:
    """
    Найти устройства договора, которые могут быть связаны с принтером.

    Args:
        printer_id: ID принтера

    Returns:
        list: Список словарей с информацией об устройствах
    """
    from contracts.models import ContractDevice
    from inventory.models import Printer

    try:
        printer = Printer.objects.get(pk=printer_id)
    except Printer.DoesNotExist:
        return []

    if not printer.serial_number or not printer.serial_number.strip():
        return []

    # Ищем устройства с таким же серийником
    matching_devices = ContractDevice.objects.filter(
        serial_number__iexact=printer.serial_number
    ).select_related('organization', 'printer')

    results = []
    for device in matching_devices:
        results.append({
            'device_id': device.id,
            'serial_number': device.serial_number,
            'organization': str(device.organization),
            'is_linked': device.printer_id == printer_id,
            'current_printer_id': device.printer_id,
        })

    return results
