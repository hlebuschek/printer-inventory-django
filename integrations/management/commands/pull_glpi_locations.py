"""
Management команда для быстрого подтягивания адресов (локаций) из GLPI.

Использует сохранённые ранее GLPI ID (из GLPISync), поэтому не ищет устройства
по серийнику заново — только читает локацию карточки. Названия локаций кэшируются,
так что на N устройств уходит ~N запросов + по одному на уникальную локацию.

Примеры использования:
  python manage.py pull_glpi_locations                # Все устройства с известным GLPI ID
  python manage.py pull_glpi_locations --limit 10
  python manage.py pull_glpi_locations --device-ids 1 2 3
  python manage.py pull_glpi_locations --dry-run      # Показать изменения без сохранения
"""

import time

from django.core.management.base import BaseCommand

from contracts.models import ContractDevice
from integrations.glpi.client import GLPIClient
from integrations.models import GLPISync


class Command(BaseCommand):
    help = "Подтягивает адреса (локации) устройств из GLPI по сохранённым GLPI ID"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Ограничить количество устройств")
        parser.add_argument("--device-ids", nargs="+", type=int, help="ID конкретных устройств")
        parser.add_argument(
            "--delay", type=float, default=0.3, help="Задержка между запросами в секундах (по умолчанию 0.3)"
        )
        parser.add_argument("--dry-run", action="store_true", help="Не сохранять изменения, только показать")

    def handle(self, *args, **options):
        latest_syncs = (
            GLPISync.objects.filter(status="FOUND_SINGLE")
            .order_by("contract_device_id", "-checked_at")
            .distinct("contract_device_id")
        )
        if options["device_ids"]:
            latest_syncs = latest_syncs.filter(contract_device_id__in=options["device_ids"])

        device_to_glpi_id = {s.contract_device_id: s.glpi_ids[0] for s in latest_syncs if s.glpi_ids}

        devices = ContractDevice.objects.filter(id__in=device_to_glpi_id).select_related("city")
        if options["limit"]:
            devices = devices[: options["limit"]]

        devices = list(devices)
        total = len(devices)
        self.stdout.write(f"Устройств с известным GLPI ID: {total}")
        if not total:
            self.stdout.write(self.style.WARNING("Нечего обновлять. Сначала запустите sync_glpi / проверку в GLPI."))
            return

        location_cache = {}  # locations_id -> completename
        stats = {"updated": 0, "unchanged": 0, "no_location": 0, "errors": 0}

        with GLPIClient() as client:
            for idx, device in enumerate(devices, 1):
                glpi_id = device_to_glpi_id[device.id]
                try:
                    printer = client.get_printer(glpi_id)
                    if printer is None:
                        stats["errors"] += 1
                        self.stdout.write(self.style.ERROR(f"[{idx}/{total}] {device} — карточка {glpi_id} не найдена"))
                        continue

                    location_id = printer.get("locations_id")
                    location_name = ""
                    if location_id:
                        if location_id not in location_cache:
                            location_cache[location_id] = client.get_location_name(location_id) or ""
                        location_name = location_cache[location_id]

                    if not location_name:
                        stats["no_location"] += 1

                    new_value = location_name[:500]
                    if device.glpi_location != new_value:
                        prefix = "[dry-run] " if options["dry_run"] else ""
                        self.stdout.write(
                            f"{prefix}[{idx}/{total}] {device.serial_number or device.id}: "
                            f"'{device.glpi_location}' -> '{new_value}'"
                        )
                        if not options["dry_run"]:
                            device.glpi_location = new_value
                            device.save(update_fields=["glpi_location", "updated_at"])
                        stats["updated"] += 1
                    else:
                        stats["unchanged"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    self.stdout.write(self.style.ERROR(f"[{idx}/{total}] {device} — ошибка: {e}"))

                if options["delay"] and idx < total:
                    time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: обновлено {stats['updated']}, без изменений {stats['unchanged']}, "
                f"без локации в GLPI {stats['no_location']}, ошибок {stats['errors']}"
            )
        )
