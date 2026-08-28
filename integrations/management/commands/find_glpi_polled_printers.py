"""
Ищет принтеры, которые не заполняются автосинхронизацией из inventory,
но при этом автоматически инвентаризируются в GLPI (есть свежий PrinterLog).
Результат — список IP-адресов, которые можно добавить на опрос в нашу систему.

Примеры использования:
  python manage.py find_glpi_polled_printers                    # последний закрытый месяц
  python manage.py find_glpi_polled_printers --month 2026-08
  python manage.py find_glpi_polled_printers --month 2026-08 --csv /tmp/candidates.csv
  python manage.py find_glpi_polled_printers --limit 20 --delay 0.5
"""

import csv
import time
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from integrations.glpi.client import GLPIAPIError, GLPIClient
from integrations.glpi.monthly_report_export import get_latest_closed_month
from integrations.glpi.services import probe_serial_in_glpi
from inventory.models import Printer
from monthly_report.models import MonthlyReport


class Command(BaseCommand):
    help = (
        "Находит устройства из monthly_report без автосинхронизации (device_ip пуст), "
        "которые GLPI опрашивает сам (PrinterLog за месяц или позже), и выводит их IP"
    )

    def add_arguments(self, parser):
        parser.add_argument("--month", type=str, help="Месяц в формате YYYY-MM (по умолчанию последний закрытый)")
        parser.add_argument("--limit", type=int, help="Ограничить количество проверяемых устройств")
        parser.add_argument("--delay", type=float, default=0.2, help="Задержка между запросами к GLPI (сек)")
        parser.add_argument("--csv", type=str, help="Сохранить найденных кандидатов в CSV-файл")
        parser.add_argument("--serial", nargs="+", type=str, help="Проверить только указанные серийники")

    def handle(self, *args, **options):
        month = self._resolve_month(options["month"])
        self.stdout.write(f"Месяц: {month.strftime('%Y-%m')}")

        candidates = self._collect_candidates(month)
        if not candidates:
            self.stdout.write(self.style.WARNING("Нет устройств для проверки: все строки месяца на опросе"))
            return

        if options["serial"]:
            wanted = set(options["serial"])
            candidates = [c for c in candidates if c["serial"] in wanted]
            if not candidates:
                raise CommandError("Указанные серийники не найдены среди кандидатов (или уже на опросе)")

        if options["limit"]:
            candidates = candidates[: options["limit"]]

        inventory_serials = set(
            Printer.objects.filter(serial_number__in=[c["serial"] for c in candidates]).values_list(
                "serial_number", flat=True
            )
        )

        total = len(candidates)
        self.stdout.write(f"Устройств без автосинхронизации (device_ip пуст): {total}")
        self.stdout.write("=" * 70)

        # Свежесть: GLPI инвентаризировал устройство в проверяемом месяце или позже
        freshness_cutoff = timezone.make_aware(datetime(month.year, month.month, 1))

        stats = {"active": 0, "stale": 0, "not_found": 0, "errors": 0}
        found = []
        start_time = time.time()

        try:
            with GLPIClient() as client:
                for idx, cand in enumerate(candidates, 1):
                    serial = cand["serial"]
                    try:
                        probe = probe_serial_in_glpi(client, serial, freshness_cutoff)
                    except Exception as e:
                        stats["errors"] += 1
                        self.stdout.write(f"[{idx}/{total}] {serial:20} | {self.style.ERROR(f'✗ Ошибка: {e}')}")
                        continue

                    if probe["status"] == "GLPI_ACTIVE":
                        stats["active"] += 1
                        ip = client.get_printer_ip(probe["glpi_printer_id"])
                        glpi_date = probe["glpi_date"].strftime("%Y-%m-%d") if probe["glpi_date"] else "?"
                        found.append(
                            {
                                "organization": cand["organization"],
                                "serial_number": serial,
                                "equipment_model": cand["equipment_model"],
                                "glpi_name": probe["glpi_name"],
                                "glpi_ip": ip or "",
                                "glpi_counter": probe["glpi_counter"],
                                "glpi_date": glpi_date,
                                "glpi_state": probe["glpi_state"],
                                "in_inventory": serial in inventory_serials,
                            }
                        )
                        msg = f"✓ GLPI опрашивает | IP: {ip or 'не найден'} | счётчик: {probe['glpi_counter']} ({glpi_date})"
                        if serial in inventory_serials:
                            msg += " | уже есть в inventory!"
                        self.stdout.write(f"[{idx}/{total}] {serial:20} | {self.style.SUCCESS(msg)}")
                    elif probe["status"] == "GLPI_STALE":
                        stats["stale"] += 1
                        glpi_date = probe["glpi_date"].strftime("%Y-%m-%d") if probe["glpi_date"] else "нет PrinterLog"
                        self.stdout.write(f"[{idx}/{total}] {serial:20} | ⊘ Найден, но не опрашивается ({glpi_date})")
                    elif probe["status"] == "NOT_FOUND":
                        stats["not_found"] += 1
                        self.stdout.write(f"[{idx}/{total}] {serial:20} | ✗ Не найден в GLPI")
                    else:
                        stats["errors"] += 1
                        error_msg = self.style.ERROR(f"✗ Ошибка: {probe.get('error') or 'неизвестная'}")
                        self.stdout.write(f"[{idx}/{total}] {serial:20} | {error_msg}")

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

        self._print_summary(stats, found)

        if options["csv"] and found:
            self._write_csv(options["csv"], found)
            self.stdout.write(self.style.SUCCESS(f"CSV сохранён: {options['csv']}"))

    def _resolve_month(self, month_str):
        if month_str:
            try:
                parsed = datetime.strptime(month_str, "%Y-%m")
            except ValueError:
                raise CommandError("Неверный формат месяца, ожидается YYYY-MM (например 2026-08)")
            return date(parsed.year, parsed.month, 1)

        latest = get_latest_closed_month()
        if not latest:
            raise CommandError("Нет закрытых месяцев, укажите месяц явно: --month YYYY-MM")
        return date(latest.year, latest.month, 1)

    def _collect_candidates(self, month):
        """Группирует строки месяца по серийнику, оставляет устройства без единой строки на опросе."""
        rows = MonthlyReport.objects.filter(month=month).values(
            "serial_number", "organization", "equipment_model", "device_ip"
        )
        if not rows:
            raise CommandError(f"В monthly_report нет данных за {month.strftime('%Y-%m')}")

        grouped = {}
        for row in rows:
            serial = (row["serial_number"] or "").strip()
            if not serial:
                continue
            entry = grouped.setdefault(
                serial,
                {
                    "serial": serial,
                    "organization": row["organization"],
                    "equipment_model": row["equipment_model"],
                    "on_polling": False,
                },
            )
            if row["device_ip"]:
                entry["on_polling"] = True

        return sorted(
            (c for c in grouped.values() if not c["on_polling"]),
            key=lambda c: (c["organization"], c["serial"]),
        )

    def _print_summary(self, stats, found):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("ИТОГИ")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ GLPI опрашивает сам:      {stats['active']}"))
        self.stdout.write(f"⊘ В GLPI, но без опроса:    {stats['stale']}")
        self.stdout.write(f"✗ Не найдено в GLPI:        {stats['not_found']}")
        if stats["errors"]:
            self.stdout.write(self.style.ERROR(f"✗ Ошибок:                   {stats['errors']}"))

        if not found:
            return

        self.stdout.write("\nКандидаты на добавление в опрос:")
        header = f"{'Организация':30} | {'Серийник':18} | {'IP':15} | {'Счётчик':>8} | {'Дата GLPI':10} | Модель"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for f in found:
            note = " (уже в inventory)" if f["in_inventory"] else ""
            self.stdout.write(
                f"{f['organization'][:30]:30} | {f['serial_number']:18} | {f['glpi_ip']:15} | "
                f"{f['glpi_counter'] or 0:>8} | {f['glpi_date']:10} | {f['equipment_model']}{note}"
            )

    def _write_csv(self, path, found):
        fieldnames = [
            "organization",
            "serial_number",
            "equipment_model",
            "glpi_name",
            "glpi_ip",
            "glpi_counter",
            "glpi_date",
            "glpi_state",
            "in_inventory",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(found)
