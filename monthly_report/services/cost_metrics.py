"""Стоимость услуги за месяц по п.7.5.2 ТЗ: F = B×K1×K2.

B — базовая стоимость: отпечатки строки отчёта по типам (A4/A3, ч/б/цвет),
умноженные на цены типа из договора устройства. F — фактическая: при выполнении
целевых показателей (K1 ≥ 98%, K2 ≥ 85%, Таблица №3 ТЗ) равна B, иначе B×K1×K2
с коэффициентами в долях. Буквальное толкование фразы «в случае соблюдения целевых
показателей фактическая стоимость равна базовой» бизнесом не подтверждено —
спорные строки в выгрузке помечены примечанием.

Строки без договора остаются без стоимости: придумывать цену хуже, чем показать
дыру в данных. Строки без K1/K2 (SLA не ведётся) оплачиваются полностью —
зафиксированных нарушений нет, обнулять оплату из-за отсутствия графика нельзя.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models.functions import Trim, Upper

from contracts.models import ContractDevice

from .sla_metrics import month_metrics_applied

# Целевые значения показателей качества — Таблица №3 ТЗ
K1_TARGET = 98.0
K2_TARGET = 85.0

KOPECK = Decimal("0.01")

A4_FIELDS = (
    ("a4_bw_start", "a4_bw_end", "price_a4_bw"),
    ("a4_color_start", "a4_color_end", "price_a4_color"),
)
A3_FIELDS = (
    ("a3_bw_start", "a3_bw_end", "price_a3_bw"),
    ("a3_color_start", "a3_color_end", "price_a3_color"),
)


def _normalized(serial):
    return (serial or "").strip().upper()


def _fields_for_row(report, group):
    """Дубли строк по серийнику делят форматы так же, как recompute_group:
    первая строка считается по A4, остальные — по A3. Иначе отпечатки
    задвоились бы и в количестве, и в деньгах."""
    if len(group) == 1:
        return A4_FIELDS + A3_FIELDS
    return A4_FIELDS if report is group[0] else A3_FIELDS


def _row_cost(report, contract, fields):
    pages, base = 0, Decimal("0")
    for start_name, end_name, price_name in fields:
        count = int(getattr(report, end_name) or 0) - int(getattr(report, start_name) or 0)
        pages += count
        base += Decimal(count) * getattr(contract, price_name)
    return pages, base.quantize(KOPECK, rounding=ROUND_HALF_UP)


def _actual_cost(base, k1, k2):
    """Возвращает (F, примечание)."""
    if k1 is None or k2 is None:
        return base, "SLA не ведётся — оплата полная"
    if k1 >= K1_TARGET and k2 >= K2_TARGET:
        return base, "целевые показатели соблюдены"
    actual = base * Decimal(str(k1)) * Decimal(str(k2)) / Decimal(10000)
    return actual.quantize(KOPECK, rounding=ROUND_HALF_UP), "ниже целевых показателей"


def month_cost_rows(month_dt: date):
    """Строки акта сдачи-приёмки (Прил. 3 ТЗ) и итоги за месяц.

    K1/K2 пересчитываются на лету через month_metrics_applied — файл идёт
    на сверку с актом подрядчика, БД не изменяется.
    """
    reports, _, _ = month_metrics_applied(month_dt)
    reports.sort(key=lambda r: (r.order_number, r.id))

    serials = {_normalized(r.serial_number) for r in reports if _normalized(r.serial_number)}
    devices = (
        ContractDevice.objects.select_related("contract")
        .annotate(normalized_serial=Upper(Trim("serial_number")))
        .filter(normalized_serial__in=serials)
    )
    device_by_serial = {device.normalized_serial: device for device in devices}

    groups = defaultdict(list)
    for report in reports:
        if _normalized(report.serial_number):
            groups[_normalized(report.serial_number)].append(report)

    rows = []
    totals = {"pages": 0, "base": Decimal("0"), "actual": Decimal("0"), "vat": Decimal("0"), "with_vat": Decimal("0")}
    for report in reports:
        serial = _normalized(report.serial_number)
        device = device_by_serial.get(serial)
        contract = device.contract if device else None
        row = {
            "report": report,
            "contract": contract,
            "pages": None,
            "base": None,
            "actual": None,
            "vat": None,
            "with_vat": None,
            "note": "",
        }

        if contract is None:
            row["note"] = "у устройства не указан договор" if device else "устройство не найдено в договорах"
            rows.append(row)
            continue

        fields = _fields_for_row(report, groups[serial]) if serial else A4_FIELDS + A3_FIELDS
        row["pages"], row["base"] = _row_cost(report, contract, fields)
        row["actual"], row["note"] = _actual_cost(row["base"], report.k1, report.k2)
        row["vat"] = (row["actual"] * contract.vat_rate / Decimal(100)).quantize(KOPECK, rounding=ROUND_HALF_UP)
        row["with_vat"] = row["actual"] + row["vat"]

        totals["pages"] += row["pages"]
        totals["base"] += row["base"]
        totals["actual"] += row["actual"]
        totals["vat"] += row["vat"]
        totals["with_vat"] += row["with_vat"]
        rows.append(row)

    return rows, totals
