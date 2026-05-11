"""
Аналитика для Service Desk-дашборда Okdesk:
- timeseries «создано/закрыто» по дням за период,
- топ исполнителей по количеству закрытых заявок,
- среднее время от создания до закрытия,
- KPI: всего создано/закрыто за период.

Все агрегаты считаются distinct по issue_id, потому что одна заявка может быть
представлена несколькими строками OkdeskIssue (по одной на ContractDevice).
"""

from datetime import datetime, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import OkdeskIssue
from .services_okdesk_dashboard import (
    ACTIVE_STATUSES,
    CLOSED_STATUS,
    _apply_author,
    _apply_search,
    _mine_filter,
    _parse_optional_date,
)


def _resolve_period(date_from, date_to):
    """Возвращает (date_from, date_to, start_dt, end_dt). По умолчанию — 30 дней."""
    df = _parse_optional_date(date_from)
    dt = _parse_optional_date(date_to)
    today = timezone.localdate()
    if not dt:
        dt = today
    if not df:
        df = dt - timedelta(days=29)  # последние 30 дней (включая dt)
    if df > dt:
        df, dt = dt, df
    start_dt = timezone.make_aware(datetime.combine(df, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(dt, datetime.min.time())) + timedelta(days=1)
    return df, dt, start_dt, end_dt


def _base_qs(user=None, mine=False, search="", author=""):
    """Базовый queryset с применением общих фильтров (без статуса/диапазона дат)."""
    qs = OkdeskIssue.objects.all()
    if mine and user:
        qs = _mine_filter(qs, user)
    qs = _apply_search(qs, search)
    qs = _apply_author(qs, author)
    return qs


def _daily_counts(qs, field, start_dt, end_dt):
    """Сколько уникальных заявок попадает в каждый день периода по полю `field`
    (created_at или completed_at)."""
    rows = (
        qs.filter(**{f"{field}__gte": start_dt, f"{field}__lt": end_dt})
        .annotate(day=TruncDate(field))
        .values("day")
        .annotate(c=Count("issue_id", distinct=True))
    )
    return {r["day"]: r["c"] for r in rows}


def _date_range(start_date, end_date):
    """Список date-объектов от start до end включительно."""
    days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=i) for i in range(days)]


def get_okdesk_analytics(
    date_from=None,
    date_to=None,
    user=None,
    mine=False,
    search="",
    author="",
    only_period_created=False,
):
    """Сводная аналитика за период.

    `only_period_created` — учитывать в среднем/медиане времени решения только
    заявки, СОЗДАННЫЕ внутри того же периода (а не «закрытые в периоде, но
    висевшие полгода»). По умолчанию False — берём всё, что закрыто в периоде.

    Возвращает dict:
        period: {date_from, date_to}
        totals: {created, closed, active_now, resolution: {...}}
        timeseries: [{date, created, closed}, ...]
        top_assignees: [{assignee, closed}, ...] (top 10)
    """
    df, dt, start_dt, end_dt = _resolve_period(date_from, date_to)
    base = _base_qs(user=user, mine=mine, search=search, author=author)

    # Per-day counts
    created_map = _daily_counts(base, "created_at", start_dt, end_dt)
    closed_qs = base.filter(status_name=CLOSED_STATUS)
    closed_map = _daily_counts(closed_qs, "completed_at", start_dt, end_dt)

    timeseries = [
        {
            "date": day.isoformat(),
            "created": created_map.get(day, 0),
            "closed": closed_map.get(day, 0),
        }
        for day in _date_range(df, dt)
    ]

    total_created = sum(p["created"] for p in timeseries)
    total_closed = sum(p["closed"] for p in timeseries)

    # Top assignees: считаем по уникальным issue_id среди закрытых в периоде.
    top_rows = (
        closed_qs.filter(completed_at__gte=start_dt, completed_at__lt=end_dt)
        .exclude(assignee_name="")
        .exclude(assignee_name__isnull=True)
        .values("assignee_name")
        .annotate(c=Count("issue_id", distinct=True))
        .order_by("-c")[:10]
    )
    top_assignees = [{"assignee": r["assignee_name"], "closed": r["c"]} for r in top_rows]

    # Среднее/медиана времени решения для заявок, закрытых в периоде.
    resolution = _resolution_stats(closed_qs, start_dt, end_dt, only_period_created=only_period_created)

    # Активных сейчас (без учёта периода — снимок).
    active_now = base.filter(status_name__in=ACTIVE_STATUSES).values("issue_id").distinct().count()

    return {
        "period": {"date_from": df.isoformat(), "date_to": dt.isoformat()},
        "totals": {
            "created": total_created,
            "closed": total_closed,
            "active_now": active_now,
            "resolution": resolution,
        },
        "timeseries": timeseries,
        "top_assignees": top_assignees,
    }


def _resolution_stats(closed_qs, start_dt, end_dt, only_period_created=False):
    """Время от создания до закрытия (часы) — среднее, медиана, размер выборки.

    Берёт заявки, ЗАКРЫТЫЕ в [start_dt, end_dt). Если `only_period_created` —
    дополнительно требует, чтобы и created_at был в том же периоде (так
    исключаются «долгожители», которые висели задолго до периода и завышают
    среднее).
    """
    qs = closed_qs.filter(completed_at__gte=start_dt, completed_at__lt=end_dt)
    if only_period_created:
        qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_dt)

    rows = qs.values("issue_id", "created_at", "completed_at")
    seen = set()
    seconds = []
    for r in rows:
        iid = r["issue_id"]
        if iid in seen:
            continue
        seen.add(iid)
        cr, cl = r["created_at"], r["completed_at"]
        if not cr or not cl or cl < cr:
            continue
        seconds.append((cl - cr).total_seconds())

    if not seconds:
        return {
            "avg_hours": None,
            "median_hours": None,
            "sample_size": 0,
            "only_period_created": bool(only_period_created),
        }

    seconds.sort()
    n = len(seconds)
    avg = sum(seconds) / n
    if n % 2 == 1:
        median = seconds[n // 2]
    else:
        median = (seconds[n // 2 - 1] + seconds[n // 2]) / 2

    return {
        "avg_hours": round(avg / 3600, 1),
        "median_hours": round(median / 3600, 1),
        "sample_size": n,
        "only_period_created": bool(only_period_created),
    }
