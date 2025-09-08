# monthly_report/services/__init__.py - исправленная версия

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

    Правило группировки:
    - Если задан serial -> по serial (case-insensitive)
    - Иначе по inventory (case-insensitive)
    - Пустые ключи не группируются

    Новая логика раскладки:
    - Если в группе 1 запись: A4 + A3
    - Если >1: распределяем пропорционально по order_number
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

    # Применяем логику распределения
    if len(rows) == 1:
        # Одна запись: просто A4 + A3
        row, a4, a3, combined = calculations[0]
        row.total_prints = combined
        logger.debug(f"Одиночная запись {row.id}: total_prints = {combined}")
    else:
        # Несколько записей: используем улучшенную логику
        _distribute_prints_in_group(calculations)

    # Сохраняем изменения
    MonthlyReport.objects.bulk_update([calc[0] for calc in calculations], ["total_prints"])

    logger.info(f"recompute_group: обновлено {len(rows)} записей для {sn or inv} в {month}")


def _distribute_prints_in_group(calculations: List[Tuple[MonthlyReport, int, int, int]]) -> None:
    """
    Распределяет счетчики в группе согласно бизнес-логике.

    Новая логика:
    - Первая запись (по order_number): получает все A4 + пропорциональную долю A3
    - Остальные записи: получают оставшиеся A3 пропорционально
    """
    if not calculations:
        return

    # Сортируем по order_number для предсказуемости
    sorted_calcs = sorted(calculations, key=lambda x: (x[0].order_number, x[0].id))

    total_a4 = sum(calc[1] for calc in sorted_calcs)
    total_a3 = sum(calc[2] for calc in sorted_calcs)

    if total_a4 == 0 and total_a3 == 0:
        # Нет печати вообще
        for row, _, _, _ in sorted_calcs:
            row.total_prints = 0
        return

    # Первая запись получает весь A4
    first_row = sorted_calcs[0][0]
    first_row.total_prints = total_a4

    logger.debug(f"Первая запись {first_row.id}: total_prints = {total_a4} (весь A4)")

    # Распределяем A3 между остальными записями
    remaining_rows = sorted_calcs[1:]
    if remaining_rows and total_a3 > 0:
        # Вычисляем доли A3 для каждой записи
        remaining_a3_totals = [calc[2] for calc in remaining_rows]
        sum_remaining_a3 = sum(remaining_a3_totals)

        if sum_remaining_a3 > 0:
            for i, (row, _, a3_own, _) in enumerate(remaining_rows):
                # Пропорциональное распределение
                proportion = a3_own / sum_remaining_a3
                allocated_a3 = round(total_a3 * proportion)
                row.total_prints = allocated_a3

                logger.debug(f"Запись {row.id}: total_prints = {allocated_a3} "
                             f"(A3: {a3_own}/{sum_remaining_a3} * {total_a3})")
        else:
            # Если у остальных записей нет A3, распределяем поровну
            per_record = total_a3 // len(remaining_rows)
            remainder = total_a3 % len(remaining_rows)

            for i, (row, _, _, _) in enumerate(remaining_rows):
                allocation = per_record + (1 if i < remainder else 0)
                row.total_prints = allocation
                logger.debug(f"Запись {row.id}: total_prints = {allocation} (равное распределение A3)")


def recompute_month(month) -> None:
    """
    Массовый пересчёт месяца с улучшенной производительностью и логированием.
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