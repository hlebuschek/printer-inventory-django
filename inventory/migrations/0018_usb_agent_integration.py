from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0017_alter_webparsingrule_field_name"),
    ]

    operations = [
        # 1. Расширяем PollingMethod choices, добавляя USB_API
        migrations.AlterField(
            model_name="printer",
            name="polling_method",
            field=models.CharField(
                choices=[
                    ("SNMP", "SNMP (GLPI Agent)"),
                    ("WEB", "Web Parsing"),
                    ("USB_API", "USB Agent (API)"),
                ],
                default="SNMP",
                max_length=10,
                verbose_name="Метод опроса",
            ),
        ),
        # 2. ConnectionType — для USB-принтеров IP не значим
        migrations.AddField(
            model_name="printer",
            name="connection_type",
            field=models.CharField(
                choices=[("NETWORK", "Сетевой"), ("USB", "USB")],
                db_index=True,
                default="NETWORK",
                help_text="NETWORK для SNMP/Web, USB для принтеров через локальный агент",
                max_length=10,
                verbose_name="Тип подключения",
            ),
        ),
        # 3. usb_identifier — DeviceInstanceId, заполняется только для USB
        migrations.AddField(
            model_name="printer",
            name="usb_identifier",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Заполняется только для USB-принтеров",
                max_length=200,
                verbose_name="USB DeviceInstanceId",
            ),
        ),
        # 4. Сужаем unique_active_ip до сетевых принтеров
        # (USB используют placeholder IP и не должны конфликтовать)
        migrations.RemoveConstraint(
            model_name="printer",
            name="unique_active_ip",
        ),
        migrations.AddConstraint(
            model_name="printer",
            constraint=models.UniqueConstraint(
                condition=Q(("is_active", True), ("connection_type", "NETWORK")),
                fields=("ip_address",),
                name="unique_active_ip",
            ),
        ),
        # 5. data_source в InventoryTask — отличаем USB-опросы от SNMP/Web
        migrations.AddField(
            model_name="inventorytask",
            name="data_source",
            field=models.CharField(
                choices=[
                    ("SNMP_LOCAL", "SNMP (локальный GLPI)"),
                    ("WEB_SCRAPING", "Web Parsing"),
                    ("USB_AGENT", "USB Agent API"),
                ],
                db_index=True,
                default="SNMP_LOCAL",
                max_length=20,
                verbose_name="Источник данных",
            ),
        ),
        # 6. agent_id для аудита USB-опросов
        migrations.AddField(
            model_name="inventorytask",
            name="agent_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Заполняется только для USB-агентов",
                max_length=100,
                verbose_name="ID агента",
            ),
        ),
        migrations.AddIndex(
            model_name="inventorytask",
            index=models.Index(fields=["data_source"], name="inv_task_data_source_idx"),
        ),
        # 7. Новая модель USBAgent
        migrations.CreateModel(
            name="USBAgent",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "agent_id",
                    models.CharField(db_index=True, max_length=100, unique=True, verbose_name="ID агента"),
                ),
                (
                    "token",
                    models.CharField(db_index=True, max_length=128, unique=True, verbose_name="Токен доступа"),
                ),
                (
                    "hostname",
                    models.CharField(blank=True, max_length=200, verbose_name="Имя компьютера"),
                ),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True, verbose_name="Активен"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации"),
                ),
                (
                    "last_seen",
                    models.DateTimeField(auto_now=True, verbose_name="Последняя активность"),
                ),
                (
                    "agent_version",
                    models.CharField(blank=True, default="", max_length=20, verbose_name="Версия агента"),
                ),
            ],
            options={
                "verbose_name": "USB-агент",
                "verbose_name_plural": "USB-агенты",
                "ordering": ["-last_seen"],
            },
        ),
    ]
