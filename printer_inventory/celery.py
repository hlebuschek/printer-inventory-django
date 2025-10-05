import os
from celery import Celery
from django.conf import settings
import logging

# Устанавливаем переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')

# Создаем экземпляр Celery
app = Celery('printer_inventory')

# Используем настройки Django с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автообнаружение задач
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# ===== ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ CELERY =====
app.conf.update(
    # Таймауты
    task_soft_time_limit=60 * 10,  # 10 минут soft limit
    task_time_limit=60 * 15,  # 15 минут hard limit

    # Retry настройки
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Prefetch настройки для лучшей производительности
    worker_prefetch_multiplier=1,

    # Мониторинг - ОТКЛЮЧАЕМ избыточные события
    task_send_sent_event=False,  # Не отправляем событие "отправлено"
    task_track_started=False,  # Не отслеживаем старт задачи
    worker_send_task_events=False,  # Не отправляем события задач

    # Результаты задач
    result_expires=60 * 60 * 24,  # 24 часа
    result_extended=False,  # Не сохраняем расширенную информацию

    # Beat настройки
    beat_schedule_filename='celerybeat-schedule.db',

    # ===== КРИТИЧНО: МИНИМАЛЬНОЕ ЛОГИРОВАНИЕ =====
    worker_hijack_root_logger=False,
    worker_log_format='[%(levelname)s] %(message)s',
    worker_task_log_format='[%(levelname)s][%(task_name)s] %(message)s',

    # Redirect stdout/stderr для уменьшения логов
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level='WARNING',
)

# Настройка логгера Celery
logger = logging.getLogger(__name__)


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Настройка периодических задач"""
    # Только КРИТИЧНЫЕ логи при настройке
    pass


@app.task
def check_redis_connection():
    """Проверка соединения с Redis"""
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 30)
        result = cache.get('health_check')
        return {'status': 'ok', 'redis': 'connected'} if result == 'ok' else {'status': 'error',
                                                                              'redis': 'disconnected'}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {'status': 'error', 'redis': f'error: {str(e)}'}


@app.task(bind=True)
def debug_task(self):
    """Отладочная задача - минимум логов"""
    return f'Request: {self.request!r}'


@app.on_after_finalize.connect
def debug_tasks(sender, **kwargs):
    """Минимальная отладочная информация о зарегистрированных задачах"""
    if settings.DEBUG:
        logger.info("=== Celery Configuration ===")
        all_tasks = sorted(sender.tasks.keys())
        inventory_tasks = [t for t in all_tasks if 'inventory' in t]
        logger.info(f"Total tasks: {len(all_tasks)}, Inventory: {len(inventory_tasks)}")

        # Проверяем beat schedule
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        if beat_schedule:
            logger.info(f"Beat schedule: {len(beat_schedule)} periodic tasks")

        # Критическая проверка inventory задач
        required_tasks = [
            'inventory.tasks.inventory_daemon_task',
            'inventory.tasks.run_inventory_task'
        ]

        missing_tasks = [t for t in required_tasks if t not in sender.tasks]
        if missing_tasks:
            logger.error(f"CRITICAL: Missing tasks: {missing_tasks}")
        else:
            logger.info("✓ All required inventory tasks registered")