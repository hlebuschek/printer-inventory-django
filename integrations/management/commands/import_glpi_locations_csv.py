"""
Management команда для быстрого наполнения glpi_location из CSV-экспорта GLPI,
без обхода API (в отличие от pull_glpi_locations).

CSV — экспорт списка принтеров из GLPI: нужны колонки с серийным номером и
местонахождением (completename локации). Разделитель и колонки определяются
автоматически по заголовку, но их можно задать явно.

Примеры использования:
  python manage.py import_glpi_locations_csv printers.csv
  python manage.py import_glpi_locations_csv printers.csv --dry-run
  python manage.py import_glpi_locations_csv printers.csv --serial-column "Серийный номер" --location-column "Местонахождение"
  python manage.py import_glpi_locations_csv printers.csv --encoding cp1251 --delimiter ";"
"""

import csv

from django.core.management.base import BaseCommand, CommandError

from contracts.models import ContractDevice

SERIAL_HEADER_HINTS = ("серийный номер", "серийн", "serial")
LOCATION_HEADER_HINTS = ("местоположен", "местонахожден", "локац", "location")


class Command(BaseCommand):
    help = "Наполняет ContractDevice.glpi_location из CSV-экспорта GLPI (матчинг по серийному номеру)"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Путь к CSV-файлу (экспорт из GLPI)")
        parser.add_argument(
            "--serial-column", help="Название колонки с серийным номером (по умолчанию — автоопределение)"
        )
        parser.add_argument("--location-column", help="Название колонки с локацией (по умолчанию — автоопределение)")
        parser.add_argument("--encoding", default="utf-8-sig", help="Кодировка файла (по умолчанию utf-8-sig)")
        parser.add_argument("--delimiter", help="Разделитель (по умолчанию — автоопределение из ';', ',', табуляции)")
        parser.add_argument(
            "--clear-missing",
            action="store_true",
            help="Очистить glpi_location у устройств, серийника которых нет в CSV",
        )
        parser.add_argument("--dry-run", action="store_true", help="Не сохранять изменения, только показать")

    def handle(self, *args, **options):
        serial_to_location = self._read_csv(options)
        self.stdout.write(f"В CSV серийников с локацией: {len(serial_to_location)}")

        devices = list(ContractDevice.objects.all().only("id", "serial_number", "glpi_location"))
        stats = {"updated": 0, "unchanged": 0, "not_in_csv": 0, "cleared": 0}
        to_save = []

        for device in devices:
            serial = (device.serial_number or "").strip().upper()
            if not serial or serial not in serial_to_location:
                stats["not_in_csv"] += 1
                if options["clear_missing"] and device.glpi_location:
                    self._log_change(device, "", options["dry_run"])
                    device.glpi_location = ""
                    to_save.append(device)
                    stats["cleared"] += 1
                continue

            new_value = serial_to_location[serial][:500]
            if device.glpi_location == new_value:
                stats["unchanged"] += 1
                continue

            self._log_change(device, new_value, options["dry_run"])
            device.glpi_location = new_value
            to_save.append(device)
            stats["updated"] += 1

        if to_save and not options["dry_run"]:
            ContractDevice.objects.bulk_update(to_save, ["glpi_location"], batch_size=500)

        matched_serials = {(d.serial_number or "").strip().upper() for d in devices}
        csv_only = sum(1 for s in serial_to_location if s not in matched_serials)

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово{' (dry-run)' if options['dry_run'] else ''}: обновлено {stats['updated']}, "
                f"без изменений {stats['unchanged']}, устройств без серийника в CSV {stats['not_in_csv']}, "
                f"очищено {stats['cleared']}, серийников из CSV без устройства {csv_only}"
            )
        )

    def _read_csv(self, options):
        try:
            # errors="replace": GLPI иногда обрезает мультибайтовый символ в конце поля
            with open(options["csv_path"], newline="", encoding=options["encoding"], errors="replace") as f:
                sample = f.read(8192)
                f.seek(0)
                delimiter = options["delimiter"]
                if not delimiter:
                    try:
                        delimiter = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
                    except csv.Error:
                        delimiter = ";"
                reader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    raise CommandError("CSV пустой или без заголовка")

                serial_col = options["serial_column"] or self._find_column(reader.fieldnames, SERIAL_HEADER_HINTS)
                location_col = options["location_column"] or self._find_column(reader.fieldnames, LOCATION_HEADER_HINTS)
                if not serial_col or serial_col not in reader.fieldnames:
                    raise CommandError(
                        f"Не найдена колонка с серийным номером. Заголовки CSV: {reader.fieldnames}. "
                        f"Укажите её через --serial-column"
                    )
                if not location_col or location_col not in reader.fieldnames:
                    raise CommandError(
                        f"Не найдена колонка с локацией. Заголовки CSV: {reader.fieldnames}. "
                        f"Укажите её через --location-column"
                    )
                self.stdout.write(
                    f"Колонки: серийник='{serial_col}', локация='{location_col}', разделитель='{delimiter}'"
                )

                mapping = {}
                for row in reader:
                    serial = (row.get(serial_col) or "").strip().upper()
                    location = (row.get(location_col) or "").strip()
                    if serial and location:
                        mapping[serial] = location
                return mapping
        except FileNotFoundError:
            raise CommandError(f"Файл не найден: {options['csv_path']}")
        except UnicodeDecodeError as e:
            raise CommandError(
                f"Не удалось прочитать файл в кодировке {options['encoding']}: {e}. Попробуйте --encoding cp1251"
            )

    @staticmethod
    def _find_column(fieldnames, hints):
        # Сначала точное совпадение, потом подстрока — чтобы "Серийный номер" выигрывал
        # у "Плагины - Custom - Серийный номер на бирке"
        for hint in hints:
            for name in fieldnames:
                if name.strip().lower() == hint:
                    return name
        for hint in hints:
            for name in fieldnames:
                if hint in name.lower():
                    return name
        return None

    def _log_change(self, device, new_value, dry_run):
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}{device.serial_number or device.id}: '{device.glpi_location}' -> '{new_value}'")
