from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta, datetime, timezone as dt_timezone
from typing import Dict, Optional, Tuple, Set, List
import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from .models import MonthlyReport
from .services import recompute_group

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

    return start_local.astimezone(dt_timezone.utc), end_local.astimezone(dt_timezone.utc)


@dataclass
class SyncStats:
    updated_rows: int = 0
    groups_recomputed: int = 0
    errors: int = 0
    skipped_serials: int = 0
    manually_edited_skipped: int = 0


def _get_duplicate_groups(reports: List[MonthlyReport]) -> Dict[Tuple[str, str], List[MonthlyReport]]:
    """
    Группирует записи по (serial_number, inventory_number) и находит дубли.
    Возвращает только группы с 2+ записями.
    """
    groups = defaultdict(list)

    for r in reports:
        sn = (r.serial_number or '').strip()
        inv = (r.inventory_number or '').strip()
        if not sn and not inv:
            continue
        groups[(sn, inv)].append(r)

    # Сортируем записи внутри каждой группы по order_number и id
    for key in groups:
        groups[key].sort(key=lambda x: (x.order_number, x.id))

    # Оставляем только группы с дублями
    return {k: v for k, v in groups.items() if len(v) >= 2}


def _assign_autofields(
        report: MonthlyReport,
        start: Optional[Dict],
        end: Optional[Dict],
        *,
        only_empty: bool,
        is_duplicate: bool = False,
        dup_position: int = 0
) -> Tuple[bool, Set[str]]:
    """
    ЛОГИКА С УЧЕТОМ ДУБЛЕЙ:
    - *_auto поля обновляются всегда
    - *_end поля обновляются ВСЕГДА, КРОМЕ помеченных как manually_edited
    - ДЛЯ ДУБЛЕЙ: первая строка = только A4, остальные = только A3
    """
    changed = False
    updated_fields = set()

    # Определяем какие поля обновлять в зависимости от позиции дубля
    if is_duplicate:
        if dup_position == 0:
            # Первая строка дубля - только A4 end поля
            counter_mapping = {
                'a4_bw_end_auto': (end or {}).get("bw_a4"),
                'a4_color_end_auto': (end or {}).get("color_a4"),
            }
            # ТОЛЬКО end поля, start не трогаем (заполняются из Excel)
            main_auto_mapping = {
                'a4_bw_end': counter_mapping.get('a4_bw_end_auto'),
                'a4_color_end': counter_mapping.get('a4_color_end_auto'),
            }
        else:
            # Остальные строки дубля - только A3 end поля
            counter_mapping = {
                'a3_bw_end_auto': (end or {}).get("bw_a3"),
                'a3_color_end_auto': (end or {}).get("color_a3"),
            }
            # ТОЛЬКО end поля, start не трогаем (заполняются из Excel)
            main_auto_mapping = {
                'a3_bw_end': counter_mapping.get('a3_bw_end_auto'),
                'a3_color_end': counter_mapping.get('a3_color_end_auto'),
            }
    else:
        # Обычная запись (не дубль) - обновляем все end поля
        counter_mapping = {
            'a4_bw_end_auto': (end or {}).get("bw_a4"),
            'a4_color_end_auto': (end or {}).get("color_a4"),
            'a3_bw_end_auto': (end or {}).get("bw_a3"),
            'a3_color_end_auto': (end or {}).get("color_a3"),
        }
        # ТОЛЬКО end поля, start не трогаем (заполняются из Excel)
        main_auto_mapping = {
            'a4_bw_end': counter_mapping.get('a4_bw_end_auto'),
            'a4_color_end': counter_mapping.get('a4_color_end_auto'),
            'a3_bw_end': counter_mapping.get('a3_bw_end_auto'),
            'a3_color_end': counter_mapping.get('a3_color_end_auto'),
        }

    # 1. Обновляем auto поля всегда (если они есть в counter_mapping)
    for field_name, val in counter_mapping.items():
        if val is None or not hasattr(report, field_name):
            continue
        if getattr(report, field_name, None) != val:
            setattr(report, field_name, val)
            updated_fields.add(field_name)
            changed = True

    # 2. Основные поля = auto поля (кроме ручных)
    for field_name, auto_val in main_auto_mapping.items():
        if auto_val is None or not hasattr(report, field_name):
            continue

        # Пропускаем только ручные поля
        if report.is_field_manually_edited(field_name):
            logger.debug(
                f"Пропускаем поле {field_name} для записи {report.id}: "
                f"отредактировано вручную"
            )
            continue

        current = getattr(report, field_name)

        # Обновляем ВСЕГДА (не только пустые), если не ручное
        if current != auto_val:
            setattr(report, field_name, auto_val)
            updated_fields.add(field_name)
            changed = True

    return changed, updated_fields


