from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import Group, Permission

# Утилиты ─────────────────────────────────────────────────────────────────────

def get_perm(app_label: str, codename: str) -> Permission | None:
    try:
        return Permission.objects.select_related("content_type").get(
            content_type__app_label=app_label,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None

def get_perm_by_name(name: str, app_label: str | None = None) -> Permission | None:
    qs = Permission.objects.select_related("content_type").filter(name=name)
    if app_label:
        qs = qs.filter(content_type__app_label=app_label)
    return qs.first()

def add_perms(group: Group, perms: list[Permission | None], log: list[str]):
    to_add = [p for p in perms if p is not None]
    missing = [p for p in perms if p is None]
    if to_add:
        group.permissions.add(*to_add)
    for m in missing:
        # m is None — вывести диагностическое сообщение мы не можем без контекста,
        # поэтому лог формируем в вызывающем коде
        pass

# Команда ─────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Создать/обновить стандартные группы и права для Inventory и Contracts"

    @transaction.atomic
    def handle(self, *args, **options):
        logs: list[str] = []

        # === Базовые наборы стандартных (CRUD) прав по моделям ===
        inv_view = [
            get_perm("inventory", "view_printer"),
            get_perm("inventory", "view_organization"),
            get_perm("inventory", "view_inventorytask"),
            get_perm("inventory", "view_pagecounter"),
        ]
        inv_edit_minor = [
            get_perm("inventory", "change_printer"),
        ]
        inv_all = inv_view + [
            get_perm("inventory", "add_printer"),
            get_perm("inventory", "change_printer"),
            get_perm("inventory", "delete_printer"),
            get_perm("inventory", "add_organization"),
            get_perm("inventory", "change_organization"),
            get_perm("inventory", "delete_organization"),
            get_perm("inventory", "add_inventorytask"),
            get_perm("inventory", "change_inventorytask"),
            get_perm("inventory", "delete_inventorytask"),
            get_perm("inventory", "add_pagecounter"),
            get_perm("inventory", "change_pagecounter"),
            get_perm("inventory", "delete_pagecounter"),
        ]

        ctr_view = [
            get_perm("contracts", "view_city"),
            get_perm("contracts", "view_manufacturer"),
            get_perm("contracts", "view_devicemodel"),
            get_perm("contracts", "view_contractstatus"),
            get_perm("contracts", "view_contractdevice"),
        ]
        ctr_add_change = [
            get_perm("contracts", "add_city"),
            get_perm("contracts", "change_city"),
            get_perm("contracts", "add_manufacturer"),
            get_perm("contracts", "change_manufacturer"),
            get_perm("contracts", "add_devicemodel"),
            get_perm("contracts", "change_devicemodel"),
            get_perm("contracts", "add_contractstatus"),
            get_perm("contracts", "change_contractstatus"),
            get_perm("contracts", "add_contractdevice"),
            get_perm("contracts", "change_contractdevice"),
        ]
        ctr_all = ctr_view + ctr_add_change + [
            get_perm("contracts", "delete_city"),
            get_perm("contracts", "delete_manufacturer"),
            get_perm("contracts", "delete_devicemodel"),
            get_perm("contracts", "delete_contractstatus"),
            get_perm("contracts", "delete_contractdevice"),
        ]

        # === Кастомные права (по именам) ===
        inv_custom = [
            get_perm_by_name("Can run inventory scans", app_label="inventory"),
            get_perm_by_name("Can export printers to Excel", app_label="inventory"),
            get_perm_by_name("Can export AMB report", app_label="inventory"),
        ]
        ctr_custom = [
            get_perm_by_name("Can access Contracts app", app_label="contracts"),
            get_perm_by_name("Can export contracts to Excel", app_label="contracts"),
        ]
        access_custom = [
            get_perm("access", "view_entity_changes"),
        ]

        # Проверка отсутствующих прав — соберём список для вывода
        def check_missing(label: str, items: list[Permission | None]):
            miss = [i for i in items if i is None]
            if miss:
                logs.append(f"[WARN] В наборе «{label}» отсутствуют {len(miss)} прав(а). "
                            f"Проверьте, что приложения мигрированы и кастомные права созданы.")

        check_missing("inv_view", inv_view)
        check_missing("inv_edit_minor", inv_edit_minor)
        check_missing("inv_all", inv_all)
        check_missing("ctr_view", ctr_view)
        check_missing("ctr_add_change", ctr_add_change)
        check_missing("ctr_all", ctr_all)
        check_missing("inv_custom", inv_custom)
        check_missing("ctr_custom", ctr_custom)
        check_missing("access_custom", access_custom)

        # === Создание/обновление групп ===
        groups_spec = {
            "Наблюдатель":        inv_view + ctr_view + access_custom,
            "Оператор инвентаризации": inv_view + ctr_view + inv_edit_minor + inv_custom + access_custom,
            "Контент-менеджер договоров": ctr_view + ctr_add_change + ctr_custom + access_custom,
            "Администратор приложения":   inv_all + inv_custom + ctr_all + ctr_custom + access_custom,
        }

        for group_name, perms in groups_spec.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            before = group.permissions.count()
            add_perms(group, perms, logs)
            after = group.permissions.count()
            self.stdout.write(self.style.SUCCESS(
                f"Группа «{group_name}»: прав было {before}, стало {after}"
            ))

        # Итоговые предупреждения
        if logs:
            self.stdout.write("")  # пустая строка
            for line in logs:
                self.stdout.write(self.style.WARNING(line))
