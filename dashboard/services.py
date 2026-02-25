"""
Dashboard services — агрегация данных из inventory, contracts, monthly_report.
Все функции кэшируются через Redis с TTL 5 минут.
"""
import re
import logging
from datetime import date, timedelta

from django.utils import timezone
from django.db.models import Count, Q, Max, Sum, OuterRef, Subquery, IntegerField
from django.db.models.functions import TruncMonth
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_TTL = 60 * 5  # 5 минут


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_percent(value: str) -> int | None:
    """Извлечь целое число из строки вида '75%', '75', 'N/A', пустой."""
    if not value:
        return None
    match = re.search(r'\d+', value)
    return int(match.group()) if match else None


def _cache_key(name: str, org_id, period_days=None) -> str:
    parts = [f'dashboard:{name}', f'org:{org_id or "all"}']
    if period_days is not None:
        parts.append(f'period:{period_days}')
    return ':'.join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Статус принтеров (online / offline)
# ─────────────────────────────────────────────────────────────────────────────

def get_printer_status(org_id=None):
    """
    Возвращает counts online/offline активных принтеров.
    «Online» = есть SUCCESS InventoryTask за последние 24 часа.
    """
    key = _cache_key('printer_status', org_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import Printer, InventoryTask

    since = timezone.now() - timedelta(hours=24)

    qs = Printer.objects.filter(is_active=True)
    if org_id:
        qs = qs.filter(organization_id=org_id)

    total = qs.count()

    # online: принтер, у которого есть SUCCESS за последние 24ч
    online_ids = (
        InventoryTask.objects
        .filter(status='SUCCESS', task_timestamp__gte=since, printer__is_active=True)
        .values_list('printer_id', flat=True)
        .distinct()
    )
    if org_id:
        online_ids = (
            InventoryTask.objects
            .filter(status='SUCCESS', task_timestamp__gte=since,
                    printer__is_active=True, printer__organization_id=org_id)
            .values_list('printer_id', flat=True)
            .distinct()
        )

    online = qs.filter(id__in=online_ids).count()
    offline = total - online
    percentage = round(online / total * 100) if total else 0

    result = {
        'total': total,
        'online': online,
        'offline': offline,
        'percentage': percentage,
    }
    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. Статистика опросов по статусам
# ─────────────────────────────────────────────────────────────────────────────

def get_poll_stats(org_id=None, period_days=7):
    key = _cache_key('poll_stats', org_id, period_days)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import InventoryTask

    cutoff = timezone.now() - timedelta(days=period_days)
    qs = InventoryTask.objects.filter(task_timestamp__gte=cutoff)
    if org_id:
        qs = qs.filter(printer__organization_id=org_id)

    rows = qs.values('status').annotate(count=Count('id')).order_by('status')
    result = [{'status': r['status'], 'count': r['count']} for r in rows]

    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. Расходники — критический уровень
# ─────────────────────────────────────────────────────────────────────────────

def get_low_consumables(org_id=None, threshold=20):
    key = _cache_key(f'low_consumables_{threshold}', org_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import Printer, InventoryTask, PageCounter

    # Последний успешный PageCounter для каждого активного принтера
    latest_task_sq = (
        InventoryTask.objects
        .filter(printer=OuterRef('id'), status='SUCCESS')
        .order_by('-task_timestamp')
        .values('id')[:1]
    )

    qs = Printer.objects.filter(is_active=True)
    if org_id:
        qs = qs.filter(organization_id=org_id)

    printer_ids = list(qs.values_list('id', flat=True))

    # Последние PageCounter для этих принтеров
    latest_task_ids = (
        InventoryTask.objects
        .filter(printer_id__in=printer_ids, status='SUCCESS')
        .values('printer_id')
        .annotate(last_id=Max('id'))
        .values_list('last_id', flat=True)
    )

    counters = (
        PageCounter.objects
        .filter(task_id__in=latest_task_ids)
        .select_related('task__printer', 'task__printer__organization', 'task__printer__device_model')
        .only(
            'task__printer__ip_address',
            'task__printer__model',
            'task__printer__organization__name',
            'task__printer__device_model',
            'toner_black', 'toner_cyan', 'toner_magenta', 'toner_yellow',
            'drum_black', 'drum_cyan', 'drum_magenta', 'drum_yellow',
            'task__task_timestamp',
        )
    )

    result = []
    for c in counters:
        consumable_fields = {
            'toner_black': c.toner_black,
            'toner_cyan': c.toner_cyan,
            'toner_magenta': c.toner_magenta,
            'toner_yellow': c.toner_yellow,
            'drum_black': c.drum_black,
            'drum_cyan': c.drum_cyan,
            'drum_magenta': c.drum_magenta,
            'drum_yellow': c.drum_yellow,
        }

        low = {}
        for field, val in consumable_fields.items():
            pct = _parse_percent(val)
            if pct is not None and pct < threshold:
                low[field] = pct

        if not low:
            continue

        printer = c.task.printer
        result.append({
            'printer_id': printer.id,
            'ip_address': printer.ip_address,
            'model': printer.device_model.name if printer.device_model else printer.model,
            'organization': printer.organization.name if printer.organization else '—',
            'last_poll': c.task.task_timestamp.isoformat(),
            'low_consumables': low,
            'min_level': min(low.values()),
        })

    result.sort(key=lambda x: x['min_level'])

    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Топ проблемных принтеров
# ─────────────────────────────────────────────────────────────────────────────

def get_problem_printers(org_id=None, period_days=7, limit=10):
    key = _cache_key(f'problem_printers_{limit}', org_id, period_days)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import InventoryTask

    cutoff = timezone.now() - timedelta(days=period_days)
    failure_statuses = ['FAILED', 'VALIDATION_ERROR', 'HISTORICAL_INCONSISTENCY']

    qs = (
        InventoryTask.objects
        .filter(status__in=failure_statuses, task_timestamp__gte=cutoff,
                printer__is_active=True)
    )
    if org_id:
        qs = qs.filter(printer__organization_id=org_id)

    rows = (
        qs.values(
            'printer_id',
            'printer__ip_address',
            'printer__model',
            'printer__organization__name',
        )
        .annotate(failure_count=Count('id'))
        .order_by('-failure_count')[:limit]
    )

    result = [
        {
            'printer_id': r['printer_id'],
            'ip_address': r['printer__ip_address'],
            'model': r['printer__model'],
            'organization': r['printer__organization__name'] or '—',
            'failure_count': r['failure_count'],
        }
        for r in rows
    ]

    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Тренд объёма печати по месяцам
# ─────────────────────────────────────────────────────────────────────────────

def get_print_trend(org_id=None, months=0):
    """
    months=0  → все доступные данные
    months=N  → последние N месяцев
    """
    key = _cache_key(f'print_trend_{months}', org_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from monthly_report.models import MonthlyReport

    qs = MonthlyReport.objects.all()
    if months and months > 0:
        today = date.today()
        year = today.year
        month = today.month - months
        while month <= 0:
            month += 12
            year -= 1
        cutoff = date(year, month, 1)
        qs = qs.filter(month__gte=cutoff)
    if org_id:
        # MonthlyReport.organization — строковое поле, совпадает с Organization.name
        from inventory.models import Organization
        try:
            org_name = Organization.objects.get(pk=org_id).name
            qs = qs.filter(organization=org_name)
        except Organization.DoesNotExist:
            qs = qs.none()

    rows = (
        qs.values('month')
        .annotate(total=Sum('total_prints'))
        .order_by('month')
    )

    result = [
        {
            'month': r['month'].strftime('%Y-%m'),
            'label': r['month'].strftime('%b %Y'),
            'total': r['total'] or 0,
        }
        for r in rows
    ]

    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5b. Детали по организации (устройства с последним статусом)
# ─────────────────────────────────────────────────────────────────────────────

def get_org_devices(org_id, status_filter=None):
    """
    Возвращает устройства организации с последним статусом опроса.
    status_filter: 'online' | 'offline' | None (все)
    """
    from inventory.models import Printer, InventoryTask
    from django.db.models import Subquery, OuterRef

    since = timezone.now() - timedelta(hours=24)

    last_status_sq = (
        InventoryTask.objects
        .filter(printer=OuterRef('pk'))
        .order_by('-task_timestamp')
        .values('status')[:1]
    )
    last_ts_sq = (
        InventoryTask.objects
        .filter(printer=OuterRef('pk'))
        .order_by('-task_timestamp')
        .values('task_timestamp')[:1]
    )

    qs = (
        Printer.objects
        .filter(is_active=True, organization_id=org_id)
        .select_related('device_model', 'device_model__manufacturer')
        .annotate(last_status=Subquery(last_status_sq), last_ts=Subquery(last_ts_sq))
        .order_by('ip_address')
    )

    # online = SUCCESS за последние 24ч
    online_ids = set(
        InventoryTask.objects
        .filter(status='SUCCESS', task_timestamp__gte=since, printer__is_active=True,
                printer__organization_id=org_id)
        .values_list('printer_id', flat=True)
        .distinct()
    )

    result = []
    for p in qs:
        is_online = p.id in online_ids
        if status_filter == 'online' and not is_online:
            continue
        if status_filter == 'offline' and is_online:
            continue

        result.append({
            'printer_id': p.id,
            'ip_address': p.ip_address,
            'model': p.device_model.name if p.device_model else p.model,
            'serial_number': p.serial_number,
            'last_status': p.last_status or '—',
            'last_poll': p.last_ts.isoformat() if p.last_ts else None,
            'is_online': is_online,
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 6. Сводка по организациям
# ─────────────────────────────────────────────────────────────────────────────

def get_org_summary():
    key = _cache_key('org_summary', None)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import Printer, Organization, InventoryTask

    since = timezone.now() - timedelta(hours=24)

    orgs = Organization.objects.filter(active=True)
    result = []

    for org in orgs:
        printers = Printer.objects.filter(is_active=True, organization=org)
        total = printers.count()
        if total == 0:
            continue

        online_ids = (
            InventoryTask.objects
            .filter(status='SUCCESS', task_timestamp__gte=since,
                    printer__is_active=True, printer__organization=org)
            .values_list('printer_id', flat=True)
            .distinct()
        )
        online = printers.filter(id__in=online_ids).count()
        online_pct = round(online / total * 100) if total else 0

        result.append({
            'org_id': org.id,
            'org_name': org.name,
            'total_printers': total,
            'online': online,
            'offline': total - online,
            'online_pct': online_pct,
        })

    result.sort(key=lambda x: x['org_name'])
    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 7. Последние опросы
# ─────────────────────────────────────────────────────────────────────────────

def get_recent_activity(org_id=None, limit=20):
    key = _cache_key(f'recent_activity_{limit}', org_id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import InventoryTask

    qs = (
        InventoryTask.objects
        .select_related('printer', 'printer__organization', 'printer__device_model')
        .filter(printer__is_active=True)
    )
    if org_id:
        qs = qs.filter(printer__organization_id=org_id)

    rows = qs.order_by('-task_timestamp')[:limit]

    result = [
        {
            'task_id': t.id,
            'printer_id': t.printer_id,
            'ip_address': t.printer.ip_address,
            'model': t.printer.device_model.name if t.printer.device_model else t.printer.model,
            'organization': t.printer.organization.name if t.printer.organization else '—',
            'status': t.status,
            'timestamp': t.task_timestamp.isoformat(),
            'error_message': t.error_message or '',
        }
        for t in rows
    ]

    cache.set(key, result, CACHE_TTL)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 8. Список организаций для фильтра
# ─────────────────────────────────────────────────────────────────────────────

def get_organizations():
    key = 'dashboard:organizations'
    cached = cache.get(key)
    if cached is not None:
        return cached

    from inventory.models import Organization

    orgs = Organization.objects.filter(active=True).values('id', 'name').order_by('name')
    result = list(orgs)
    cache.set(key, result, CACHE_TTL)
    return result
