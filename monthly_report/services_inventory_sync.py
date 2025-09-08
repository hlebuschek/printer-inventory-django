from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone as dt_timezone
from typing import Dict, Optional, Tuple, Set
import logging

from django.db import transaction, IntegrityError
from django.utils import timezone
from django.core.cache import cache

from .models import MonthlyReport
from .services import recompute_group
from .integrations.inventory_adapter import (
    fetch_printer_info_by_serial,
    fetch_counters_snaps_for_range,
)

logger = logging.getLogger(__name__)


def _month_bounds_utc(month_dt: date) -> Tuple[datetime, datetime]:
    """
    Возвращает UTC-границы месяца с учётом локальной TZ.
    Конец — либо конец месяца, либо текущее время (если текущий месяц).
    """
    tz = timezone.get_current_timezone()

    start_local = datetime(month_dt.year, month_dt.month, 1, 0, 0, 0, tzinfo=tz)
    if month_dt.month == 12:
        next_local = datetime(month_dt.year + 1, 1, 1, 0, 0, 0, tzinfo=tz)
    else:
        next_local = datetime(month_dt.year, month_dt.month + 1, 1, 0, 0, 0, tzinfo=tz)

    end_local = min(timezone.localtime(), next_local - timedelta(seconds=1))

    # ИСПРАВЛЕНИЕ: используем datetime.timezone.utc вместо timezone.utc
    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)


@dataclass
class SyncStats:
    updated_rows: int = 0
    groups_recomputed: int = 0
    errors: int = 0
    skipped_serials: int = 0


def _assign_autofields(report: MonthlyReport, start: Optional[Dict], end: Optional[Dict],
                       *, only_empty: bool) -> Tuple[bool, Set[str]]:
    """
    Заполняет *_auto и, если ручные поля пустые — копирует авто в них.
    Возвращает: (changed: bool, updated_fields: Set[str])
    """
    changed = False
    updated_fields = set()

    # читаем строго по ключам PageCounter
    counter_mapping = {
        'a4_bw_start_auto': (start or {}).get("bw_a4"),
        'a4_bw_end_auto': (end or {}).get("bw_a4"),
        'a4_color_start_auto': (start or {}).get("color_a4"),
        'a4_color_end_auto': (end or {}).get("color_a4"),
        'a3_bw_start_auto': (start or {}).get("bw_a3"),
        'a3_bw_end_auto': (end or {}).get("bw_a3"),
        'a3_color_start_auto': (start or {}).get("color_a3"),
        'a3_color_end_auto': (end or {}).get("color_a3"),
    }

    # Обновляем auto поля
    for field_name, val in counter_mapping.items():
        if val is None or not hasattr(report, field_name):
            continue
        if getattr(report, field_name, None) != val:
            setattr(report, field_name, val)
            updated_fields.add(field_name)
            changed = True

    # Зеркалируем в основные поля при необходимости
    mirror_mapping = {
        'a4_bw_start': counter_mapping['a4_bw_start_auto'],
        'a4_bw_end': counter_mapping['a4_bw_end_auto'],
        'a4_color_start': counter_mapping['a4_color_start_auto'],
        'a4_color_end': counter_mapping['a4_color_end_auto'],
        'a3_bw_start': counter_mapping['a3_bw_start_auto'],
        'a3_bw_end': counter_mapping['a3_bw_end_auto'],
        'a3_color_start': counter_mapping['a3_color_start_auto'],
        'a3_color_end': counter_mapping['a3_color_end_auto'],
    }

    for field_name, val in mirror_mapping.items():
        if val is None or not hasattr(report, field_name):
            continue

        current = getattr(report, field_name)
        should_update = False

        if only_empty:
            # Для числовых полей IntegerField проверяем только None и 0
            should_update = current is None or current == 0
        else:
            # Обновляем всегда
            should_update = True

        if should_update and current != val:
            setattr(report, field_name, val)
            updated_fields.add(field_name)
            changed = True

    return changed, updated_fields


def sync_month_from_inventory(month_dt: date, *, only_empty: bool = True) -> Dict:
    """
    Автоподтягивание счётчиков за месяц по серийнику с улучшенной безопасностью.

    Возвращает статистику синхронизации.
    """
    sync_key = f"sync_month_{month_dt.strftime('%Y_%m')}"

    # Защита от одновременной синхронизации того же месяца
    if cache.get(sync_key):
        logger.warning(f"Синхронизация месяца {month_dt} уже выполняется")
        return {
            "ok": False,
            "error": "Синхронизация уже выполняется",
            "updated_rows": 0,
            "groups_recomputed": 0,
        }

    try:
        # Устанавливаем блокировку на 10 минут
        cache.set(sync_key, True, timeout=600)

        return _sync_month_internal(month_dt, only_empty=only_empty)

    except Exception as e:
        logger.error(f"Ошибка синхронизации месяца {month_dt}: {e}")
        return {
            "ok": False,
            "error": str(e),
            "updated_rows": 0,
            "groups_recomputed": 0,
        }
    finally:
        cache.delete(sync_key)


