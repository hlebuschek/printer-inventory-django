"""Привязка существующих личных токенов Okdesk к дефолтному инстансу."""

from django.db import migrations


def attach_tokens(apps, schema_editor):
    UserOkdeskToken = apps.get_model("access", "UserOkdeskToken")
    OkdeskInstance = apps.get_model("integrations", "OkdeskInstance")

    if not UserOkdeskToken.objects.filter(instance__isnull=True).exists():
        return

    instance = OkdeskInstance.objects.order_by("id").first()
    if instance is None:
        raise RuntimeError(
            "Есть личные токены Okdesk, но нет ни одного OkdeskInstance — "
            "миграция integrations.0014 должна была его создать."
        )
    UserOkdeskToken.objects.filter(instance__isnull=True).update(instance=instance)


class Migration(migrations.Migration):

    dependencies = [
        ("access", "0009_userokdesktoken_instance_alter_userokdesktoken_user_and_more"),
        ("integrations", "0014_okdesk_default_instance"),
    ]

    operations = [
        migrations.RunPython(attach_tokens, migrations.RunPython.noop),
    ]