def sync_month_from_inventory(month_dt: date, *, only_empty: bool = True) -> Dict:
    """
    Автоподтягивание счётчиков за месяц по серийнику с улучшенной безопасностью.

    ОБНОВЛЕННАЯ ЛОГИКА:
    - Поля *_end обновляются только если НЕ помечены как manually_edited
    - Поля *_auto обновляются всегда для справки
    - ДЛЯ ДУБЛЕЙ: первая строка получает A4, остальные — A3

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
        logger.exception(f"Ошибка синхронизации месяца {month_dt}")
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
    Внутренняя логика синхронизации месяца с БАТЧЕВЫМИ запросами.
    """
    logger.info(f"Начало синхронизации месяца {month_dt}, only_empty={only_empty}")

    period_start_utc, period_end_utc = _month_bounds_utc(month_dt)

    # Получаем записи для синхронизации
    with transaction.atomic():
        qs = (MonthlyReport.objects
              .select_for_update()
              .filter(month__year=month_dt.year, month__month=month_dt.month)
              .exclude(serial_number__isnull=True)
              .exclude(serial_number__exact=''))

        reports_list = list(qs)

    if not reports_list:
        logger.info(f"Нет записей для синхронизации в месяце {month_dt}")
        return {
            "ok": True,
            "updated_rows": 0,
            "groups_recomputed": 0,
            "manually_edited_skipped": 0,
            "skipped_serials": 0,
        }

    # ====== ОПРЕДЕЛЯЕМ ДУБЛИ ======
    duplicate_groups = _get_duplicate_groups(reports_list)

    # Создаем маппинг report.id -> (is_duplicate, position)
    report_dup_info = {}
    for (sn, inv), group_reports in duplicate_groups.items():
        for position, report in enumerate(group_reports):
            report_dup_info[report.id] = {
                'is_duplicate': True,
                'position': position,
                'group_size': len(group_reports)
            }

    logger.info(
        f"Найдено {len(duplicate_groups)} групп дублей "
        f"(всего {sum(len(g) for g in duplicate_groups.values())} записей)"
    )

    # ====== БАТЧЕВАЯ ЗАГРУЗКА ======
    # Собираем все уникальные серийники
    all_serials = list(set(
        r.serial_number.strip()
        for r in reports_list
        if r.serial_number and r.serial_number.strip()
    ))

    logger.info(f"Загрузка данных для {len(all_serials)} уникальных серийников")

    # Импортируем функцию батчевой загрузки
    try:
        from .integrations.inventory_batch import get_counters_for_month_batch
    except ImportError as e:
        logger.error(f"Не удалось импортировать inventory_batch: {e}")
        return {
            "ok": False,
            "error": f"Модуль inventory_batch недоступен: {e}",
            "updated_rows": 0,
            "groups_recomputed": 0,
        }

    # ОДИН набор запросов для всех серийников!
    inventory_data = get_counters_for_month_batch(
        all_serials,
        period_start_utc,
        period_end_utc
    )

    logger.info(f"Получено данных inventory для {len(inventory_data)} принтеров")

    stats = SyncStats()
    groups_to_recalc: Set[Tuple[str, str]] = set()
    now = timezone.now()

    # Обрабатываем записи батчами
    batch_size = 100
    for i in range(0, len(reports_list), batch_size):
        batch = reports_list[i:i + batch_size]

        try:
            with transaction.atomic():
                _process_sync_batch_optimized(
                    batch, inventory_data, report_dup_info, only_empty,
                    stats, groups_to_recalc, now
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

    logger.info(
        f"Синхронизация завершена: обновлено={stats.updated_rows}, "
        f"групп={stats.groups_recomputed}, ошибок={stats.errors}, "
        f"пропущено_серийников={stats.skipped_serials}, "
        f"ручное_редактирование={stats.manually_edited_skipped}"
    )

    return {
        "ok": True,
        "updated_rows": stats.updated_rows,
        "groups_recomputed": stats.groups_recomputed,
        "errors": stats.errors,
        "skipped_serials": stats.skipped_serials,
        "manually_edited_skipped": stats.manually_edited_skipped,
        "duplicate_groups": len(duplicate_groups),
        "period_start": period_start_utc.isoformat(),
        "period_end": period_end_utc.isoformat(),
    }


def _process_sync_batch_optimized(
        batch, inventory_data, report_dup_info, only_empty,
        stats, groups_to_recalc, now
):
    """
    Обработка батча с использованием предзагруженных данных.
    ВАЖНО: учитывает логику дублей (первая строка = A4, остальные = A3).
    """
    for r in batch:
        sn = (r.serial_number or "").strip()
        if not sn:
            stats.skipped_serials += 1
            continue

        # Берем данные из предзагруженного словаря
        data = inventory_data.get(sn)
        if not data:
            stats.skipped_serials += 1
            continue

        # Проверяем, является ли запись дублем
        dup_info = report_dup_info.get(r.id, {'is_duplicate': False, 'position': 0})

        try:
            updated_fields = set()
            any_change = False

            # Обновляем IP и время
            if data.get('ip') and r.device_ip != data['ip']:
                r.device_ip = data['ip']
                updated_fields.add('device_ip')
                any_change = True

            if data.get('last_ok') and r.inventory_last_ok != data['last_ok']:
                r.inventory_last_ok = data['last_ok']
                updated_fields.add('inventory_last_ok')
                any_change = True

            r.inventory_autosync_at = now
            updated_fields.add('inventory_autosync_at')

            # Обновляем счетчики С УЧЕТОМ ДУБЛЕЙ
            start = data.get('start')
            end = data.get('end')

            if start or end:
                counters_changed, counter_fields = _assign_autofields(
                    r, start, end,
                    only_empty=only_empty,
                    is_duplicate=dup_info['is_duplicate'],
                    dup_position=dup_info['position']
                )
                if counters_changed:
                    updated_fields.update(counter_fields)
                    any_change = True

            if any_change:
                r.save(update_fields=list(updated_fields))
                stats.updated_rows += 1
                groups_to_recalc.add((r.serial_number or "", r.inventory_number or ""))

                # Логируем обработку дублей
                if dup_info['is_duplicate']:
                    logger.debug(
                        f"Обновлен дубль: запись {r.id}, позиция {dup_info['position']}, "
                        f"поля: {counter_fields & {'a4_bw_end', 'a4_color_end', 'a3_bw_end', 'a3_color_end'} }"
                    )

        except Exception as e:
            logger.error(f"Ошибка синхронизации записи {r.id} (SN: {sn}): {e}")
            stats.errors += 1