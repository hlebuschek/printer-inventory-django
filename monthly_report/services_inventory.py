from __future__ import annotations
from typing import Iterable, Tuple, Dict, Any, Optional
from datetime import datetime
from django.apps import apps
from django.db.models import Q, OuterRef, Subquery, Max
import logging

logger = logging.getLogger(__name__)


def get_inventory_suggestions(
        pairs: Iterable[Tuple[str | None, str | None]]
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    Массовое получение данных из inventory для списка (serial_number, inventory_number).

    Возвращает dict с ключом (sn, inv) и данными:
      {
        'ip': str|None,
        'polled_at': datetime|None,
        'a4_bw': int,
        'a4_color': int,
        'a3_bw': int,
        'a3_color': int
      }

    ОПТИМИЗАЦИЯ: Всего 2 запроса вместо N:
    1. Получаем все Printer по серийникам
    2. Получаем последние успешные PageCounter для этих принтеров
    """
    try:
        Printer = apps.get_model("inventory", "Printer")
        InventoryTask = apps.get_model("inventory", "InventoryTask")
        PageCounter = apps.get_model("inventory", "PageCounter")
    except LookupError as e:
        logger.warning(f"Модели inventory не найдены: {e}")
        return {}

    # Нормализуем пары и собираем уникальные серийники
    norm_pairs = []
    serial_numbers = set()

    for sn, inv in pairs:
        sn = (sn or "").strip()
        inv = (inv or "").strip()
        norm_pairs.append((sn, inv))
        if sn:
            serial_numbers.add(sn)

    if not serial_numbers:
        return {}

    # ====== ЗАПРОС 1: Получаем все принтеры по серийникам ======
    printers = Printer.objects.filter(
        serial_number__in=list(serial_numbers)
    ).values(
        'id',
        'serial_number',
        'ip_address',
        'last_updated'
    )

    # Создаем маппинг serial_number -> printer_data
    printer_map = {
        p['serial_number']: {
            'id': p['id'],
            'ip': p['ip_address'],
            'last_updated': p['last_updated']
        }
        for p in printers
    }

    if not printer_map:
        logger.debug(f"Не найдено принтеров для серийников: {serial_numbers}")
        return {}

    printer_ids = [p['id'] for p in printer_map.values()]

    # ====== ЗАПРОС 2: Получаем последние счетчики для всех принтеров ======
    # Используем подзапрос для получения ID последней успешной задачи для каждого принтера
    latest_task_subquery = InventoryTask.objects.filter(
        printer_id=OuterRef('printer_id'),
        status='SUCCESS'
    ).order_by('-task_timestamp').values('id')[:1]

    # Получаем счетчики с последних успешных задач
    counters = PageCounter.objects.filter(
        task__printer_id__in=printer_ids,
        task__status='SUCCESS'
    ).select_related('task', 'task__printer').annotate(
        # Добавляем информацию о последней задаче
        latest_task_id=Subquery(latest_task_subquery)
    ).filter(
        task_id=OuterRef('latest_task_id')
    ).values(
        'task__printer__serial_number',
        'task__task_timestamp',
        'bw_a4',
        'color_a4',
        'bw_a3',
        'color_a3'
    )

    # Альтернативный вариант (может быть быстрее на PostgreSQL):
    # Используем DISTINCT ON для получения последней записи для каждого принтера
    latest_counters = PageCounter.objects.filter(
        task__printer_id__in=printer_ids,
        task__status='SUCCESS'
    ).select_related(
        'task',
        'task__printer'
    ).order_by(
        'task__printer_id',
        '-task__task_timestamp'
    ).distinct('task__printer_id')

    # Создаем маппинг serial_number -> counter_data
    counter_map = {}
    for counter in latest_counters:
        sn = counter.task.printer.serial_number
        counter_map[sn] = {
            'polled_at': counter.task.task_timestamp,
            'a4_bw': int(counter.bw_a4 or 0),
            'a4_color': int(counter.color_a4 or 0),
            'a3_bw': int(counter.bw_a3 or 0),
            'a3_color': int(counter.color_a3 or 0),
        }

    # ====== ФОРМИРУЕМ РЕЗУЛЬТАТ ======
    result: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for sn, inv in norm_pairs:
        if not sn:
            continue

        printer_data = printer_map.get(sn)
        if not printer_data:
            continue

        counter_data = counter_map.get(sn, {})

        result[(sn, inv)] = {
            'ip': printer_data.get('ip'),
            'polled_at': counter_data.get('polled_at') or printer_data.get('last_updated'),
            'a4_bw': counter_data.get('a4_bw', 0),
            'a4_color': counter_data.get('a4_color', 0),
            'a3_bw': counter_data.get('a3_bw', 0),
            'a3_color': counter_data.get('a3_color', 0),
        }

    logger.info(
        f"Загружено данных inventory: "
        f"{len(serial_numbers)} серийников -> "
        f"{len(printer_map)} принтеров -> "
        f"{len(counter_map)} счетчиков"
    )

    return result


# ====== ДОПОЛНИТЕЛЬНАЯ ОПТИМИЗАЦИЯ: Если вам нужен только последний снимок ======

def get_inventory_latest_counters(
        serial_numbers: Iterable[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Еще более оптимизированная версия - получает только последние счетчики.
    Один запрос с JOIN и DISTINCT ON (работает только на PostgreSQL).

    Возвращает: {serial_number: {ip, polled_at, a4_bw, a4_color, a3_bw, a3_color}}
    """
    try:
        Printer = apps.get_model("inventory", "Printer")
        InventoryTask = apps.get_model("inventory", "InventoryTask")
        PageCounter = apps.get_model("inventory", "PageCounter")
    except LookupError:
        return {}

    serial_list = [s.strip() for s in serial_numbers if s and s.strip()]
    if not serial_list:
        return {}

    # Одним запросом получаем принтеры с их последними счетчиками
    data = (
        PageCounter.objects
        .filter(
            task__printer__serial_number__in=serial_list,
            task__status='SUCCESS'
        )
        .select_related('task__printer')
        .order_by('task__printer__serial_number', '-task__task_timestamp')
        .distinct('task__printer__serial_number')
        .values(
            'task__printer__serial_number',
            'task__printer__ip_address',
            'task__task_timestamp',
            'bw_a4',
            'color_a4',
            'bw_a3',
            'color_a3'
        )
    )

    result = {}
    for row in data:
        sn = row['task__printer__serial_number']
        result[sn] = {
            'ip': row['task__printer__ip_address'],
            'polled_at': row['task__task_timestamp'],
            'a4_bw': int(row['bw_a4'] or 0),
            'a4_color': int(row['color_a4'] or 0),
            'a3_bw': int(row['bw_a3'] or 0),
            'a3_color': int(row['color_a3'] or 0),
        }

    return result


# ====== ДЛ�Я ИСПОЛЬЗОВАНИЯ В sync_month_from_inventory ======

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
    except LookupError:
        return {}

    serial_list = [s.strip() for s in serial_numbers if s and s.strip()]
    if not serial_list:
        return {}

    # Получаем принтеры
    printers = Printer.objects.filter(
        serial_number__in=serial_list
    ).values('id', 'serial_number', 'ip_address')

    printer_map = {p['id']: p for p in printers}
    sn_to_id = {p['serial_number']: p['id'] for p in printers}

    if not printer_map:
        return {}

    # Получаем все успешные задачи в периоде для этих принтеров
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

    # Группируем по принтеру
    from collections import defaultdict
    printer_counters = defaultdict(list)

    for tc in tasks_counters:
        printer_counters[tc['task__printer_id']].append({
            'timestamp': tc['task__task_timestamp'],
            'bw_a4': tc['bw_a4'],
            'color_a4': tc['color_a4'],
            'bw_a3': tc['bw_a3'],
            'color_a3': tc['color_a3'],
        })

    # Формируем результат
    result = {}

    for printer_id, counters in printer_counters.items():
        if not counters:
            continue

        printer = printer_map[printer_id]
        sn = printer['serial_number']

        # Сортируем по времени (если еще не отсортировано)
        counters.sort(key=lambda x: x['timestamp'])

        start_counter = counters[0] if counters else None
        end_counter = counters[-1] if counters else None

        result[sn] = {
            'ip': printer['ip_address'],
            'last_ok': end_counter['timestamp'] if end_counter else None,
            'start': {
                'bw_a4': start_counter['bw_a4'],
                'color_a4': start_counter['color_a4'],
                'bw_a3': start_counter['bw_a3'],
                'color_a3': start_counter['color_a3'],
            } if start_counter else None,
            'end': {
                'bw_a4': end_counter['bw_a4'],
                'color_a4': end_counter['color_a4'],
                'bw_a3': end_counter['bw_a3'],
                'color_a3': end_counter['color_a3'],
            } if end_counter else None,
        }

    return result