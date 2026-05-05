"""
Экспорт серийников Okdesk-заявок в CSV (локально).

Выгружает все заявки, у которых serial_numbers заполнен.
Файл потом переносится на прод и применяется через import_okdesk_serials.py.

Использование:
    python export_okdesk_serials.py                 # → okdesk_serials.csv
    python export_okdesk_serials.py /tmp/out.csv    # произвольный путь
"""

import csv
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "printer_inventory.settings")
import django  # noqa: E402

django.setup()

from integrations.models import OkdeskIssue  # noqa: E402


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "okdesk_serials.csv"

    qs = (
        OkdeskIssue.objects.exclude(serial_numbers="")
        .exclude(serial_numbers__isnull=True)
        .order_by("issue_id")
        .values_list("issue_id", "serial_numbers")
    )

    total = qs.count()
    print(f"Заявок с серийниками для экспорта: {total}")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["issue_id", "serial_numbers"])
        for issue_id, serials in qs.iterator():
            writer.writerow([issue_id, serials])

    print(f"Готово: {out_path}")


if __name__ == "__main__":
    main()
