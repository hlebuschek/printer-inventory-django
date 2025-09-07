from django.utils import timezone
from django.apps import apps

def _get_serial_from_snapshot(instance):
    # подстроитесь под вашу модель: либо instance.serial_number,
    # либо instance.device.serial, и т.п.
    sn = getattr(instance, "serial_number", None)
    if not sn:
        device = getattr(instance, "device", None)
        sn = getattr(device, "serial_number", None) or getattr(device, "serial", None)
    return (sn or "").strip()

def on_inventory_snapshot_saved(sender, instance, created, **kwargs):
    if not created:
        return
    serial = _get_serial_from_snapshot(instance)
    if not serial:
        return

    MonthControl = apps.get_model("monthly_report", "MonthControl")
    from monthly_report.services_inventory_sync import sync_month_from_inventory

    now = timezone.now()
    for mc in MonthControl.objects.filter(edit_until__gt=now).only("month", "edit_until"):
        # только в открытые месяцы; переписываем только авто-поля (only_empty=False),
        # но чужие ручные правки не трогаем (см. флаги *_end_auto).
        sync_month_from_inventory(mc.month, only_empty=False, serial_filter=serial)
