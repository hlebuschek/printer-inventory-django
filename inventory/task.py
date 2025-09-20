import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Printer, InventoryTask
from .services import run_inventory_for_printer

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_inventory_task(self, printer_id: int, xml_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Асинхронная задача для опроса одного принтера.

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
            }

            # Кэшируем результат
            cache.set(f'last_inventory_{printer_id}', result, timeout=60 * 60 * 24)  # 24 часа

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
        }


@shared_task(bind=True)
def inventory_daemon_task(self):
    """
    Периодическая задача для опроса всех принтеров.
    Заменяет APScheduler демон.
    """
    logger.info("Starting inventory daemon task")

    try:
        printers = Printer.objects.all()
        logger.info(f"Found {printers.count()} printers for inventory")

        if not printers.exists():
            return {'success': True, 'message': 'No printers to poll', 'count': 0}

        # Запускаем задачи для каждого принтера
        task_ids = []
        for printer in printers:
            # Проверяем, не запущена ли уже задача для этого принтера
            cache_key = f'inventory_task_{printer.id}'
            if not cache.get(cache_key):
                task = run_inventory_task.delay(printer.id)
                task_ids.append(task.id)
                logger.debug(f"Queued inventory task {task.id} for printer {printer.ip_address}")

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
    """
    Задача для очистки старых данных инвентаризации.
    """
    try:
        from django.utils import timezone
        from datetime import timedelta

        # Удаляем задачи старше 90 дней
        cutoff_date = timezone.now() - timedelta(days=90)
        old_tasks = InventoryTask.objects.filter(task_timestamp__lt=cutoff_date)
        deleted_count = old_tasks.count()
        old_tasks.delete()

        logger.info(f"Cleaned up {deleted_count} old inventory tasks")

        # Очищаем кэш результатов
        cache_prefix = 'last_inventory_'
        cache.delete_many([f'{cache_prefix}{i}' for i in range(1, 10000)])  # примерно

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
        from django.core.cache import cache

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


@shared_task
def monitor_redis_health():
    """
    Задача для мониторинга состояния Redis.
    """
    try:
        from django.core.cache import cache
        import redis

        # Тестируем основной кэш
        test_key = 'redis_health_check'
        test_value = timezone.now().isoformat()

        cache.set(test_key, test_value, timeout=60)
        retrieved_value = cache.get(test_key)

        # Получаем информацию о Redis
        redis_client = cache._cache.get_client(None)
        redis_info = redis_client.info()

        health_data = {
            'cache_working': retrieved_value == test_value,
            'redis_version': redis_info.get('redis_version'),
            'connected_clients': redis_info.get('connected_clients'),
            'used_memory_human': redis_info.get('used_memory_human'),
            'total_commands_processed': redis_info.get('total_commands_processed'),
            'timestamp': timezone.now().isoformat(),
        }

        # Кэшируем результаты мониторинга
        cache.set('redis_health', health_data, timeout=300)  # 5 минут

        return {'success': True, 'health': health_data}

    except Exception as exc:
        logger.error(f"Error monitoring Redis health: {exc}", exc_info=True)
        return {'success': False, 'error': str(exc)}