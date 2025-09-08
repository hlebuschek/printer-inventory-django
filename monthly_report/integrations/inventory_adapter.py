# monthly_report/integrations/inventory_adapter.py - оптимизированная версия
from __future__ import annotations
from typing import Optional, Dict, List
from datetime import datetime
import logging

from django.apps import apps
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def _extract_counters(snap) -> Dict[str, int]:
    """
    Возвращает счётчики строго в формате модели PageCounter:
    bw_a4, color_a4, bw_a3, color_a3.
    """
    if not snap:
        return {"bw_a4": 0, "color_a4": 0, "bw_a3": 0, "color_a3": 0}

    return {
        "bw_a4": int(getattr(snap, "bw_a4", 0) or 0),
        "color_a4": int(getattr(snap, "color_a4", 0) or 0),
        "bw_a3": int(getattr(snap, "bw_a3", 0) or 0),
        "color_a3": int(getattr(snap, "color_a3", 0) or 0),
    }


def fetch_printer_info_by_serial(serial: str) -> Optional[Dict]:
    """
    Возвращает {'ip': <ip|None>, 'last_ok': <datetime|None>} по серийному номеру.
    """
    serial = (serial or "").strip()
    if not serial:
        return None

    try:
        Printer = apps.get_model("inventory", "Printer")
        PageSnap = apps.get_model("inventory", "PageCounter")
    except LookupError:
        logger.warning("Модели inventory.Printer или inventory.PageCounter не найдены")
        return None

    try:
        printer = (
            Printer.objects
            .filter(serial_number__iexact=serial)
            .only('id', 'ip_address')  # Оптимизация: загружаем только нужные поля
            .first()
        )
        if not printer:
            return None

        ip = getattr(printer, "ip_address", None)

        # Оптимизированный запрос на последний успешный снимок
        last_ok_snap = (
            PageSnap.objects
            .filter(task__printer=printer, task__status="SUCCESS")
            .only('recorded_at')  # Загружаем только время
            .order_by("-recorded_at")
            .first()
        )
        last_ok = getattr(last_ok_snap, "recorded_at", None) if last_ok_snap else None

        return {"ip": ip, "last_ok": last_ok}

    except Exception as e:
        logger.error(f"Ошибка получения информации о принтере {serial}: {e}")
        return None


def fetch_counters_snaps_for_range(
        serial: str, period_start: datetime, period_end: datetime
) -> Dict[str, Optional[Dict]]:
    """
    Счётчики на начало/конец периода (или ближайшие внутри):
      {'start': {'bw_a4':..., 'color_a4':..., 'bw_a3':..., 'color_a3':...} | None,
       'end':   {...} | None}
    Берём только PageCounter у задач со статусом SUCCESS.
    """
    serial = (serial or "").strip()
    if not serial:
        return {"start": None, "end": None}

    try:
        Printer = apps.get_model("inventory", "Printer")
        PageSnap = apps.get_model("inventory", "PageCounter")
    except LookupError:
        logger.warning("Модели inventory.Printer или inventory.PageCounter не найдены")
        return {"start": None, "end": None}

    try:
        printer = (
            Printer.objects
            .filter(serial_number__iexact=serial)
            .only('id')  # Нужен только ID для связи
            .first()
        )
        if not printer:
            return {"start": None, "end": None}

        # Базовый QuerySet с оптимизацией
        qs = (
            PageSnap.objects
            .filter(task__printer=printer, task__status="SUCCESS")
            .only('recorded_at', 'bw_a4', 'color_a4', 'bw_a3', 'color_a3')  # Только нужные поля
            .order_by("recorded_at")
        )

        # Старт: первый в диапазоне [start..end], иначе ближайший после start
        start_snap = qs.filter(recorded_at__gte=period_start, recorded_at__lte=period_end).first()
        if not start_snap:
            start_snap = qs.filter(recorded_at__gte=period_start).first()

        # Конец: последний в диапазоне, иначе ближайший до end
        end_snap = (
            qs.filter(recorded_at__gte=period_start, recorded_at__lte=period_end)
            .order_by("-recorded_at")
            .first()
        )
        if not end_snap:
            end_snap = qs.filter(recorded_at__lte=period_end).order_by("-recorded_at").first()

        return {
            "start": _extract_counters(start_snap) if start_snap else None,
            "end": _extract_counters(end_snap) if end_snap else None,
        }

    except Exception as e:
        logger.error(f"Ошибка получения счетчиков для принтера {serial}: {e}")
        return {"start": None, "end": None}


def fetch_multiple_printer_info(serials: List[str]) -> Dict[str, Dict]:
    """
    Массовое получение информации о принтерах для оптимизации.
    Возвращает словарь {serial: {'ip': ..., 'last_ok': ...}}
    """
    if not serials:
        return {}

    # Очищаем серийники
    clean_serials = [(s or "").strip() for s in serials if (s or "").strip()]
    if not clean_serials:
        return {}

    try:
        Printer = apps.get_model("inventory", "Printer")
        PageSnap = apps.get_model("inventory", "PageCounter")
    except LookupError:
        logger.warning("Модели inventory.Printer или inventory.PageCounter не найдены")
        return {}

    try:
        # Получаем все принтеры одним запросом
        printers = list(
            Printer.objects
            .filter(serial_number__in=clean_serials)
            .only('id', 'serial_number', 'ip_address')
        )

        if not printers:
            return {}

        # Получаем последние успешные снимки для всех принтеров
        from django.db.models import OuterRef, Subquery

        latest_snaps = (
            PageSnap.objects
            .filter(task__printer_id=OuterRef('id'), task__status='SUCCESS')
            .only('recorded_at')
            .order_by('-recorded_at')
            .values('recorded_at')[:1]
        )

        printers_with_snaps = (
            Printer.objects
            .filter(id__in=[p.id for p in printers])
            .annotate(last_snap_time=Subquery(latest_snaps))
            .values('serial_number', 'ip_address', 'last_snap_time')
        )

        result = {}
        for printer_data in printers_with_snaps:
            serial = printer_data['serial_number']
            if serial:
                result[serial] = {
                    'ip': printer_data['ip_address'],
                    'last_ok': printer_data['last_snap_time']
                }

        return result

    except Exception as e:
        logger.error(f"Ошибка массового получения информации о принтерах: {e}")
        return {}