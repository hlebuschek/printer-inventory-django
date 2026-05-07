"""Partial unique constraint: серийник уникален среди активных USB-принтеров.

Защищает от race-condition в `_resolve_printer`, когда два одновременных
USB-reading'а от одного агента могли создать дубликат Printer-row.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0019_usbagent_token_hash"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="printer",
            constraint=models.UniqueConstraint(
                fields=["serial_number"],
                condition=Q(is_active=True) & Q(connection_type="USB"),
                name="unique_active_usb_serial",
            ),
        ),
    ]
