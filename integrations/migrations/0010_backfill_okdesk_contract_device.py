"""
Бэкфилл связей OkdeskIssue → ContractDevice.

Правила:
- Заявка без серийников → одна строка, contract_device=NULL (как было).
- Серийники есть, но ни один не найден в ContractDevice → одна строка, contract_device=NULL.
- Часть серийников нашлась → по строке на каждое найденное устройство.
  serial_numbers у строки оставляем равным её одному серийнику.
- Все серийники нашлись → N строк по числу устройств.
"""

import re

from django.db import migrations
from django.db.models import Count, Min


def _normalize(value):
    if not value:
        return ""
    return re.sub(r"[-_\s]", "", value).upper()


def link_to_contract_devices(apps, schema_editor):
    OkdeskIssue = apps.get_model("integrations", "OkdeskIssue")
    ContractDevice = apps.get_model("contracts", "ContractDevice")

    # serial (normalized) -> (device_id, original_trimmed_serial)
    serial_to_device = {}
    for dev_id, sn in (
        ContractDevice.objects.exclude(serial_number="").values_list("id", "serial_number").iterator()
    ):
        key = _normalize(sn)
        if not key:
            continue
        # ContractDevice.serial_number имеет partial unique по Lower(serial_number),
        # так что коллизий быть не должно; но на всякий случай — first-wins.
        serial_to_device.setdefault(key, (dev_id, sn.strip()))

    matched_rows = 0
    cloned_rows = 0
    orphan_rows = 0

    for issue in OkdeskIssue.objects.all().iterator():
        raw = (issue.serial_numbers or "").strip()
        if not raw:
            orphan_rows += 1
            continue

        serials = [s.strip() for s in raw.split(",") if s.strip()]
        seen_devs = set()
        matches = []
        for s in serials:
            hit = serial_to_device.get(_normalize(s))
            if hit and hit[0] not in seen_devs:
                seen_devs.add(hit[0])
                matches.append(hit)

        if not matches:
            # NULL-сирота, serial_numbers оставляем как есть
            orphan_rows += 1
            continue

        first_dev_id, first_serial = matches[0]
        OkdeskIssue.objects.filter(pk=issue.pk).update(
            contract_device_id=first_dev_id,
            serial_numbers=first_serial,
        )
        matched_rows += 1

        for dev_id, serial in matches[1:]:
            OkdeskIssue.objects.create(
                issue_id=issue.issue_id,
                title=issue.title,
                contract_device_id=dev_id,
                created_at=issue.created_at,
                completed_at=issue.completed_at,
                status_name=issue.status_name,
                priority_name=issue.priority_name,
                author_name=issue.author_name,
                assignee_name=issue.assignee_name,
                company_name=issue.company_name,
                serial_numbers=serial,
                deadline_at=issue.deadline_at,
                is_overdue=issue.is_overdue,
                source=issue.source,
                synced_at=issue.synced_at,
                created_by_id=issue.created_by_id,
            )
            cloned_rows += 1

    print(
        f"  OkdeskIssue backfill: matched={matched_rows}, cloned={cloned_rows}, orphan={orphan_rows}"
    )


def reverse_collapse(apps, schema_editor):
    """Откат: схлопываем дубликаты, чтобы issue_id снова стал уникальным."""
    OkdeskIssue = apps.get_model("integrations", "OkdeskIssue")
    duplicates = (
        OkdeskIssue.objects.values("issue_id")
        .annotate(c=Count("id"), keep=Min("id"))
        .filter(c__gt=1)
    )
    for d in duplicates:
        OkdeskIssue.objects.filter(issue_id=d["issue_id"]).exclude(pk=d["keep"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0009_link_okdeskissue_to_contract_device"),
        ("contracts", "0005_devicemodel_has_network_port"),
    ]

    operations = [
        migrations.RunPython(link_to_contract_devices, reverse_collapse),
    ]
