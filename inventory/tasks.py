# inventory/tasks.py
import logging
from typing import Optional, Dict, Any

from celery import shared_task
from django.utils import timezone

from .models import Printer, InventoryTask
from .services import run_inventory_for_printer

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, priority=9)
def run_inventory_task_priority(
    self,
    printer_id: int,
    user_id: Optional[int] = None,
    xml_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Приоритетная задача опроса принтера (для пользовательских запросов).
    БЕЗ rate limiting через Redis - для 30 пользователей не нужно.
    """
    try:
        # Проверяем существование принтера
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer {printer_id} does not exist")
            return {
                'success': False,
                'error': f'Printer {printer_id} not found'
            }

        # Запускаем инвентаризацию
        logger.info(
            f"Starting PRIORITY inventory for printer {printer_id} "
            f"({printer.ip_address})"
        )
        success, message = run_inventory_for_printer(printer_id, xml_path)

        result = {
            'success': success,
            'message': message,
            'printer_id': printer_id,
            'printer_ip': printer.ip_address,
            'timestamp': timezone.now().isoformat(),
            'priority': True,
            'user_id': user_id,
        }

        logger.info(
            f"PRIORITY inventory completed for printer {printer_id}: "
            f"{'SUCCESS' if success else 'FAILED'}"
        )
        return result

    except Exception as exc:
        logger.error(
            f"Error in priority inventory task for printer {printer_id}: {exc}",
            exc_info=True
        )

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying priority inventory for printer {printer_id}, "
                f"attempt {self.request.retries + 1}"
            )
            raise self.retry(exc=exc, countdown=30)

        return {
            'success': False,
            'error': str(exc),
            'printer_id': printer_id,
            'timestamp': timezone.now().isoformat(),
            'priority': True,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60, priority=1)
def run_inventory_task(
    self,
    printer_id: int,
    xml_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Обычная задача опроса принтера (для периодического демона).
    Низкий приоритет.
    """
    try:
        # Проверяем существование принтера
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer {printer_id} does not exist")
            return {
                'success': False,
                'error': f'Printer {printer_id} not found'
            }

        # Запускаем инвентаризацию
        logger.info(f"Starting inventory for printer {printer_id} ({printer.ip_address})")
        success, message = run_inventory_for_printer(printer_id, xml_path)

        result = {
            'success': success,
            'message': message,
            'printer_id': printer_id,
            'printer_ip': printer.ip_address,
            'timestamp': timezone.now().isoformat(),
            'priority': False,
        }

        logger.info(
            f"Inventory completed for printer {printer_id}: "
            f"{'SUCCESS' if success else 'FAILED'}"
        )
        return result

    except Exception as exc:
        logger.error(
            f"Error in inventory task for printer {printer_id}: {exc}",
            exc_info=True
        )

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying inventory for printer {printer_id}, "
                f"attempt {self.request.retries + 1}"
            )
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

        return {
            'success': False,
            'error': str(exc),
            'printer_id': printer_id,
            'timestamp': timezone.now().isoformat(),
            'priority': False,
        }


@shared_task(bind=True)
def inventory_daemon_task(self):
    """
    Периодическая задача для опроса всех принтеров.
    Запускает обычные (низкоприоритетные) задачи.
    """
    logger.info("Starting inventory daemon task")

    try:
        printers = Printer.objects.all()
        logger.info(f"Found {printers.count()} printers for inventory")

        if not printers.exists():
            return {
                'success': True,
                'message': 'No printers to poll',
                'count': 0
            }

        # Запускаем задачи для каждого принтера
        task_ids = []

        for printer in printers:
            # Используем обычную (низкоприоритетную) задачу
            task = run_inventory_task.apply_async(
                args=[printer.id],
                priority=1  # Низкий приоритет
            )
            task_ids.append(task.id)
            logger.debug(f"Queued task {task.id} for printer {printer.ip_address}")

        logger.info(f"Queued {len(task_ids)} inventory tasks")

        return {
            'success': True,
            'message': f'Queued {len(task_ids)} inventory tasks',
            'task_ids': task_ids,
            'total_printers': printers.count(),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Error in inventory daemon task: {exc}", exc_info=True)
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat(),
        }


@shared_task
def cleanup_old_inventory_data():
    """Задача для очистки старых данных инвентаризации."""
    try:
        from datetime import timedelta

        # Удаляем задачи старше 90 дней
        cutoff_date = timezone.now() - timedelta(days=90)
        old_tasks = InventoryTask.objects.filter(task_timestamp__lt=cutoff_date)
        deleted_count = old_tasks.count()
        old_tasks.delete()

        logger.info(f"Cleaned up {deleted_count} old inventory tasks")

        return {
            'success': True,
            'deleted_tasks': deleted_count,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Error in cleanup task: {exc}", exc_info=True)
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat(),
        }