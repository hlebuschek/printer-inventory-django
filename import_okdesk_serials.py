"""
Импорт серийников Okdesk-заявок из CSV на прод.

Безопасная логика — обновляет ТОЛЬКО:
  - заявки, которые УЖЕ существуют на проде (по issue_id)
  - и где serial_numbers сейчас пустой (по умолчанию)

Использование:
    python import_okdesk_serials.py okdesk_serials.csv             # dry-run по умолчанию
    python import_okdesk_serials.py okdesk_serials.csv --apply     # реально записать
    python import_okdesk_serials.py okdesk_serials.csv --apply --force
                                    # перезаписать даже если на проде уже есть serial_numbers
"""

import csv
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "printer_inventory.settings")
import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from integrations.models import OkdeskIssue  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_okdesk_serials.py <csv_path> [--apply] [--force]")
        sys.exit(1)

    csv_path = sys.argv[1]
    apply_changes = "--apply" in sys.argv
    force = "--force" in sys.argv

    if not os.path.exists(csv_path):
        print(f"Файл не найден: {csv_path}")
        sys.exit(1)

    # Читаем CSV в словарь {issue_id: serial_numbers}
    incoming = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                incoming[int(row["issue_id"])] = (row["serial_numbers"] or "").strip()
            except (ValueError, KeyError):
                continue

    print(f"Из CSV прочитано записей: {len(incoming)}")
    print(f"Режим: {'APPLY' if apply_changes else 'DRY-RUN'} | force={force}")

    # На проде существуют эти issue_id?
    prod_qs = OkdeskIssue.objects.filter(issue_id__in=incoming.keys()).only("issue_id", "serial_numbers")
    prod_map = {i.issue_id: i for i in prod_qs}

    print(f"Найдено на проде: {len(prod_map)}")
    print(f"Отсутствуют на проде (будут пропущены): {len(incoming) - len(prod_map)}")

    will_update = []
    skip_already_filled = 0
    skip_same_value = 0

    for issue_id, new_sn in incoming.items():
        if not new_sn:
            continue
        prod = prod_map.get(issue_id)
        if not prod:
            continue
        current = (prod.serial_numbers or "").strip()
        if current and not force:
            skip_already_filled += 1
            continue
        if current == new_sn:
            skip_same_value += 1
            continue
        will_update.append((issue_id, current, new_sn))

    print()
    print(f"К обновлению:                       {len(will_update)}")
    print(f"Пропущено (уже заполнены, не force): {skip_already_filled}")
    print(f"Пропущено (значение уже совпадает): {skip_same_value}")

    # Покажем первые 10 для проверки
    if will_update:
        print("\nПримеры (первые 10):")
        for issue_id, old, new in will_update[:10]:
            print(f"  #{issue_id}: {old!r} -> {new!r}")

    if not apply_changes:
        print("\nDRY-RUN — изменения не записаны. Запусти с --apply для применения.")
        return

    if not will_update:
        print("\nНечего обновлять.")
        return

    print("\nПрименяем изменения...")
    updated = 0
    with transaction.atomic():
        for issue_id, _old, new_sn in will_update:
            OkdeskIssue.objects.filter(issue_id=issue_id).update(serial_numbers=new_sn)
            updated += 1

    print(f"Обновлено: {updated}")


if __name__ == "__main__":
    main()
