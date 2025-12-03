# Generated manually to allow blank serial_number and snmp_community

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0015_alter_inventorytask_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='printer',
            name='serial_number',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=100,
                verbose_name='Серийный номер'
            ),
        ),
        migrations.AlterField(
            model_name='printer',
            name='snmp_community',
            field=models.CharField(
                blank=True,
                default='public',
                max_length=100,
                verbose_name='SNMP сообщество'
            ),
        ),
    ]
