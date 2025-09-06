# monthly_report/services.py
from __future__ import annotations

from typing import Optional, Iterable
from django.db import transaction, models
from .models import MonthlyReport


def _nz(x) -> int:
    """Безопасно привести к int, пустые/None -> 0."""
    try:
        return int(x or 0)
    except Exception:
        return 0


def _pair(obj: MonthlyReport, start_name: str, end_name: str) -> int:
    """max(0, end - start) c безопасным доступом к полям."""
    start = _nz(getattr(obj, start_name, 0))
    end = _nz(getattr(obj, end_name, 0))
    return max(0, end - start)


def _a4(obj: MonthlyReport) -> int:
    # Если каких-то полей нет в модели — getattr вернёт 0.
    return _pair(obj, "a4_bw_start", "a4_bw_end") + _pair(obj, "a4_color_start", "a4_color_end")


def _a3(obj: MonthlyReport) -> int:
    # Некоторые схемы держат только A3 BW — это учитываем.
    return _pair(obj, "a3_bw_start", "a3_bw_end") + _pair(obj, "a3_color_start", "a3_color_end")


@transaction.atomic
def recompute_group(month, serial: Optional[str], inventory: Optional[str]) -> None:
    """
    Пересчитать total_prints в группе за указанный месяц.
    Правило группировки: если задан serial -> по serial (case-insensitive),
    иначе — по inventory (case-insensitive). Пустые ключи не группируются.

    Раскладка:
      - если в группе 1 запись: A4 + A3;
      - если >1: первая — только A4, остальные — только A3.
    """
    sn = (serial or "").strip()
    inv = (inventory or "").strip()
    if not sn and not inv:
        return

    qs = MonthlyReport.objects.select_for_update().filter(month=month)
    qs = qs.filter(serial_number__iexact=sn) if sn else qs.filter(inventory_number__iexact=inv)

    rows = list(qs.order_by("order_number", "id"))
    if not rows:
        return

    if len(rows) == 1:
        rows[0].total_prints = _a4(rows[0]) + _a3(rows[0])
    else:
        rows[0].total_prints = _a4(rows[0])
        for r in rows[1:]:
            r.total_prints = _a3(r)

    MonthlyReport.objects.bulk_update(rows, ["total_prints"])


def recompute_month(month) -> None:
    """
    Массовый пересчёт месяца — удобно вызывать после импорта Excel.
    Сначала считаем все группы по SN (непустые), затем — группы по инвентарным
    номером там, где SN отсутствует.
    """
    # Все непустые серийники
    serials = (
        MonthlyReport.objects.filter(month=month)
        .exclude(serial_number__isnull=True)
        .exclude(serial_number__exact="")
        .values_list("serial_number", flat=True)
        .distinct()
    )
    for sn in serials:
        recompute_group(month, sn, None)

    # Инвентарные только у тех строк, где нет SN
    inventories = (
        MonthlyReport.objects.filter(month=month)
        .filter(models.Q(serial_number__isnull=True) | models.Q(serial_number__exact=""))
        .exclude(inventory_number__isnull=True)
        .exclude(inventory_number__exact="")
        .values_list("inventory_number", flat=True)
        .distinct()
    )
    for inv in inventories:
        recompute_group(month, None, inv)
