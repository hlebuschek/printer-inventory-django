# Generated migration to add can_delete_month permission

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_report', '0008_monthcontrol_auto_sync_enabled'),
    ]

    operations = [
        # Permissions are automatically created from Meta.permissions
        # This migration updates the model options to include the new permission
        migrations.AlterModelOptions(
            name='monthlyreport',
            options={
                'ordering': ['month', 'order_number'],
                'permissions': [
                    ('access_monthly_report', 'Доступ к модулю ежемесячных отчётов'),
                    ('upload_monthly_report', 'Загрузка отчётов из Excel'),
                    ('edit_counters_start', 'Право редактировать поля *_start'),
                    ('edit_counters_end', 'Право редактировать поля *_end'),
                    ('sync_from_inventory', 'Подтягивать IP/счётчики из Inventory'),
                    ('view_change_history', 'Просмотр истории изменений'),
                    ('view_monthly_report_metrics', 'Просмотр метрик автозаполнения и пользователей'),
                    ('can_manage_month_visibility', 'Управление видимостью месяцев (публикация/скрытие)'),
                    ('can_reset_auto_polling', 'Возврат принтера на автоопрос'),
                    ('can_poll_all_printers', 'Опрос всех принтеров одновременно'),
                    ('can_delete_month', 'Удаление месяца и всех связанных данных'),
                ],
                'verbose_name': 'Ежемесячный отчёт',
                'verbose_name_plural': 'Ежемесячные отчёты',
            },
        ),
    ]
