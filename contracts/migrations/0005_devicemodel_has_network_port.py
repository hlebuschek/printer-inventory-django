# Generated manually on 2025-11-22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0004_cartridge_devicemodelcartridge'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicemodel',
            name='has_network_port',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Устройство имеет встроенный сетевой порт',
                verbose_name='Наличие сетевого порта'
            ),
        ),
    ]
