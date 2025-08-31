from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import ContractDevice
from inventory.models import Printer

@receiver(pre_save, sender=ContractDevice)
def autolink_printer(sender, instance: ContractDevice, **kwargs):
    if instance.printer_id or not instance.serial_number:
        return
    sn = instance.serial_number.strip()
    try:
        p = Printer.objects.get(serial_number__iexact=sn)
        instance.printer = p
    except Printer.DoesNotExist:
        pass
