# inventory/tasks.py
import logging
from typing import Optional, Dict, Any

from celery import shared_task
from django.utils import timezone

from .models import Printer, InventoryTask
from .services import run_inventory_for_printer

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, priority=9, queue='high_priority')
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


@shared_task(bind=True, max_retries=3, default_retry_delay=60, priority=1, queue='low_priority')
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


@shared_task(bind=True, queue='daemon')
def inventory_daemon_task(self):
    """
    Периодическая задача для опроса всех принтеров.
    Запускает обычные (низкоприоритетные) задачи.
    """
    logger.warning("=" * 80)
    logger.warning("STARTING INVENTORY DAEMON TASK")
    logger.warning(f"Task ID: {self.request.id}")
    logger.warning(f"Timestamp: {timezone.now()}")
    logger.warning("=" * 80)

    try:
        # ВАЖНО: получаем ВСЕ принтеры без фильтров
        printers = Printer.objects.all().order_by('id')
        total_count = printers.count()

        logger.warning(f"Found {total_count} printers in database")

        # Логируем первые и последние ID для проверки
        if printers.exists():
            first_id = printers.first().id
            last_id = printers.last().id
            logger.warning(f"Printer IDs range: {first_id} to {last_id}")

        if not printers.exists():
            logger.warning("No printers found - exiting")
            return {
                'success': True,
                'message': 'No printers to poll',
                'count': 0
            }

        # Запускаем задачи для каждого принтера
        task_ids = []
        failed_to_queue = []
        sample_ips = []

        for idx, printer in enumerate(printers, 1):
            try:
                # Используем обычную (низкоприоритетную) задачу
                task = run_inventory_task.apply_async(
                    args=[printer.id],
                    priority=1
                )
                task_ids.append(task.id)

                # Сохраняем примеры IP
                if len(sample_ips) < 20:
                    sample_ips.append(f"{printer.id}:{printer.ip_address}")

                # Логируем прогресс каждые 100 принтеров
                if idx % 100 == 0:
                    logger.warning(f"Progress: {idx}/{total_count} tasks queued")

            except Exception as e:
                logger.error(f"FAILED to queue task for printer {printer.id} ({printer.ip_address}): {e}")
                failed_to_queue.append(printer.id)

        logger.warning("=" * 80)
        logger.warning(f"DAEMON COMPLETED")
        logger.warning(f"Successfully queued: {len(task_ids)}/{total_count}")
        logger.warning(f"Failed to queue: {len(failed_to_queue)}")

        if failed_to_queue:
            logger.error(f"Failed printer IDs: {failed_to_queue}")

        logger.warning(f"Sample queued (first 20): {sample_ips}")
        logger.warning("=" * 80)

        return {
            'success': True,
            'message': f'Queued {len(task_ids)}/{total_count} inventory tasks',
            'task_ids': task_ids[:10],
            'failed_ids': failed_to_queue,
            'total_printers': total_count,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"CRITICAL ERROR IN DAEMON TASK: {exc}", exc_info=True)
        logger.error("=" * 80)
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