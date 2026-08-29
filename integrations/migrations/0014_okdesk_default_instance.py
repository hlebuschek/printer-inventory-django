"""
Привязка существующих okdesk-данных к дефолтному инстансу.

До этой миграции интеграция работала с единственным инстансом Okdesk,
чей адрес и системный токен задавались через env (OKDESK_API_URL,
OKDESK_API_TOKEN). Миграция создаёт OkdeskInstance из этих значений
и привязывает к нему все существующие заявки и комментарии.
"""

import os

from django.db import migrations


def _env_verify_ssl():
    return os.getenv("OKDESK_VERIFY_SSL", "True").lower() in ("true", "1", "yes")


def create_default_instance(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    OkdeskInstance = apps.get_model("integrations", "OkdeskInstance")
    OkdeskIssue = apps.get_model("integrations", "OkdeskIssue")
    OkdeskComment = apps.get_model("integrations", "OkdeskComment")

    api_token = os.getenv("OKDESK_API_TOKEN", "")
    has_data = OkdeskIssue.objects.exists() or OkdeskComment.objects.exists()
    provider = ServiceProvider.objects.filter(issue_tracker="okdesk").order_by("id").first()

    if not (provider or has_data or api_token):
        return  # свежая БД без okdesk — инстанс создавать не из чего

    if provider is None:
        provider = ServiceProvider.objects.create(name="АМБ", code="amb", issue_tracker="okdesk")

    encrypted = ""
    if api_token:
        from access.crypto import encrypt_token

        encrypted = encrypt_token(api_token)

    instance = OkdeskInstance.objects.create(
        service_provider=provider,
        api_url=os.getenv("OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1"),
        encrypted_token=encrypted,
        verify_ssl=_env_verify_ssl(),
        is_active=True,
    )

    OkdeskIssue.objects.filter(instance__isnull=True).update(instance=instance)
    OkdeskComment.objects.filter(instance__isnull=True).update(instance=instance)


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0013_okdeskinstance_and_more"),
        ("contracts", "0008_seed_service_providers"),
    ]

    operations = [
        migrations.RunPython(create_default_instance, migrations.RunPython.noop),
    ]
