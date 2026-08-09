from django.db import migrations

PROVIDERS = [
    ("АМБ", "amb", "okdesk"),
    ("Tonex", "tonex", "none"),
]


def seed(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    ContractDevice = apps.get_model("contracts", "ContractDevice")

    for name, code, issue_tracker in PROVIDERS:
        ServiceProvider.objects.get_or_create(
            code=code,
            defaults={"name": name, "issue_tracker": issue_tracker},
        )

    # До появления подрядчиков весь парк обслуживала АМБ через Okdesk
    amb = ServiceProvider.objects.get(code="amb")
    ContractDevice.objects.filter(service_provider__isnull=True).update(service_provider=amb)


def unseed(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    ContractDevice = apps.get_model("contracts", "ContractDevice")

    ContractDevice.objects.filter(service_provider__code__in=[code for _, code, _ in PROVIDERS]).update(
        service_provider=None
    )
    ServiceProvider.objects.filter(code__in=[code for _, code, _ in PROVIDERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0007_serviceprovider_contractdevice_service_provider_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
