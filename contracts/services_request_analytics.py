"""Аналитика журнала заявок.

Считается по тем же отобранным заявкам, что показывает журнал, — иначе цифры
на экране разойдутся с таблицей под ними. Разрез по подрядчику здесь главный:
договоров теперь несколько одновременно, и сравнивать их надо в одном месте.

Показатели операционные (сколько заявок, сколько просрочено, сколько простояли).
Договорные K1/K2 живут в месячном отчёте и считаются на единицу оборудования —
здесь их намеренно нет, чтобы не появилось второй «правды» о качестве услуги.
"""

from collections import defaultdict

from django.utils import timezone

from .models import ServiceRequest
from .services_working_hours import calculator_for_request

TOP_LIMIT = 10


def build_analytics(queryset):
    """Сводка, разрезы по подрядчику/городу/организации и динамика по дням."""
    requests = list(
        queryset.select_related("schedule_snapshot", "device__work_schedule", "device__city__work_schedule")
    )
    downtime = _downtime_by_request(requests)

    return {
        "summary": _summary(requests, downtime),
        "by_provider": _group(requests, downtime, lambda r: r.service_provider.name if r.service_provider_id else "—"),
        "by_city": _group(requests, downtime, lambda r: r.device.city.name if r.device.city_id else "—")[:TOP_LIMIT],
        "by_organization": _group(
            requests, downtime, lambda r: r.device.organization.name if r.device.organization_id else "—"
        )[:TOP_LIMIT],
        "daily": _daily(requests),
    }


def _downtime_by_request(requests):
    """Простой в рабочих часах по каждой заявке."""
    cache, result = {}, {}
    for service_request in requests:
        calculator = calculator_for_request(service_request, cache) if service_request.stops_printing else None
        if calculator is None:
            result[service_request.pk] = 0.0
            continue
        result[service_request.pk] = round(service_request.downtime_hours(calculator=calculator), 2)
    return result


def _summary(requests, downtime):
    overdue = sum(1 for r in requests if r.is_overdue)
    active = sum(1 for r in requests if r.closed_at is None and r.status != ServiceRequest.REJECTED)
    total_downtime = sum(downtime.values())
    return {
        "total": len(requests),
        "active": active,
        "overdue": overdue,
        "overdue_share": _percent(overdue, len(requests)),
        "downtime_hours": round(total_downtime, 1),
        "avg_downtime_hours": round(total_downtime / len(requests), 2) if requests else 0.0,
    }


def _group(requests, downtime, key):
    buckets = defaultdict(list)
    for service_request in requests:
        buckets[key(service_request)].append(service_request)

    rows = [_row(label, items, downtime) for label, items in buckets.items()]
    return sorted(rows, key=lambda row: (-row["total"], row["label"]))


def _row(label, items, downtime):
    overdue = sum(1 for r in items if r.is_overdue)
    total_downtime = sum(downtime[r.pk] for r in items)
    return {
        "label": label,
        "total": len(items),
        "overdue": overdue,
        "overdue_share": _percent(overdue, len(items)),
        "downtime_hours": round(total_downtime, 1),
        "avg_downtime_hours": round(total_downtime / len(items), 2) if items else 0.0,
    }


def _daily(requests):
    """Заведено и восстановлено по дням: видно, копится очередь или разгребается."""
    created, restored = defaultdict(int), defaultdict(int)
    for service_request in requests:
        created[timezone.localdate(service_request.registered_at)] += 1
        if service_request.restored_at:
            restored[timezone.localdate(service_request.restored_at)] += 1

    days = sorted(set(created) | set(restored))
    return [{"date": day.isoformat(), "created": created[day], "restored": restored[day]} for day in days]


def _percent(part, whole):
    return round(part * 100 / whole, 1) if whole else 0.0
