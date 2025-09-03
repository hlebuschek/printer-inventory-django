from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

INV_APP_PERMS = {
    "access": "inventory.access_inventory_app",
    "run": "inventory.run_inventory",
    "export": ["inventory.export_printers", "inventory.export_amb_report"],
}

CON_APP_PERMS = {
    "access": "contracts.access_contracts_app",
    "export": ["contracts.export_contracts"],
}

# Какие модели считаем «основными» для CRUD
INV_MODELS = ["printer", "organization", "inventorytask"]  # pagecounter обычно только view
CON_MODELS = ["contractdevice", "city", "manufacturer", "devicemodel", "contractstatus"]

CODENAMES = lambda act, model: f"{act}_{model}"

class Command(BaseCommand):
    help = "Create default RBAC groups and assign permissions"

    def add_model_perms(self, perms, app_label, models, acts):
        for model in models:
            for act in acts:
                perms.add(f"{app_label}.{CODENAMES(act, model)}")
        # Всегда включаем view_* для всех моделей приложения
        for ct in ContentType.objects.filter(app_label=app_label):
            perms.add(f"{app_label}.view_{ct.model}")
        return perms

    def get_permissions(self, perm_codes):
        objs = set()
        for code in perm_codes:
            if isinstance(code, (list, tuple, set)):
                for c in code:
                    try:
                        objs.add(Permission.objects.get(codename=c.split(".")[-1], content_type__app_label=c.split(".")[0]))
                    except Permission.DoesNotExist:
                        self.stderr.write(self.style.WARNING(f"Permission not found: {c}"))
            else:
                try:
                    objs.add(Permission.objects.get(codename=code.split(".")[-1], content_type__app_label=code.split(".")[0]))
                except Permission.DoesNotExist:
                    self.stderr.write(self.style.WARNING(f"Permission not found: {code}"))
        return objs

    def handle(self, *args, **options):
        # Inventory Viewer
        inv_viewer_codes = set([INV_APP_PERMS["access"], *INV_APP_PERMS["export"]])
        inv_viewer_codes = self.add_model_perms(inv_viewer_codes, "inventory", [], acts=[])  # только view_* для всех моделей

        # Inventory Editor = Viewer + CRUD основных моделей
        inv_editor_codes = set(inv_viewer_codes)
        inv_editor_codes = self.add_model_perms(inv_editor_codes, "inventory", INV_MODELS, acts=["add", "change", "delete"])

        # Inventory Admin = Editor + run_inventory
        inv_admin_codes = set(inv_editor_codes)
        inv_admin_codes.add(INV_APP_PERMS["run"])

        # Contracts Viewer
        con_viewer_codes = set([CON_APP_PERMS["access"], *CON_APP_PERMS["export"]])
        con_viewer_codes = self.add_model_perms(con_viewer_codes, "contracts", [], acts=[])

        # Contracts Editor
        con_editor_codes = set(con_viewer_codes)
        con_editor_codes = self.add_model_perms(con_editor_codes, "contracts", CON_MODELS, acts=["add", "change", "delete"])

        # Contracts Admin (пока без доп. спецправ)
        con_admin_codes = set(con_editor_codes)

        groups = {
            "Inventory Viewer": inv_viewer_codes,
            "Inventory Editor": inv_editor_codes,
            "Inventory Admin": inv_admin_codes,
            "Contracts Viewer": con_viewer_codes,
            "Contracts Editor": con_editor_codes,
            "Contracts Admin": con_admin_codes,
        }

        for name, codes in groups.items():
            group, _ = Group.objects.get_or_create(name=name)
            perms = self.get_permissions(codes)
            group.permissions.set(list(perms))
            group.save()
            self.stdout.write(self.style.SUCCESS(f"Group ensured: {name} ({len(perms)} perms)"))

        self.stdout.write(self.style.SUCCESS("RBAC groups initialized."))