from __future__ import annotations
from typing import Iterable, Dict, Any
from datetime import datetime
from django.apps import apps
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


def get_counters_for_month_batch(
        serial_numbers: Iterable[str],
        period_start_utc: datetime,
        period_end_utc: datetime
) -> Dict[str, Dict[str, Any]]:
    """
    Получает начальные и конечные счетчики для батча серийников за период.

    Возвращает: {
        serial_number: {
            'start': {bw_a4, color_a4, bw_a3, color_a3} | None,
            'end': {bw_a4, color_a4, bw_a3, color_a3} | None,
            'ip': str,
            'last_ok': datetime
        }
    }
    """
    try:
        Printer = apps.get_model("inventory", "Printer")
        InventoryTask = apps.get_model("inventory", "InventoryTask")
        PageCounter = apps.get_model("inventory", "PageCounter")
    except LookupError as e:
        logger.warning(f"Модели inventory не найдены: {e}")
        return {}

    serial_list = [s.strip() for s in serial_numbers if s and s.strip()]
    if not serial_list:
        return {}

    # ====== ЗАПРОС 1: Получаем принтеры ======
    printers = Printer.objects.filter(
        serial_number__in=serial_list
    ).values('id', 'serial_number', 'ip_address')

    printer_map = {p['id']: p for p in printers}

    if not printer_map:
        logger.debug(f"Принтеры не найдены для {len(serial_list)} серийников")
        return {}

    logger.debug(f"Найдено {len(printer_map)} принтеров из {len(serial_list)} серийников")

    # ====== ЗАПРОС 2: Получаем все счетчики за период ======
    tasks_counters = (
        PageCounter.objects
        .filter(
            task__printer_id__in=list(printer_map.keys()),
            task__status='SUCCESS',
            task__task_timestamp__gte=period_start_utc,
            task__task_timestamp__lte=period_end_utc
        )
        .select_related('task')
        .order_by('task__printer_id', 'task__task_timestamp')
        .values(
            'task__printer_id',
            'task__task_timestamp',
            'bw_a4',
            'color_a4',
            'bw_a3',
            'color_a3'
        )
    )

    # ====== ГРУППИРУЕМ ПО ПРИНТЕРУ ======
    printer_counters = defaultdict(list)

    for tc in tasks_counters:
        printer_counters[tc['task__printer_id']].append({
            'timestamp': tc['task__task_timestamp'],
            'bw_a4': tc['bw_a4'],
            'color_a4': tc['color_a4'],
            'bw_a3': tc['bw_a3'],
            'color_a3': tc['color_a3'],
        })

    logger.debug(f"Найдено счетчиков для {len(printer_counters)} принтеров")

    # ====== ФОРМИРУЕМ РЕЗУЛЬТАТ ======
    result = {}

    for printer_id, counters in printer_counters.items():
        if not counters:
            continue

        printer = printer_map[printer_id]
        sn = printer['serial_number']

        # Сортируем по времени (на всякий случай, хотя уже должно быть отсортировано)
        counters.sort(key=lambda x: x['timestamp'])

        start_counter = counters[0]
        end_counter = counters[-1]

        result[sn] = {
            'ip': printer['ip_address'],
            'last_ok': end_counter['timestamp'],
            'start': {
                'bw_a4': start_counter['bw_a4'],
                'color_a4': start_counter['color_a4'],
                'bw_a3': start_counter['bw_a3'],
                'color_a3': start_counter['color_a3'],
            },
            'end': {
                'bw_a4': end_counter['bw_a4'],
                'color_a4': end_counter['color_a4'],
                'bw_a3': end_counter['bw_a3'],
                'color_a3': end_counter['color_a3'],
            },
        }

    logger.info(
        f"Батчевая загрузка: {len(serial_list)} серийников -> "
        f"{len(printer_map)} принтеров -> {len(result)} с данными"
    )

    return result