# Generated manually for integrations app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contracts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GLPISync',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('NOT_FOUND', 'Не найден в GLPI'), ('FOUND_SINGLE', 'Найден (1 карточка)'), ('FOUND_MULTIPLE', 'Найдено несколько карточек'), ('ERROR', 'Ошибка при проверке')], max_length=20, verbose_name='Статус')),
                ('searched_serial', models.CharField(max_length=255, verbose_name='Искомый серийник')),
                ('glpi_ids', models.JSONField(blank=True, default=list, help_text='Список ID найденных карточек в GLPI', verbose_name='ID в GLPI')),
                ('glpi_data', models.JSONField(blank=True, default=dict, help_text='Полные данные из GLPI API', verbose_name='Данные из GLPI')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Сообщение об ошибке')),
                ('checked_at', models.DateTimeField(auto_now_add=True, verbose_name='Время проверки')),
                ('checked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Проверил')),
                ('contract_device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='glpi_syncs', to='contracts.contractdevice', verbose_name='Устройство')),
            ],
            options={
                'verbose_name': 'Синхронизация с GLPI',
                'verbose_name_plural': 'Синхронизации с GLPI',
                'ordering': ['-checked_at'],
            },
        ),
        migrations.CreateModel(
            name='IntegrationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('system', models.CharField(choices=[('GLPI', 'GLPI'), ('OTHER', 'Другая система')], max_length=50, verbose_name='Система')),
                ('level', models.CharField(choices=[('DEBUG', 'Отладка'), ('INFO', 'Информация'), ('WARNING', 'Предупреждение'), ('ERROR', 'Ошибка')], default='INFO', max_length=20, verbose_name='Уровень')),
                ('message', models.TextField(verbose_name='Сообщение')),
                ('details', models.JSONField(blank=True, default=dict, help_text='Дополнительная информация в формате JSON', verbose_name='Детали')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Время')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Лог интеграции',
                'verbose_name_plural': 'Логи интеграций',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='glpisync',
            index=models.Index(fields=['contract_device', '-checked_at'], name='integration_contrac_5dc1ef_idx'),
        ),
        migrations.AddIndex(
            model_name='glpisync',
            index=models.Index(fields=['status'], name='integration_status_8bb1b9_idx'),
        ),
        migrations.AddIndex(
            model_name='glpisync',
            index=models.Index(fields=['searched_serial'], name='integration_searche_3e64f3_idx'),
        ),
        migrations.AddIndex(
            model_name='integrationlog',
            index=models.Index(fields=['system', '-created_at'], name='integration_system_d0d8a1_idx'),
        ),
        migrations.AddIndex(
            model_name='integrationlog',
            index=models.Index(fields=['level'], name='integration_level_8bb6c7_idx'),
        ),
    ]
