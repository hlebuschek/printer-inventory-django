import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Printer, InventoryTask
from .services import run_inventory_for_printer

logger = logging.getLogger(__name__)


# Rate limiter для пользователей
class UserRateLimiter:
    """Ограничение количества запросов от пользователя"""

    @staticmethod
    def check_rate_limit(user_id: int, printer_id: int) -> bool:
        """Проверяет, может ли пользователь запустить опрос"""
        # Ключ для пользователя
        user_key = f'inventory_rate_user_{user_id}'
        # Ключ для конкретного принтера и пользователя
        printer_key = f'inventory_rate_printer_{user_id}_{printer_id}'

        # Проверяем общий лимит пользователя (5 запросов в минуту)
        user_count = cache.get(user_key, 0)
        if user_count >= 5:
            return False

        # Проверяем, не опрашивается ли уже этот принтер этим пользователем
        if cache.get(printer_key):
            return False

        # Увеличиваем счётчики
        cache.set(user_key, user_count + 1, timeout=60)  # 1 минута
        cache.set(printer_key, True, timeout=30)  # 30 секунд на опрос

        return True

    @staticmethod
    def clear_printer_lock(user_id: int, printer_id: int):
        """Снимает блокировку с принтера"""
        printer_key = f'inventory_rate_printer_{user_id}_{printer_id}'
        cache.delete(printer_key)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, priority=9)
