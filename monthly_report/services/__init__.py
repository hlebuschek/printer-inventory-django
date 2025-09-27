# monthly_report/services/__init__.py - обновленная версия с логикой дублей

from __future__ import annotations
import logging
from typing import Optional, Iterable, List, Tuple
from django.db import transaction, models
from ..models import MonthlyReport

logger = logging.getLogger(__name__)


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


def _calculate_page_counts(obj: MonthlyReport) -> Tuple[int, int, int]:
    """
    Вычисляет счетчики A4 и A3 для объекта.
    Возвращает: (a4_total, a3_total, combined_total)
    """
    a4_bw = _pair(obj, "a4_bw_start", "a4_bw_end")
    a4_color = _pair(obj, "a4_color_start", "a4_color_end")
    a3_bw = _pair(obj, "a3_bw_start", "a3_bw_end")
    a3_color = _pair(obj, "a3_color_start", "a3_color_end")

    a4_total = a4_bw + a4_color
    a3_total = a3_bw + a3_color
    combined_total = a4_total + a3_total

    return a4_total, a3_total, combined_total


@transaction.atomic
def recompute_group(month, serial: Optional[str], inventory: Optional[str]) -> None:
    """
    Пересчитать total_prints в группе за указанный месяц.

    НОВАЯ ЛОГИКА для дублирующихся серийников:
    - Если в группе 1 запись: A4 + A3
    - Если в группе >1 запись (дубли): первая строка = только A4, остальные = только A3

    Правило группировки:
    - Если задан serial -> по serial (case-insensitive)
    - Иначе по inventory (case-insensitive)
    - Пустые ключи не группируются
    """
    sn = (serial or "").strip()
    inv = (inventory or "").strip()

    if not sn and not inv:
        logger.warning(f"recompute_group: пустые ключи для месяца {month}")
        return

    # Формируем запрос
    qs = MonthlyReport.objects.select_for_update().filter(month=month)
    if sn:
        qs = qs.filter(serial_number__iexact=sn)
    else:
        qs = qs.filter(inventory_number__iexact=inv)

    rows = list(qs.order_by("order_number", "id"))
    if not rows:
        logger.info(f"recompute_group: нет записей для {sn or inv} в {month}")
        return

    # Вычисляем счетчики для каждой записи
    calculations = []
    total_a4 = total_a3 = 0

    for row in rows:
        a4_total, a3_total, combined = _calculate_page_counts(row)
        calculations.append((row, a4_total, a3_total, combined))
        total_a4 += a4_total
        total_a3 += a3_total

    # НОВАЯ ЛОГИКА: применяем правила дублей
    if len(rows) == 1:
        # Одна запись: просто A4 + A3
        row, a4, a3, combined = calculations[0]
        row.total_prints = combined
        logger.debug(f"Одиночная запись {row.id}: total_prints = {combined}")
    else:
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: для дублей применяем строгую логику A4/A3
        _distribute_prints_for_duplicates(calculations)

    # Сохраняем изменения
    MonthlyReport.objects.bulk_update([calc[0] for calc in calculations], ["total_prints"])

    logger.info(f"recompute_group: обновлено {len(rows)} записей для {sn or inv} в {month}")


def _distribute_prints_for_duplicates(calculations: List[Tuple[MonthlyReport, int, int, int]]) -> None:
    """
    НОВАЯ ФУНКЦИЯ: Распределяет счетчики в группе дублей согласно строгой логике:
    - Первая строка (по order_number, id): получает только A4
    - Остальные строки: получают только A3

    Это предотвращает двойной учёт и обеспечивает правильную логику разделения форматов.
    """
    if not calculations:
        return

    # Сортируем по order_number и id для предсказуемого порядка
    sorted_calcs = sorted(calculations, key=lambda x: (x[0].order_number, x[0].id))

    # Первая строка = только A4
    first_row, first_a4, first_a3, _ = sorted_calcs[0]
    first_row.total_prints = first_a4
    logger.debug(f"Дубль - первая строка {first_row.id}: total_prints = {first_a4} (только A4)")

    # Остальные строки = только A3
    for i, (row, row_a4, row_a3, _) in enumerate(sorted_calcs[1:], 1):
        row.total_prints = row_a3
        logger.debug(f"Дубль - строка #{i + 1} {row.id}: total_prints = {row_a3} (только A3)")


def recompute_month(month) -> None:
    """
    Массовый пересчёт месяца с улучшенной производительностью и логированием.
    Теперь учитывает новую логику дублей.
    """
    logger.info(f"Начало пересчета месяца {month}")

    try:
        with transaction.atomic():
            # Все непустые серийники
            serials = (
                MonthlyReport.objects.filter(month=month)
                .exclude(serial_number__isnull=True)
                .exclude(serial_number__exact="")
                .values_list("serial_number", flat=True)
                .distinct()
            )

            logger.info(f"Найдено {len(serials)} уникальных серийников")

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

            logger.info(f"Найдено {len(inventories)} уникальных инвентарных номеров")

            for inv in inventories:
                recompute_group(month, None, inv)

    except Exception as e:
        logger.error(f"Ошибка при пересчете месяца {month}: {e}")
        raise

    logger.info(f"Пересчет месяца {month} завершен успешно")


def get_duplicate_summary(month) -> dict:
    """
    НОВАЯ ФУНКЦИЯ: Возвращает сводку по дублирующимся записям в месяце.
    Полезно для отладки и мониторинга.
    """
    from collections import defaultdict

    reports = MonthlyReport.objects.filter(month=month).values(
        'id', 'serial_number', 'inventory_number', 'order_number',
        'total_prints', 'a4_bw_start', 'a4_bw_end', 'a4_color_start', 'a4_color_end',
        'a3_bw_start', 'a3_bw_end', 'a3_color_start', 'a3_color_end'
    ).order_by('order_number', 'id')

    groups = defaultdict(list)
    for r in reports:
        sn = (r['serial_number'] or '').strip()
        inv = (r['inventory_number'] or '').strip()
        if not sn and not inv:
            continue
        groups[(sn, inv)].append(r)

    # Анализируем только группы с дублями
    duplicate_groups = {}
    total_duplicates = 0

    for key, reports_list in groups.items():
        if len(reports_list) >= 2:
            sn, inv = key
            sorted_reports = sorted(reports_list, key=lambda x: (x['order_number'], x['id']))

            group_info = {
                'key': key,
                'count': len(sorted_reports),
                'reports': []
            }

            for pos, r in enumerate(sorted_reports):
                a4_total = max(0, (r['a4_bw_end'] or 0) - (r['a4_bw_start'] or 0)) + \
                           max(0, (r['a4_color_end'] or 0) - (r['a4_color_start'] or 0))
                a3_total = max(0, (r['a3_bw_end'] or 0) - (r['a3_bw_start'] or 0)) + \
                           max(0, (r['a3_color_end'] or 0) - (r['a3_color_start'] or 0))

                expected_total = a4_total if pos == 0 else a3_total

                group_info['reports'].append({
                    'id': r['id'],
                    'position': pos,
                    'order_number': r['order_number'],
                    'a4_prints': a4_total,
                    'a3_prints': a3_total,
                    'actual_total': r['total_prints'],
                    'expected_total': expected_total,
                    'is_correct': r['total_prints'] == expected_total
                })

            duplicate_groups[f"{sn or 'NO_SN'}_{inv or 'NO_INV'}"] = group_info
            total_duplicates += len(sorted_reports)

    return {
        'month': month,
        'total_reports': len(reports),
        'total_duplicates': total_duplicates,
        'duplicate_groups_count': len(duplicate_groups),
        'groups': duplicate_groups
    }