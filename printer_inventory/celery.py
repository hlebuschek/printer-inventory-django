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

# Импорт Django перед автообнаружением
import django
django.setup()

# Автообнаружение задач
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# ===== ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ =====
app.conf.update(
    # Таймауты
    task_soft_time_limit=60 * 10,  # 10 минут soft limit
    task_time_limit=60 * 15,  # 15 минут hard limit

    # Мониторинг - ОТКЛЮЧАЕМ избыточные события
    task_send_sent_event=False,
    task_track_started=False,
    worker_send_task_events=False,

    # Результаты задач - СОКРАЩЕНО с 24 часов до 1 часа для экономии памяти Redis
    result_expires=60 * 60,  # 1 час (было 24 часа)
    result_extended=False,

    # Игнорировать результаты для периодических задач (экономия памяти)
    task_ignore_result=False,  # По умолчанию сохраняем результаты

    # Beat настройки
    beat_schedule_filename='celerybeat-schedule.db',

    # Логирование
    worker_hijack_root_logger=False,
    worker_log_format='[%(levelname)s] %(message)s',
    worker_task_log_format='[%(levelname)s][%(task_name)s] %(message)s',
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level='WARNING',
)

logger = logging.getLogger(__name__)


@app.task
def check_redis_connection():
    """Проверка соединения с Redis"""
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 30)
        result = cache.get('health_check')
        return {'status': 'ok', 'redis': 'connected'} if result == 'ok' else {
            'status': 'error',
            'redis': 'disconnected'
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {'status': 'error', 'redis': f'error: {str(e)}'}


@app.task(bind=True)
def debug_task(self):
    """Отладочная задача"""
    return f'Request: {self.request!r}'


@app.on_after_finalize.connect
def debug_tasks(sender, **kwargs):
    """Отладочная информация о зарегистрированных задачах"""
    if settings.DEBUG:
        logger.info("=== Celery Configuration ===")
        all_tasks = sorted(sender.tasks.keys())
        inventory_tasks = [t for t in all_tasks if 'inventory' in t]
        logger.info(f"Total tasks: {len(all_tasks)}, Inventory: {len(inventory_tasks)}")

        # Проверяем beat schedule
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        if beat_schedule:
            logger.info(f"Beat schedule: {len(beat_schedule)} periodic tasks")
            for task_name, task_config in beat_schedule.items():
                logger.info(f"  - {task_name}: {task_config['task']}")

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


# Явный импорт задач для гарантированной регистрации
try:
    from integrations.tasks import export_monthly_report_to_glpi  # noqa: F401
    logger.info("✓ Explicitly imported integrations.tasks")
except ImportError as e:
    logger.error(f"Failed to import integrations.tasks: {e}")