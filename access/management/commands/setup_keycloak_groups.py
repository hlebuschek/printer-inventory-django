from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Создать группы по умолчанию для пользователей Keycloak"

    @transaction.atomic
    def handle(self, *args, **options):
        # Создаём группу "Наблюдатель" если её нет
        group, created = Group.objects.get_or_create(name="Наблюдатель")

        if created:
            self.stdout.write(self.style.SUCCESS('Создана группа "Наблюдатель"'))
        else:
            self.stdout.write(self.style.WARNING('Группа "Наблюдатель" уже существует'))

        # Базовые права просмотра + заполнение данных приёмки (счётчик, PDF).
        # Добавляем недостающие права идемпотентно, ничего не удаляя.
        perms_to_add = [
            "inventory.view_printer",
            "inventory.view_organization",
            "inventory.view_inventorytask",
            "inventory.view_pagecounter",
            "contracts.view_contractdevice",
            "contracts.view_city",
            "contracts.view_manufacturer",
            "contracts.view_devicemodel",
            "contracts.view_contractstatus",
            "contracts.access_contracts_app",
            "contracts.manage_device_acceptance",
        ]

        permissions = []
        for perm_code in perms_to_add:
            try:
                app_label, codename = perm_code.split(".")
                perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                permissions.append(perm)
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Право "{perm_code}" не найдено'))

        if permissions:
            before = group.permissions.count()
            group.permissions.add(*permissions)
            added = group.permissions.count() - before
            if added:
                self.stdout.write(self.style.SUCCESS(f'Добавлено {added} прав(а) в группу "Наблюдатель"'))

        # Показываем информацию о группе
        permissions_count = group.permissions.count()
        self.stdout.write(self.style.SUCCESS(f'Группа "Наблюдатель" настроена. Прав: {permissions_count}'))
