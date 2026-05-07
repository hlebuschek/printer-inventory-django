"""Перевод USBAgent.token на хранение в виде SHA-256 hex (token_hash).

Plaintext-токены, которые были выданы агентам до миграции, продолжают работать —
у каждого агента в БД hash от его plaintext-токена, агент шлёт plaintext в Bearer,
сервер хэширует и сравнивает.
"""

import hashlib

from django.db import migrations, models


def forward_hash_existing(apps, schema_editor):
    """Хэшируем существующие plaintext-значения.

    После RenameField столбец content всё ещё plaintext (token_hex(32) = 64 hex chars).
    SHA-256 hex тоже 64 символа из того же алфавита, различить контент нельзя —
    поэтому проход безусловный. Идемпотентность гарантируется тем, что эта
    миграция применяется ровно один раз (Django трекает её в django_migrations)."""
    USBAgent = apps.get_model("inventory", "USBAgent")
    for agent in USBAgent.objects.all():
        if not agent.token_hash:
            continue
        agent.token_hash = hashlib.sha256(agent.token_hash.encode("utf-8")).hexdigest()
        agent.save(update_fields=["token_hash"])


def reverse_noop(apps, schema_editor):
    """Откат невозможен — plaintext-токены утрачены после хэширования."""
    raise RuntimeError(
        "Cannot reverse 0019_usbagent_token_hash: plaintext tokens are not stored. "
        "Generate new tokens by re-registering all agents."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0018_usb_agent_integration"),
    ]

    operations = [
        # 1. Переименовываем колонку: значения сохраняются (пока plaintext).
        migrations.RenameField(
            model_name="usbagent",
            old_name="token",
            new_name="token_hash",
        ),
        # 2. Сужаем длину: SHA-256 hex = 64 символа.
        # На этом шаге значения ещё plaintext (до 128). Нужно сначала хэшировать
        # (хэш короче 128, поэтому AlterField до 64 затем сорвал бы данные).
        # Поэтому: сначала RunPython, потом AlterField.
        migrations.RunPython(forward_hash_existing, reverse_noop),
        # 3. Применяем финальный verbose_name + max_length.
        migrations.AlterField(
            model_name="usbagent",
            name="token_hash",
            field=models.CharField(
                db_index=True,
                max_length=64,
                unique=True,
                verbose_name="Хэш токена доступа",
            ),
        ),
    ]
