"""
Импорт серийников Okdesk-заявок из CSV на проде.

Используется после миграций 0009/0010, когда на проде у большинства orphan-строк
serial_numbers пустой. CSV генерируется на dev через export_okdesk_serials.py.

Делает за один проход:
  1) обновляет serial_numbers в существующих OkdeskIssue по issue_id;
  2) релинкует orphan-строки на ContractDevice (как enrich_okdesk_serials --from-stored-serials).

Логика обновления (как в standalone-скрипте):
  - заявки, отсутствующие на проде → пропускаются;
  - заявки с уже заполненным serial_numbers → пропускаются (если не --force).

Использование:
    python manage.py import_okdesk_serials okdesk_serials.csv             # dry-run
    python manage.py import_okdesk_serials okdesk_serials.csv --apply
    python manage.py import_okdesk_serials okdesk_serials.csv --apply --force
"""

import csv
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from integrations.models import OkdeskIssue
from integrations.okdesk_enrichment import (
    build_contract_device_map,
    relink_orphan_row,
    resolve_devices,
)


class Command(BaseCommand):
    help = "Импорт serial_numbers из CSV + релинк OkdeskIssue → ContractDevice"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Путь к CSV (issue_id, serial_numbers)")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Реально записать изменения (по умолчанию — dry-run).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Перезаписывать serial_numbers даже если на проде уже заполнен.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        apply_changes = options["apply"]
        force = options["force"]

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"Файл не найден: {csv_path}"))
            return

        incoming = {}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    incoming[int(row["issue_id"])] = (row["serial_numbers"] or "").strip()
                except (ValueError, KeyError):
                    continue

        self.stdout.write(f"Из CSV прочитано записей: {len(incoming)}")
        self.stdout.write(f"Режим: {'APPLY' if apply_changes else 'DRY-RUN'} | force={force}")

        # На проде у одной issue_id может быть несколько строк (orphan + matched после 0010).
        # Для импорта работаем с orphan-строкой (contract_device IS NULL) — её и обновляем.
        prod_orphans = {
            i.issue_id: i
            for i in OkdeskIssue.objects.filter(
                issue_id__in=incoming.keys(),
                contract_device__isnull=True,
            ).only("id", "issue_id", "serial_numbers")
        }

        # Заявки, у которых orphan-строки нет (значит, всё уже разнесено по device-строкам).
        existing_ids = set(
            OkdeskIssue.objects.filter(issue_id__in=incoming.keys()).values_list("issue_id", flat=True).distinct()
        )

        missing_on_prod = len(incoming) - len(existing_ids)
        no_orphan = len(existing_ids) - len(prod_orphans)

        self.stdout.write(f"Найдено на проде (issue_id):       {len(existing_ids)}")
        self.stdout.write(f"Отсутствуют на проде:              {missing_on_prod}")
        self.stdout.write(f"Уже разлинкованы (нет orphan):     {no_orphan}")

        will_update = []
        skip_already_filled = 0
        skip_same_value = 0

        for issue_id, new_sn in incoming.items():
            if not new_sn:
                continue
            orphan = prod_orphans.get(issue_id)
            if not orphan:
                continue
            current = (orphan.serial_numbers or "").strip()
            if current and not force:
                skip_already_filled += 1
                continue
            if current == new_sn:
                skip_same_value += 1
                continue
            will_update.append((orphan, current, new_sn))

        self.stdout.write("")
        self.stdout.write(f"К обновлению serial_numbers:        {len(will_update)}")
        self.stdout.write(f"Пропущено (уже заполнен, не force): {skip_already_filled}")
        self.stdout.write(f"Пропущено (значение совпадает):     {skip_same_value}")

        if will_update:
            self.stdout.write("\nПримеры (первые 5):")
            for orphan, old, new in will_update[:5]:
                self.stdout.write(f"  #{orphan.issue_id}: {old!r} -> {new!r}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("\nDRY-RUN — изменения не записаны. Запусти с --apply."))
            return

        if not will_update:
            self.stdout.write("\nНечего обновлять.")
            return

        # 1) Записываем serial_numbers
        self.stdout.write("\nШаг 1/2: запись serial_numbers...")
        updated_serials = 0
        with transaction.atomic():
            for orphan, _old, new_sn in will_update:
                OkdeskIssue.objects.filter(pk=orphan.pk).update(serial_numbers=new_sn)
                orphan.serial_numbers = new_sn
                updated_serials += 1
        self.stdout.write(f"  Обновлено строк: {updated_serials}")

        # 2) Релинк затронутых orphan-строк на ContractDevice
        self.stdout.write("\nШаг 2/2: релинк на ContractDevice...")
        contract_device_map = build_contract_device_map()
        self.stdout.write(f"  Эталонных серийников из ContractDevice: {len(contract_device_map)}")

        relinked = 0
        cloned = 0
        no_match = 0

        with transaction.atomic():
            for orphan, _old, new_sn in will_update:
                serials_list = [s.strip() for s in new_sn.split(",") if s.strip()]
                matched = resolve_devices(serials_list, contract_device_map)
                if not matched:
                    no_match += 1
                    continue
                cloned += relink_orphan_row(orphan, matched)
                relinked += 1

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("Готово:"))
        self.stdout.write(f"  serial_numbers обновлено:  {updated_serials}")
        self.stdout.write(f"  Привязано к ContractDevice: {relinked}")
        self.stdout.write(f"  Клонов создано:             {cloned}")
        self.stdout.write(f"  Нет в ContractDevice:       {no_match}")
