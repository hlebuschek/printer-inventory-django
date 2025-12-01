# Generated manually to fix status field length issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0014_alter_inventoryaccess_options_webparsingtemplate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inventorytask',
            name='status',
            field=models.CharField(
                choices=[
                    ('SUCCESS', 'Успешно'),
                    ('FAILED', 'Ошибка'),
                    ('VALIDATION_ERROR', 'Ошибка валидации'),
                    ('HISTORICAL_INCONSISTENCY', 'Исторические данные не согласованы')
                ],
                db_index=True,
                max_length=30,
                verbose_name='Статус'
            ),
        ),
    ]