def run_inventory_task_priority(self, printer_id: int, user_id: Optional[int] = None,
                                xml_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Приоритетная задача опроса принтера (для пользовательских запросов).

    Args:
        printer_id: ID принтера
        user_id: ID пользователя, запустившего опрос
        xml_path: Опциональный путь к XML файлу

    Returns:
        Dict с результатом выполнения
    """
    try:
        # Проверяем, что принтер существует
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer with ID {printer_id} does not exist")
            if user_id:
                UserRateLimiter.clear_printer_lock(user_id, printer_id)
            return {'success': False, 'error': f'Printer {printer_id} not found'}

        # Проверяем, не запущена ли уже задача для этого принтера
        task_cache_key = f'inventory_task_running_{printer_id}'
        if cache.get(task_cache_key):
            logger.warning(f"Inventory task for printer {printer_id} already running")
            if user_id:
                UserRateLimiter.clear_printer_lock(user_id, printer_id)
            return {'success': False, 'error': 'Task already running'}

        # Устанавливаем флаг выполнения
        cache.set(task_cache_key, True, timeout=60 * 5)  # 5 минут максимум

        try:
            # Запускаем инвентаризацию
            logger.info(f"Starting PRIORITY inventory task for printer {printer_id} ({printer.ip_address})")
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

            # Кэшируем результат
            cache.set(f'last_inventory_{printer_id}', result, timeout=60 * 60 * 24)  # 24 часа

            logger.info(
                f"PRIORITY inventory task completed for printer {printer_id}: {'SUCCESS' if success else 'FAILED'}")
            return result

        finally:
            # Убираем блокировки
            cache.delete(task_cache_key)
            if user_id:
                UserRateLimiter.clear_printer_lock(user_id, printer_id)

    except Exception as exc:
        logger.error(f"Error in priority inventory task for printer {printer_id}: {exc}", exc_info=True)

        if user_id:
            UserRateLimiter.clear_printer_lock(user_id, printer_id)

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying priority inventory task for printer {printer_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=exc, countdown=30)

        return {
            'success': False,
            'error': str(exc),
            'printer_id': printer_id,
            'timestamp': timezone.now().isoformat(),
            'priority': True,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60, priority=1)
def run_inventory_task(self, printer_id: int, xml_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Обычная задача опроса принтера (для периодического демона).
    Низкий приоритет.

    Args:
        printer_id: ID принтера
        xml_path: Опциональный путь к XML файлу

    Returns:
        Dict с результатом выполнения
    """
    try:
        # Проверяем, что принтер существует
        try:
            printer = Printer.objects.get(pk=printer_id)
        except Printer.DoesNotExist:
            logger.error(f"Printer with ID {printer_id} does not exist")
            return {'success': False, 'error': f'Printer {printer_id} not found'}

        # Проверяем кэш на предмет недавнего опроса
        recent_cache_key = f'inventory_recent_{printer_id}'
        if cache.get(recent_cache_key):
            logger.debug(f"Skipping printer {printer_id} - recently polled")
            return {'success': True, 'message': 'Recently polled, skipped', 'printer_id': printer_id}

        # Проверяем кэш на предмет дублирования задач
        cache_key = f'inventory_task_{printer_id}'
        if cache.get(cache_key):
            logger.warning(f"Inventory task for printer {printer_id} already running")
            return {'success': False, 'error': 'Task already running'}

        # Устанавливаем блокировку в кэше
        cache.set(cache_key, True, timeout=60 * 10)  # 10 минут

        try:
            # Запускаем инвентаризацию
            logger.info(f"Starting inventory task for printer {printer_id} ({printer.ip_address})")
            success, message = run_inventory_for_printer(printer_id, xml_path)

            result = {
                'success': success,
                'message': message,
                'printer_id': printer_id,
                'printer_ip': printer.ip_address,
                'timestamp': timezone.now().isoformat(),
                'priority': False,
            }

            # Кэшируем результат и ставим метку о недавнем опросе
            cache.set(f'last_inventory_{printer_id}', result, timeout=60 * 60 * 24)  # 24 часа
            if success:
                cache.set(recent_cache_key, True, timeout=60 * 30)  # 30 минут - не опрашивать повторно

            logger.info(f"Inventory task completed for printer {printer_id}: {'SUCCESS' if success else 'FAILED'}")
            return result

        finally:
            # Убираем блокировку
            cache.delete(cache_key)

    except Exception as exc:
        logger.error(f"Error in inventory task for printer {printer_id}: {exc}", exc_info=True)

        # Повторяем задачу если не достигли лимита
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying inventory task for printer {printer_id}, attempt {self.request.retries + 1}")
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
            return {'success': True, 'message': 'No printers to poll', 'count': 0}

        # Запускаем задачи для каждого принтера
        task_ids = []
        skipped_count = 0

        for printer in printers:
            # Проверяем, не был ли принтер недавно опрошен
            recent_cache_key = f'inventory_recent_{printer.id}'
            if cache.get(recent_cache_key):
                skipped_count += 1
                logger.debug(f"Skipping printer {printer.ip_address} - recently polled")
                continue

            # Проверяем, не запущена ли уже задача для этого принтера
            cache_key = f'inventory_task_{printer.id}'
            if not cache.get(cache_key):
                # Используем обычную (низкоприоритетную) задачу
                task = run_inventory_task.apply_async(
                    args=[printer.id],
                    priority=1  # Низкий приоритет
                )
                task_ids.append(task.id)
                logger.debug(f"Queued inventory task {task.id} for printer {printer.ip_address}")
            else:
                skipped_count += 1
                logger.debug(f"Skipping printer {printer.ip_address} - task already running")

        logger.info(f"Queued {len(task_ids)} inventory tasks, skipped {skipped_count}")

        return {
            'success': True,
            'message': f'Queued {len(task_ids)} inventory tasks',
            'task_ids': task_ids,
            'total_printers': printers.count(),
            'skipped': skipped_count,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"Error in inventory daemon task: {exc}", exc_info=True)
        return {
            'success': False,
            'error': str(exc),
            'timestamp': timezone.now().isoformat(),
        }


# Остальные задачи остаются без изменений...
@shared_task
def cleanup_old_inventory_data():
    """
    Задача для очистки старых данных инвентаризации.
    """
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


@shared_task
def cache_printer_statistics():
    """
    Задача для кэширования статистики принтеров.
    """
    try:
        from django.db.models import Count, Q

        # Собираем статистику
        total_printers = Printer.objects.count()

        # Статистика по последним опросам
        from datetime import timedelta
        recent_cutoff = timezone.now() - timedelta(hours=24)

        recent_success = InventoryTask.objects.filter(
            task_timestamp__gte=recent_cutoff,
            status='SUCCESS'
        ).values('printer').distinct().count()

        recent_failed = InventoryTask.objects.filter(
            task_timestamp__gte=recent_cutoff,
            status__in=['FAILED', 'VALIDATION_ERROR']
        ).values('printer').distinct().count()

        # Статистика по правилам сопоставления
        match_rules_stats = Printer.objects.values('last_match_rule').annotate(
            count=Count('id')
        ).order_by('last_match_rule')

        # Статистика по организациям
        org_stats = Printer.objects.filter(
            organization__isnull=False
        ).values('organization__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        stats = {
            'total_printers': total_printers,
            'recent_success': recent_success,
            'recent_failed': recent_failed,
            'success_rate': round((recent_success / total_printers * 100) if total_printers > 0 else 0, 1),
            'match_rules': {item['last_match_rule'] or 'NONE': item['count'] for item in match_rules_stats},
            'top_organizations': list(org_stats),
            'updated_at': timezone.now().isoformat(),
        }

        # Кэшируем на 1 час
        cache.set('printer_statistics', stats, timeout=60 * 60)

        logger.info(f"Cached printer statistics: {total_printers} total, {recent_success} recent success")

        return {'success': True, 'stats': stats}

    except Exception as exc:
        logger.error(f"Error caching printer statistics: {exc}", exc_info=True)
        return {'success': False, 'error': str(exc)}


@shared_task
def send_inventory_notification(printer_id: int, status: str, message: str = None):
    """
    Задача для отправки WebSocket уведомлений об инвентаризации.
    """
    try:
        channel_layer = get_channel_layer()

        notification = {
            'type': 'inventory_update',
            'printer_id': printer_id,
            'status': status,
            'message': message,
            'timestamp': timezone.now().isoformat(),
        }

        async_to_sync(channel_layer.group_send)(
            'inventory_updates',
            notification
        )

        return {'success': True, 'notification_sent': True}

    except Exception as exc:
        logger.error(f"Error sending inventory notification: {exc}", exc_info=True)
        return {'success': False, 'error': str(exc)}