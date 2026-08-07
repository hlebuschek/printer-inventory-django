from django.db import migrations, models

# Адрес, который до появления подрядчиков был захардкожен в generate_email_for_device
AMB_SUPPORT_EMAIL = "sd@abi.com.ru"


def set_amb_email(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    ServiceProvider.objects.filter(code="amb").update(support_email=AMB_SUPPORT_EMAIL)


def clear_amb_email(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    ServiceProvider.objects.filter(code="amb").update(support_email="")


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0008_seed_service_providers"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceprovider",
            name="support_email",
            field=models.EmailField(
                blank=True,
                help_text="Адрес получателя для письма-заявки. Пусто — письмо по устройствам подрядчика не формируется",
                max_length=254,
                verbose_name="Почта сервис-деска",
            ),
        ),
        migrations.RunPython(set_amb_email, clear_amb_email),
    ]
