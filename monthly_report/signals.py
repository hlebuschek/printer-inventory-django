from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import MonthlyReport
from .services import recompute_group

@receiver(pre_save, sender=MonthlyReport)
def _capture_old_group(sender, instance: MonthlyReport, **kwargs):
    # сохраним старый ключ, чтобы после save пересчитать и "старую" группу, если запись перенесли
    if instance.pk:
        try:
            old = MonthlyReport.objects.get(pk=instance.pk)
            instance._old_group_key = (old.month, (old.serial_number or '').strip(), (old.inventory_number or '').strip())
        except MonthlyReport.DoesNotExist:
            instance._old_group_key = None
    else:
        instance._old_group_key = None

@receiver(post_save, sender=MonthlyReport)
def _recompute_new_group(sender, instance: MonthlyReport, created, **kwargs):
    # если группа изменилась — пересчитать старую
    old = getattr(instance, '_old_group_key', None)
    new = (instance.month, (instance.serial_number or '').strip(), (instance.inventory_number or '').strip())
    if old and old != new:
        recompute_group(*old)
    # и обязательно текущую
    recompute_group(*new)

@receiver(post_delete, sender=MonthlyReport)
def _recompute_on_delete(sender, instance: MonthlyReport, **kwargs):
    key = (instance.month, (instance.serial_number or '').strip(), (instance.inventory_number or '').strip())
    recompute_group(*key)
