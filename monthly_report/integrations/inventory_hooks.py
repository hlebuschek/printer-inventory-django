# monthly_report/integrations/inventory_hooks.py
"""
Интеграционные хуки для автоматической синхронизации с inventory приложением
"""
from typing import Optional
import logging
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


def on_inventory_snapshot_saved(sender, instance, created, **kwargs):
    """
    Обработчик сигнала для новых снимков PageCounter из inventory.
    Автоматически обновляет связанные записи MonthlyReport.
    """
    if not created:
        return  # обрабатываем только новые записи

    try:
        # Получаем принтер из задачи
        task = getattr(instance, 'task', None)
        if not task:
            return

        printer = getattr(task, 'printer', None)
        if not printer:
            return

        # Получаем серийный номер
        serial_number = getattr(printer, 'serial_number', None)
        if not serial_number:
            return

        serial_number = serial_number.strip()
        if not serial_number:
            return

        # Определяем текущий месяц
        now = timezone.now()
        current_month = date(now.year, now.month, 1)

        # Ищем записи MonthlyReport для этого принтера в текущем месяце
        from ..models import MonthlyReport

        reports = MonthlyReport.objects.filter(
            month=current_month,
            serial_number__iexact=serial_number
        )

        if not reports.exists():
            logger.debug(f"Нет записей MonthlyReport для принтера {serial_number} в месяце {current_month}")
            return

        # Получаем счетчики из снимка
        counters = {
            'bw_a4': int(getattr(instance, 'bw_a4', 0) or 0),
            'color_a4': int(getattr(instance, 'color_a4', 0) or 0),
            'bw_a3': int(getattr(instance, 'bw_a3', 0) or 0),
            'color_a3': int(getattr(instance, 'color_a3', 0) or 0),
        }

        # Обновляем поля *_end_auto в записях
        updated_reports = []
        for report in reports:
            updated = False

            # Проверяем каждое поле *_end и обновляем соответствующее *_auto
            mapping = {
                'a4_bw_end_auto': counters['bw_a4'],
                'a4_color_end_auto': counters['color_a4'],
                'a3_bw_end_auto': counters['bw_a3'],
                'a3_color_end_auto': counters['color_a3'],
            }

            for auto_field, counter_value in mapping.items():
                if hasattr(report, auto_field):
                    current_auto = getattr(report, auto_field, 0)
                    if current_auto != counter_value:
                        setattr(report, auto_field, counter_value)
                        updated = True

            # Обновляем информацию о принтере
            if hasattr(report, 'device_ip'):
                printer_ip = getattr(printer, 'ip_address', None)
                if printer_ip and report.device_ip != printer_ip:
                    report.device_ip = printer_ip
                    updated = True

            if hasattr(report, 'inventory_last_ok'):
                snapshot_time = getattr(instance, 'recorded_at', None) or now
                if report.inventory_last_ok != snapshot_time:
                    report.inventory_last_ok = snapshot_time
                    updated = True

            if hasattr(report, 'inventory_autosync_at'):
                report.inventory_autosync_at = now
                updated = True

            if updated:
                updated_reports.append(report)

        # Сохраняем изменения батчем
        if updated_reports:
            update_fields = [
                'a4_bw_end_auto', 'a4_color_end_auto', 'a3_bw_end_auto', 'a3_color_end_auto',
                'device_ip', 'inventory_last_ok', 'inventory_autosync_at'
            ]

            # Фильтруем поля, которые действительно есть в модели
            actual_fields = []
            for field in update_fields:
                if hasattr(updated_reports[0], field):
                    actual_fields.append(field)

            MonthlyReport.objects.bulk_update(updated_reports, actual_fields)

            logger.info(f"Автосинхронизация: обновлено {len(updated_reports)} записей для принтера {serial_number}")

            # Опционально: пересчитываем группы
            try:
                from ..services import recompute_group
                for report in updated_reports:
                    recompute_group(report.month, report.serial_number, report.inventory_number)
            except Exception as e:
                logger.error(f"Ошибка пересчета группы после автосинхронизации: {e}")

    except Exception as e:
        logger.error(f"Ошибка в автосинхронизации inventory: {e}")


def get_optimal_sync_period(printer_serial: str) -> Optional[tuple]:
    """
    Определяет оптимальный период для синхронизации конкретного принтера
    на основе истории его опросов.

    Возвращает: (start_date, end_date) или None
    """
    try:
        # Здесь может быть логика анализа истории опросов
        # и определения оптимального периода для синхронизации

        # Пока возвращаем текущий месяц
        now = timezone.now()
        start = date(now.year, now.month, 1)

        if now.month == 12:
            end = date(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(now.year, now.month + 1, 1) - timedelta(days=1)

        return start, end

    except Exception as e:
        logger.error(f"Ошибка определения периода синхронизации для {printer_serial}: {e}")
        return None