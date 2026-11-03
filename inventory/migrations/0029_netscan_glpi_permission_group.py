"""
Группа «Сканирование сетей — постановка в GLPI» для прода, где deploy.sh не запускает bootstrap_roles.

Только добавляет (как 0026): права «Сканирования сетей» + push_netscan_to_glpi.
Состав совпадает с netscan_glpi_codes в access/management/commands/bootstrap_roles.py.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_NAME = "Сканирование сетей — постановка в GLPI"
CODENAMES = [
    "access_inventory_app",
    "manage_network_scan",
    "push_netscan_to_glpi",
    "view_scannetwork",
    "add_scannetwork",
    "change_scannetwork",
    "delete_scannetwork",
    "view_networkscanrun",
    "view_discovereddevice",
]


def add_group(apps, schema_editor):
    app_config = apps.get_app_config("inventory")
    app_config.models_module = True
    create_permissions(app_config, apps=apps, verbosity=0)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(*Permission.objects.filter(content_type__app_label="inventory", codename__in=CODENAMES))


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0028_netscan_glpi_push"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(add_group, migrations.RunPython.noop)]
