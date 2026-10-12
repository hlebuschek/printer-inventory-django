"""
Проверяет позиции договора, у которых модель имеет сетевой порт, но устройство
не опрашивается в нашей системе. По каждому серийнику ходит в GLPI и смотрит
вкладку «Подключение» (Computer_Item): подключён ли принтер по USB к компьютеру.

Результат:
  - USB         — подключён к ПК в GLPI (объяснимо, почему не в сети)
  - NO_USB      — сетевой порт есть, USB-подключения нет → смотреть подробнее
  - NOT_FOUND   — не найден в GLPI
  - MULTIPLE    — найдено несколько принтеров по серийнику
  - ERROR       — ошибка проверки

Примеры:
  python manage.py check_network_usb_glpi
  python manage.py check_network_usb_glpi --limit 20 --delay 0.5
  python manage.py check_network_usb_glpi --csv /tmp/no_usb.csv
  python manage.py check_network_usb_glpi --serial ABC123 XYZ456
"""

import csv
import time

from django.core.management.base import BaseCommand, CommandError

from contracts.models import ContractDevice
from integrations.glpi.client import GLPIAPIError, GLPIClient
from inventory.models import Printer


class Command(BaseCommand):
    help = (
        "Находит позиции с сетевым портом без опроса в нашей системе и проверяет в GLPI, "
        "подключены ли они по USB (вкладка Подключение)"
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Ограничить количество проверяемых устройств")
        parser.add_argument("--delay", type=float, default=0.2, help="Задержка между запросами к GLPI (сек)")
        parser.add_argument("--csv", type=str, help="Сохранить результаты в CSV-файл")
        parser.add_argument("--serial", nargs="+", type=str, help="Проверить только указанные серийники")

    def handle(self, *args, **options):
        candidates = self._collect_candidates()
        if not candidates:
            self.stdout.write(self.style.WARNING("Нет кандидатов: все позиции с сетевым портом на опросе"))
            return

        if options["serial"]:
            wanted = {s.strip().lower() for s in options["serial"]}
            candidates = [c for c in candidates if c["serial"].lower() in wanted]
            if not candidates:
                raise CommandError("Указанные серийники не найдены среди кандидатов")

        if options["limit"]:
            candidates = candidates[: options["limit"]]

        total = len(candidates)
        self.stdout.write(f"Позиций с сетевым портом без опроса: {total}")
        self.stdout.write("=" * 70)

        stats = {"usb": 0, "no_usb": 0, "not_found": 0, "multiple": 0, "errors": 0}
        results = []
        start_time = time.time()

        try:
            with GLPIClient() as client:
                for idx, cand in enumerate(candidates, 1):
                    serial = cand["serial"]
                    row = dict(cand)
                    try:
                        self._check_in_glpi(client, serial, row)
                    except Exception as e:
                        row["result"] = "ERROR"
                        row["detail"] = str(e)

                    results.append(row)
                    self._print_row(idx, total, row, stats)

                    if idx % 50 == 0 and idx < total:
                        elapsed = time.time() - start_time
                        eta_min = (total - idx) * (elapsed / idx) / 60
                        self.stdout.write(
                            self.style.NOTICE(
                                f"--- прогресс: {idx}/{total} ({idx * 100 // total}%), "
                                f"прошло {elapsed / 60:.1f} мин, осталось ~{eta_min:.0f} мин ---"
                            )
                        )

                    if idx < total:
                        time.sleep(options["delay"])
        except GLPIAPIError as e:
            raise CommandError(f"Ошибка подключения к GLPI: {e}")

        self._print_summary(stats, results)

        if options["csv"] and results:
            self._write_csv(options["csv"], results)
            self.stdout.write(self.style.SUCCESS(f"CSV сохранён: {options['csv']}"))

    def _collect_candidates(self):
        """Активные позиции: модель с сетевым портом, не опрашиваются (нет принтера или он неактивен)."""
        inv_serials = {
            (s or "").strip().lower()
            for s in Printer.objects.filter(is_active=True)
            .exclude(serial_number=None)
            .exclude(serial_number="")
            .values_list("serial_number", flat=True)
        }

        qs = (
            ContractDevice.objects.filter(
                model__has_network_port=True,
                model__device_type="printer",
                status__is_active=True,
            )
            .exclude(serial_number="")
            .select_related("organization", "city", "model__manufacturer", "printer")
            .order_by("organization__name", "serial_number")
        )

        candidates = []
        for device in qs:
            if device.printer_id and device.printer.is_active:
                continue
            serial = device.serial_number.strip()
            if serial.lower() in inv_serials:
                continue
            candidates.append(
                {
                    "organization": device.organization.name,
                    "city": device.city.name,
                    "address": device.address,
                    "model": str(device.model),
                    "serial": serial,
                    "result": "",
                    "detail": "",
                    "glpi_printer_id": "",
                    "glpi_ip": "",
                    "usb_computers": "",
                }
            )
        return candidates

    def _check_in_glpi(self, client, serial, row):
        status, items, error = client.search_printer_by_serial(serial)

        if status == "NOT_FOUND":
            row["result"] = "NOT_FOUND"
            return
        if status == "ERROR":
            row["result"] = "ERROR"
            row["detail"] = error or "неизвестная ошибка"
            return
        if status == "FOUND_MULTIPLE":
            row["result"] = "MULTIPLE"
            row["detail"] = f"найдено {len(items)} принтеров"
            return

        item = items[0]
        printer_id = item.get("2") or item.get("id")
        if not printer_id:
            row["result"] = "ERROR"
            row["detail"] = "не удалось определить ID принтера в GLPI"
            return

        row["glpi_printer_id"] = int(printer_id)
        computers = client.get_printer_connected_computers(int(printer_id))
        row["glpi_ip"] = client.get_printer_ip(int(printer_id)) or ""

        if computers:
            row["result"] = "USB"
            row["usb_computers"] = "; ".join(
                f"{c['name']}" + (f" ({c['ip']})" if c["ip"] else "") for c in computers
            )
        else:
            row["result"] = "NO_USB"

    def _print_row(self, idx, total, row, stats):
        serial = row["serial"]
        result = row["result"]
        if result == "USB":
            stats["usb"] += 1
            self.stdout.write(f"[{idx}/{total}] {serial:20} | ⊘ USB → {row['usb_computers']}")
        elif result == "NO_USB":
            stats["no_usb"] += 1
            ip_note = f" | IP в GLPI: {row['glpi_ip']}" if row["glpi_ip"] else " | IP в GLPI нет"
            self.stdout.write(
                f"[{idx}/{total}] {serial:20} | {self.style.SUCCESS('✓ сетевой порт, USB нет — проверить')}{ip_note}"
            )
        elif result == "NOT_FOUND":
            stats["not_found"] += 1
            self.stdout.write(f"[{idx}/{total}] {serial:20} | ✗ Не найден в GLPI")
        elif result == "MULTIPLE":
            stats["multiple"] += 1
            self.stdout.write(f"[{idx}/{total}] {serial:20} | ? {row['detail']}")
        else:
            stats["errors"] += 1
            error_msg = self.style.ERROR(f"✗ Ошибка: {row['detail']}")
            self.stdout.write(f"[{idx}/{total}] {serial:20} | {error_msg}")

    def _print_summary(self, stats, results):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("ИТОГИ")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ Сетевой порт, USB нет (проверить): {stats['no_usb']}"))
        self.stdout.write(f"⊘ Подключены по USB:                 {stats['usb']}")
        self.stdout.write(f"✗ Не найдено в GLPI:                 {stats['not_found']}")
        self.stdout.write(f"? Несколько в GLPI:                  {stats['multiple']}")
        if stats["errors"]:
            self.stdout.write(self.style.ERROR(f"✗ Ошибок:                            {stats['errors']}"))

        suspects = [r for r in results if r["result"] == "NO_USB"]
        if not suspects:
            return

        self.stdout.write("\nПозиции для детальной проверки (сетевой порт есть, USB-подключения в GLPI нет):")
        header = f"{'Организация':30} | {'Серийник':18} | {'IP в GLPI':15} | Модель"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for r in suspects:
            self.stdout.write(
                f"{r['organization'][:30]:30} | {r['serial']:18} | {r['glpi_ip']:15} | {r['model']}"
            )

    def _write_csv(self, path, results):
        fieldnames = [
            "organization",
            "city",
            "address",
            "model",
            "serial",
            "result",
            "glpi_printer_id",
            "glpi_ip",
            "usb_computers",
            "detail",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(results)