def _sync_month_internal(month_dt: date, *, only_empty: bool) -> Dict:
    """
    Внутренняя логика синхронизации месяца.
    """
    logger.info(f"Начало синхронизации месяца {month_dt}, only_empty={only_empty}")

    period_start_utc, period_end_utc = _month_bounds_utc(month_dt)

    # Получаем записи для синхронизации с блокировкой
    with transaction.atomic():
        qs = (MonthlyReport.objects
              .select_for_update()
              .filter(month__year=month_dt.year, month__month=month_dt.month)
              .exclude(serial_number__isnull=True)
              .exclude(serial_number__exact='')
              .only("id", "serial_number", "inventory_number",
                    "a4_bw_start", "a4_bw_end", "a4_color_start", "a4_color_end",
                    "a3_bw_start", "a3_bw_end", "a3_color_start", "a3_color_end",
                    "a4_bw_end_auto", "a4_color_end_auto", "a3_bw_end_auto", "a3_color_end_auto",
                    "device_ip", "inventory_last_ok", "inventory_autosync_at"))

        reports_list = list(qs)

    if not reports_list:
        logger.info(f"Нет записей для синхронизации в месяце {month_dt}")
        return {
            "ok": True,
            "updated_rows": 0,
            "groups_recomputed": 0,
            "period_start_utc": period_start_utc,
            "period_end_utc": period_end_utc,
        }

    stats = SyncStats()
    groups_to_recalc: Set[Tuple[str, str]] = set()

    # Кэш для минимизации запросов к Inventory
    cache_info: Dict[str, Dict] = {}
    cache_range: Dict[str, Dict] = {}

    now = timezone.now()

    # Обрабатываем записи батчами для лучшей производительности
    batch_size = 50
    for i in range(0, len(reports_list), batch_size):
        batch = reports_list[i:i + batch_size]

        try:
            with transaction.atomic():
                _process_sync_batch(
                    batch, period_start_utc, period_end_utc, only_empty,
                    cache_info, cache_range, stats, groups_to_recalc, now
                )
        except Exception as e:
            logger.error(f"Ошибка обработки батча {i}-{i + batch_size}: {e}")
            stats.errors += 1

    # Пересчитываем группы
    for sn, inv in groups_to_recalc:
        try:
            recompute_group(month_dt, sn, inv)
            stats.groups_recomputed += 1
        except Exception as e:
            logger.error(f"Ошибка пересчета группы {sn or inv}: {e}")
            stats.errors += 1

    logger.info(f"Синхронизация месяца {month_dt} завершена: "
                f"обновлено={stats.updated_rows}, групп={stats.groups_recomputed}, "
                f"ошибок={stats.errors}, пропущено={stats.skipped_serials}")

    return {
        "ok": True,
        "updated_rows": stats.updated_rows,
        "groups_recomputed": stats.groups_recomputed,
        "errors": stats.errors,
        "skipped_serials": stats.skipped_serials,
        "period_start_utc": period_start_utc,
        "period_end_utc": period_end_utc,
    }


def _process_sync_batch(
        batch, period_start_utc, period_end_utc, only_empty,
        cache_info, cache_range, stats, groups_to_recalc, now
):
    """
    Обрабатывает батч записей для синхронизации.
    """
    for r in batch:
        sn = (r.serial_number or "").strip()
        if not sn:
            stats.skipped_serials += 1
            continue

        try:
            # Получаем информацию из кэша или делаем запрос
            if sn not in cache_info:
                cache_info[sn] = fetch_printer_info_by_serial(sn) or {}

            if sn not in cache_range:
                cache_range[sn] = fetch_counters_snaps_for_range(
                    sn, period_start_utc, period_end_utc
                ) or {}

            info = cache_info[sn]
            rng = cache_range[sn]

            # Обновляем поля принтера
            updated_fields = set()
            any_change = False

            ip = info.get("ip")
            last_ok = info.get("last_ok")

            if ip and getattr(r, "device_ip", None) != ip:
                r.device_ip = ip
                updated_fields.add("device_ip")
                any_change = True

            if last_ok and getattr(r, "inventory_last_ok", None) != last_ok:
                r.inventory_last_ok = last_ok
                updated_fields.add("inventory_last_ok")
                any_change = True

            if hasattr(r, "inventory_autosync_at"):
                r.inventory_autosync_at = now
                updated_fields.add("inventory_autosync_at")
                any_change = True

            # Обновляем счетчики
            start = rng.get("start")
            end = rng.get("end")

            if start or end:
                counters_changed, counter_fields = _assign_autofields(r, start, end, only_empty=only_empty)
                if counters_changed:
                    updated_fields.update(counter_fields)
                    any_change = True

            # Сохраняем изменения
            if any_change:
                r.save(update_fields=list(updated_fields))
                stats.updated_rows += 1
                groups_to_recalc.add((r.serial_number or "", r.inventory_number or ""))

        except Exception as e:
            logger.error(f"Ошибка синхронизации записи {r.id} (SN: {sn}): {e}")
            stats.errors += 1