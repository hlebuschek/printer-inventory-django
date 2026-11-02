"""
Группа «Сканирование сетей» для прода, где deploy.sh не запускает bootstrap_roles.

Только добавляет: создаёт группу, если её нет, и дописывает права. Чужие группы и уже
выданные права не трогает (в отличие от bootstrap_roles, который делает permissions.set()).
Состав прав совпадает с netscan_codes в access/management/commands/bootstrap_roles.py.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_NAME = "Сканирование сетей"
CODENAMES = [
    "access_inventory_app",
    "manage_network_scan",
    "view_scannetwork",
    "add_scannetwork",
    "change_scannetwork",
    "delete_scannetwork",
    "view_networkscanrun",
    "view_discovereddevice",
]


def add_group(apps, schema_editor):
    # Права новых моделей Django создаёт только в post_migrate, после ВСЕХ миграций —
    # к этому моменту их ещё нет, поэтому создаём явно.
    app_config = apps.get_app_config("inventory")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    perms = Permission.objects.filter(content_type__app_label="inventory", codename__in=CODENAMES)
    group.permissions.add(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0025_network_scan_organizations"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    # Откат группу не удаляет: в ней уже могут быть пользователи
    operations = [migrations.RunPython(add_group, migrations.RunPython.noop)]
