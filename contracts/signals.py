"""
Signals для автоматического связывания устройств между inventory и contracts.
"""

import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import ContractDevice
from inventory.models import Printer

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ContractDevice)
def autolink_printer(sender, instance: ContractDevice, **kwargs):
    """
    Автоматическое связывание устройства с принтером при сохранении.
    Работает при создании нового устройства или изменении серийного номера.
    """
    # Если уже есть связь, не трогаем
    if instance.printer_id:
        return

    # Если нет серийного номера, ничего не делаем
    if not instance.serial_number:
        return

    sn = instance.serial_number.strip()

    try:
        # Ищем АКТИВНЫЙ принтер по серийному номеру (регистронезависимо)
        matching_printers = Printer.objects.filter(
            serial_number__iexact=sn,
            is_active=True
        )
        printer_count = matching_printers.count()

        if printer_count == 0:
            logger.debug(f"Принтер с серийником {sn} не найден в inventory")
            return

        if printer_count > 1:
            logger.warning(
                f"Найдено {printer_count} принтеров с серийником {sn}, "
                f"используем первый (ID:{matching_printers.first().id})"
            )

        printer = matching_printers.first()

        # Проверяем, не занят ли принтер другим устройством
        existing = ContractDevice.objects.filter(printer=printer).exclude(pk=instance.pk).first()

        if existing:
            logger.warning(
                f"Принтер ID:{printer.id} уже связан с устройством ID:{existing.id}, "
                f"пропускаем связывание для устройства {sn}"
            )
            return

        instance.printer = printer
        logger.info(
            f"Устройство с серийником {sn} автоматически связано с принтером "
            f"ID:{printer.id}({printer.ip_address})"
        )

    except Exception as e:
        logger.error(f"Ошибка при автоматическом связывании устройства {sn}: {e}")


@receiver(post_save, sender=Printer)
def link_printer_on_save(sender, instance, created, **kwargs):
    """
    При создании/изменении принтера автоматически связываем его с устройствами договора.
    """
    # Проверяем что у принтера есть серийный номер
    if not instance.serial_number or not instance.serial_number.strip():
        return

    # Работаем только при создании нового принтера
    if not created:
        return

    sn = instance.serial_number.strip()

    try:
        # Ищем несвязанные устройства с таким серийником
        unlinked_devices = ContractDevice.objects.filter(
            serial_number__iexact=sn,
            printer__isnull=True
        )

        linked_count = 0

        for device in unlinked_devices:
            device.printer = instance
            device.save(update_fields=['printer'])
            linked_count += 1

            logger.info(
                f"Устройство ID:{device.id} ({device.organization}) автоматически связано "
                f"с новым принтером ID:{instance.id}({instance.ip_address})"
            )

        if linked_count > 0:
            logger.info(
                f"Новый принтер ID:{instance.id} связан с {linked_count} устройствами по серийнику {sn}"
            )

    except Exception as e:
        logger.error(f"Ошибка при связывании принтера ID:{instance.id}: {e}")

