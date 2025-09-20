import os
from celery import Celery
from django.conf import settings

# Устанавливаем переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')

# Создаем экземпляр Celery
app = Celery('printer_inventory')

# Используем настройки Django с префиксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически обнаруживаем задачи в приложениях Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Настройки Celery
app.conf.update(
    # Таймауты
    task_soft_time_limit=60 * 10,  # 10 минут soft limit
    task_time_limit=60 * 15,  # 15 минут hard limit

    # Retry настройки
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Prefetch настройки для лучшей производительности
    worker_prefetch_multiplier=1,

    # Мониторинг
    task_send_sent_event=True,
    task_track_started=True,

    # Результаты задач
    result_expires=60 * 60 * 24,  # 24 часа

    # Beat настройки
    beat_schedule_filename='celerybeat-schedule',

    # Логирование
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)


# Для отладки
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# Подключение к Redis при старте
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Настройка периодических задач"""
    # Проверка соединения с Redis
    sender.add_periodic_task(
        60.0 * 5,  # каждые 5 минут
        check_redis_connection.s(),
        name='check redis connection'
    )


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
        return {'status': 'error', 'redis': f'error: {str(e)}'}