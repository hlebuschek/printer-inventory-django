"""Пересчёт A/D/L/W в месячном отчёте из журнала заявок подрядчику.

Показатели качества по ТЗ считаются на единицу оборудования за отчётный месяц и идут
множителями в стоимость услуги (F = B*K1*K2). Поэтому числа должны быть воспроизводимы
из нашего журнала: отчёт подрядчика мы по договору только сверяем, а не принимаем на веру.

Строки отчёта, для которых устройство в договоре не нашлось, не трогаются: у них нет
ни графика объекта, ни заявок, и обнулять пришедшие из Excel числа было бы хуже, чем
оставить их как есть.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from django.db.models import Q
from django.db.models.functions import Trim, Upper

from contracts.models import ContractDevice, ServiceRequest, WorkSchedule
from contracts.services_working_hours import NoWorkingTimeError, WorkingTimeCalculator

from ..models import MonthlyReport

logger = logging.getLogger(__name__)

# Границы месяца зависят от часового пояса объекта, а выборка заявок общая на все города.
# Поэтому окно запроса к БД расширяем на сутки, а точную отсечку делаем по времени объекта.
TZ_MARGIN = timedelta(days=1)


def _normalized(serial):
    return (serial or "").strip().upper()


def _calculator(schedule, timezone_name, cache):
    """Калькуляторы кэшируются на весь пересчёт: каждый экземпляр читает исключения
    графика и производственный календарь, а графиков на весь договор единицы."""
    key = (schedule.pk, timezone_name)
    if key not in cache:
        cache[key] = WorkingTimeCalculator(schedule, timezone_name)
    return cache[key]


def _calculator_for_device(device, cache, default_schedule):
    schedule = device.resolve_work_schedule(default_schedule)
    if schedule is None:
        raise NoWorkingTimeError(f"Не задан график работы для устройства {device.serial_number}")
    return _calculator(schedule, device.city.timezone, cache)


def _calculator_for_request(service_request, device_calculator, cache):
    """Калькулятор по снимку графика заявки: справочник мог поменяться после подачи."""
    schedule = service_request.schedule_snapshot
    if schedule is None or schedule.pk == device_calculator.schedule.pk:
        return device_calculator
    return _calculator(schedule, device_calculator.tz.key, cache)


def _month_context(month_dt: date):
    """Строки отчёта по серийникам, найденные устройства договора и их заявки за месяц."""
    reports = list(MonthlyReport.objects.filter(month__year=month_dt.year, month__month=month_dt.month))
    rows_by_serial = defaultdict(list)
    for report in reports:
        if _normalized(report.serial_number):
            rows_by_serial[_normalized(report.serial_number)].append(report)

    devices = list(
        ContractDevice.objects.select_related("city", "work_schedule", "city__work_schedule")
        .annotate(normalized_serial=Upper(Trim("serial_number")))
        .filter(normalized_serial__in=rows_by_serial.keys())
    )
    return reports, rows_by_serial, devices, _requests_for_month(devices, month_dt)


def month_metrics_applied(month_dt: date):
    """Считает A/D/L/W и K1/K2 и проставляет их в объекты строк отчёта, НЕ сохраняя в БД.

    Отдельно от записи, потому что перезапись чисел месяца требует права
    `monthly_report.sync_from_inventory` и открытого окна редактирования, а показать
    актуальные показатели (например, в выгрузке на сверку) вправе любой читатель.

    Возвращает (все строки месяца, строки с пересчитанными метриками, статистика).
    """
    reports, rows_by_serial, devices, requests_by_device = _month_context(month_dt)

    updated, skipped_no_schedule = [], 0
    cache, default_schedule = {}, WorkSchedule.default()
    for device in devices:
        try:
            calculator = _calculator_for_device(device, cache, default_schedule)
        except NoWorkingTimeError:
            # Без графика норматив доступности не определён — строку не трогаем,
            # иначе K1 обнулится по причине, не имеющей отношения к качеству услуги.
            logger.warning("Нет графика работы для устройства %s — метрики не пересчитаны", device.serial_number)
            skipped_no_schedule += 1
            continue

        metrics = _device_metrics(calculator, month_dt, requests_by_device.get(device.pk, []), cache)
        for report in rows_by_serial[_normalized(device.serial_number)]:
            # Дубли строк по одному серийнику получают одинаковые проценты: K1/K2 —
            # характеристики единицы оборудования, а не суммируемые величины.
            report.normative_availability = metrics["A"]
            report.actual_downtime = metrics["D"]
            report.total_requests = metrics["W"]
            report.non_overdue_requests = metrics["L"]
            report.recalculate_quality_metrics()
            updated.append(report)

    matched_serials = {_normalized(device.serial_number) for device in devices}
    stats = {
        "updated_rows": len(updated),
        "devices_matched": len(matched_serials),
        "rows_without_device": sum(
            len(rows) for serial, rows in rows_by_serial.items() if serial not in matched_serials
        ),
        "skipped_no_schedule": skipped_no_schedule,
    }
    return reports, updated, stats


def recalculate_month_metrics(month_dt: date) -> dict:
    """Пересчитывает A/D/L/W и K1/K2 за месяц и сохраняет. Возвращает статистику для UI и логов."""
    _, updated, stats = month_metrics_applied(month_dt)

    MonthlyReport.objects.bulk_update(
        updated,
        ["normative_availability", "actual_downtime", "total_requests", "non_overdue_requests", "k1", "k2"],
        batch_size=500,
    )

    logger.info("Пересчёт K1/K2 за %s: %s", month_dt.strftime("%Y-%m"), stats)
    return stats


def _requests_for_month(devices, month_dt: date) -> dict[int, list[ServiceRequest]]:
    """Заявки, способные повлиять на показатели месяца: простой в периоде или срок в периоде."""
    if not devices:
        return {}

    window_start = datetime(month_dt.year, month_dt.month, 1, tzinfo=UTC) - TZ_MARGIN
    window_end = datetime(month_dt.year + month_dt.month // 12, month_dt.month % 12 + 1, 1, tzinfo=UTC) + TZ_MARGIN

    queryset = (
        ServiceRequest.objects.filter(device_id__in=[device.pk for device in devices])
        .exclude(status=ServiceRequest.REJECTED)
        .filter(
            # Простой в месяце: заявка началась до конца месяца и на его начало ещё не закрыта
            Q(registered_at__lt=window_end, restored_at__isnull=True)
            | Q(registered_at__lt=window_end, restored_at__gte=window_start)
            # Либо нормативный срок приходится на месяц — такая заявка идёт в W
            | Q(deadline_at__gte=window_start, deadline_at__lt=window_end)
        )
        .select_related("schedule_snapshot")
    )

    grouped = defaultdict(list)
    for service_request in queryset:
        grouped[service_request.device_id].append(service_request)
    return grouped


def _request_details(calculator, bounds, requests, cache) -> list[dict]:
    """Вклад каждой заявки в показатели месяца — из него собираются и суммы, и обоснование."""
    month_start, month_end = bounds
    details = []

    for service_request in requests:
        details.append(
            {
                "request": service_request,
                "downtime": service_request.downtime_hours(
                    since=month_start,
                    until=month_end,
                    calculator=_calculator_for_request(service_request, calculator, cache),
                ),
                # Повторное обращение по п.6.6.1 ТЗ наследует срок первичного, поэтому в W
                # учитывается только первичная заявка — иначе один инцидент считается дважды.
                "counts_in_w": bool(
                    service_request.counts_in_sla
                    and service_request.reopened_from_id is None
                    and service_request.deadline_at
                    and month_start <= service_request.deadline_at < month_end
                ),
            }
        )

    return details


def _device_metrics(calculator, month_dt: date, requests, cache) -> dict:
    bounds = calculator.month_bounds(month_dt.year, month_dt.month)
    details = _request_details(calculator, bounds, requests, cache)
    sla_details = [detail for detail in details if detail["counts_in_w"]]

    return {
        "A": calculator.working_hours_between(*bounds),
        "D": round(sum(detail["downtime"] for detail in details), 2),
        "W": len(sla_details),
        "L": sum(1 for detail in sla_details if not detail["request"].is_overdue),
    }


def month_journal_rows(month_dt: date) -> list[dict]:
    """Заявки, которыми обоснованы A/D/L/W месяца.

    Прикладывается к выгрузке: по договору мы сверяем отчёт подрядчика, и на спорную
    цифру нужно уметь показать конкретные заявки, а не только итог.
    """
    _, _, devices, requests_by_device = _month_context(month_dt)
    rows = []
    cache, default_schedule = {}, WorkSchedule.default()

    for device in devices:
        try:
            calculator = _calculator_for_device(device, cache, default_schedule)
        except NoWorkingTimeError:
            continue

        bounds = calculator.month_bounds(month_dt.year, month_dt.month)
        for detail in _request_details(calculator, bounds, requests_by_device.get(device.pk, []), cache):
            service_request = detail["request"]
            if not detail["downtime"] and not detail["counts_in_w"]:
                continue

            rows.append(
                {
                    "number": service_request.number,
                    "serial_number": device.serial_number,
                    "address": f"{device.city.name}, {device.address}".strip(", "),
                    "description": service_request.description,
                    "registered_at": service_request.registered_at,
                    "deadline_at": service_request.deadline_at,
                    "restored_at": service_request.restored_at,
                    "closed_at": service_request.closed_at,
                    "act_number": service_request.act_number,
                    "downtime": round(detail["downtime"], 2),
                    "counts_in_w": detail["counts_in_w"],
                    "is_overdue": service_request.is_overdue,
                }
            )

    rows.sort(key=lambda row: (row["serial_number"], row["registered_at"]))
    return rows
