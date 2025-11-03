from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0004_cartridge_devicemodelcartridge'),
        ('inventory', '0009_alter_inventorytask_status_and_more'),
    ]

    operations = [
        # Просто регистрируем существующее поле в Django ORM
        # SQL не выполняем, так как колонка уже есть в БД
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='printer',
                    name='device_model',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Модель из справочника contracts',
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='inventory_printers',
                        to='contracts.devicemodel',
                        verbose_name='Модель оборудования'
                    ),
                ),
            ],
            # database_operations пустой, так как колонка уже существует
            database_operations=[],
        ),
        
        # Изменяем описание существующего поля model
        migrations.AlterField(
            model_name='printer',
            name='model',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Устаревшее текстовое поле. Используйте device_model.',
                max_length=200,
                verbose_name='Модель (текст, устарело)'
            ),
        ),
    ]