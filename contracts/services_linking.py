"""
Сервис автоматического связывания устройств между inventory и contracts по серийному номеру.

Используется для синхронизации данных между двумя приложениями:
- inventory.Printer (принтеры для опроса)
- contracts.ContractDevice (устройства в договорах)
"""

import logging
from typing import Optional

from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)


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
    unlinked_devices = (
        ContractDevice.objects.filter(printer__isnull=True)
        .exclude(Q(serial_number__isnull=True) | Q(serial_number=""))
        .select_related("organization")
    )

    if max_devices:
        unlinked_devices = unlinked_devices[:max_devices]

    total_devices = unlinked_devices.count()

    if total_devices == 0:
        logger.info("Нет несвязанных устройств для обработки")
        return {
            "total_devices": 0,
            "linked": 0,
            "not_found": 0,
            "multiple_found": 0,
            "conflicts": 0,
            "errors": 0,
        }

    logger.info(f"Найдено {total_devices} несвязанных устройств")

    # Собираем все принтеры для быстрого поиска
    all_printers = Printer.objects.exclude(Q(serial_number__isnull=True) | Q(serial_number=""))

    printers_by_serial = {}
    for printer in all_printers:
        serial_key = printer.serial_number.strip().lower()
        if serial_key not in printers_by_serial:
            printers_by_serial[serial_key] = []
        printers_by_serial[serial_key].append(printer)

    # Проверяем какие принтеры уже заняты
    used_printers = {}
    for device in ContractDevice.objects.filter(printer__isnull=False).select_related("printer"):
        used_printers[device.printer_id] = device

    # Статистика
    stats = {
        "total_devices": total_devices,
        "linked": 0,
        "not_found": 0,
        "multiple_found": 0,
        "conflicts": 0,
        "errors": 0,
    }

    to_update = []

    # Обработка устройств
    for device in unlinked_devices:
        serial_key = device.serial_number.strip().lower()

        # Ищем принтеры
        matching_printers = printers_by_serial.get(serial_key, [])

        if len(matching_printers) == 0:
            stats["not_found"] += 1
            continue

        if len(matching_printers) > 1:
            stats["multiple_found"] += 1
            logger.warning(f"Найдено {len(matching_printers)} принтеров для серийника {device.serial_number}")

        # Ищем свободный принтер
        chosen_printer = None
        for printer in matching_printers:
            existing_device = used_printers.get(printer.id)

            if existing_device and existing_device.id != device.id:
                # Принтер занят
                stats["conflicts"] += 1
                continue

            chosen_printer = printer
            break

        if not chosen_printer:
            stats["conflicts"] += 1
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
                    device.save(update_fields=["printer"])
                    stats["linked"] += 1

                    logger.info(
                        f"Связано: устройство ID:{device.id} ({device.organization}) -> "
                        f"принтер ID:{device.printer.id}({device.printer.ip_address})"
                    )

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Ошибка сохранения устройства ID:{device.id}: {e}")

    logger.info(
        f"Автоматическое связывание завершено: "
        f"связано {stats['linked']}/{stats['total_devices']}, "
        f"не найдено {stats['not_found']}, "
        f"конфликтов {stats['conflicts']}, "
        f"ошибок {stats['errors']}"
    )

    return stats


