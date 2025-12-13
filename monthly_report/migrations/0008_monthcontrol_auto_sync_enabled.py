# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_report', '0007_add_custom_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthcontrol',
            name='auto_sync_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Автоматически обновлять данные из inventory при опросе принтеров. '
                          'Отключите для точечного ручного редактирования без риска перезаписи.',
                verbose_name='Автосинхронизация включена'
            ),
        ),
    ]
