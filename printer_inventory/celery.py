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

# ИСПРАВЛЕНИЕ 1: Принудительный импорт Django перед автообнаружением
import django
django.setup()

# ИСПРАВЛЕНИЕ 2: Явное автообнаружение с дебагом
def custom_autodiscover_tasks():
    """Кастомная функция автообнаружения с логированием"""
    logger = logging.getLogger(__name__)
    
    # Список приложений для поиска задач
    app_names = [
        'inventory',
        'contracts', 
        'monthly_report',
        'access'
    ]
    
    # Добавляем все приложения из INSTALLED_APPS
    if hasattr(settings, 'INSTALLED_APPS'):
        app_names.extend(settings.INSTALLED_APPS)
    
    # Убираем дубликаты
    app_names = list(set(app_names))
    
    logger.info(f"Searching for tasks in apps: {app_names}")
    
    # Пытаемся импортировать задачи из каждого приложения
    discovered_tasks = []
    for app_name in app_names:
        try:
            # Пытаемся импортировать модуль tasks
            tasks_module = f"{app_name}.tasks"
            __import__(tasks_module)
            discovered_tasks.append(tasks_module)
            logger.info(f"✅ Found tasks in {tasks_module}")
        except ImportError as e:
            # Это нормально - не все приложения имеют tasks.py
            if 'inventory.tasks' in str(e):
                logger.error(f"❌ Critical: Failed to import inventory.tasks: {e}")
            continue
        except Exception as e:
            logger.error(f"❌ Error importing {tasks_module}: {e}")
    
    logger.info(f"Total discovered task modules: {discovered_tasks}")
    return app_names

# Запускаем кастомное автообнаружение
discovered_apps = custom_autodiscover_tasks()
app.autodiscover_tasks(lambda: discovered_apps)

# ИСПРАВЛЕНИЕ 3: Принудительный импорт критических задач
try:
    from inventory.tasks import inventory_daemon_task, run_inventory_task
    logging.getLogger(__name__).info("✅ Critical inventory tasks imported successfully")
except Exception as e:
    logging.getLogger(__name__).error(f"❌ CRITICAL: Cannot import inventory tasks: {e}")

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
    beat_schedule_filename='celerybeat-schedule.db',

    # Логирование
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# Логгер для отладки
logger = logging.getLogger(__name__)

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Настройка периодических задач"""
    logger.info("Setting up periodic tasks...")
    
    # Проверяем, что задачи доступны
    try:
        from inventory.tasks import inventory_daemon_task
        logger.info("✅ inventory_daemon_task найдена для периодических задач")
    except ImportError as e:
        logger.error(f"❌ Не удалось импортировать inventory_daemon_task: {e}")
    
    # Добавляем задачу проверки Redis (каждые 5 минут)
    sender.add_periodic_task(
        60.0 * 5,
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
        return {'status': 'ok', 'redis': 'connected'} if result == 'ok' else {'status': 'error', 'redis': 'disconnected'}
    except Exception as e:
        return {'status': 'error', 'redis': f'error: {str(e)}'}

# Для отладки
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# ИСПРАВЛЕНИЕ 4: Детальная диагностика при финализации
@app.on_after_finalize.connect
def debug_tasks(sender, **kwargs):
    """Отладочная информация о зарегистрированных задачах"""
    logger.info("=== Registered Celery Tasks ===")
    
    # Показываем все зарегистрированные задачи
    all_tasks = sorted(sender.tasks.keys())
    logger.info(f"Total registered tasks: {len(all_tasks)}")
    
    inventory_tasks = [t for t in all_tasks if 'inventory' in t]
    logger.info(f"Inventory tasks found: {len(inventory_tasks)}")
    
    for task_name in all_tasks:
        prefix = "📋" if 'inventory' in task_name else "📄"
        logger.info(f"  {prefix} {task_name}")
    
    # Проверяем конфигурацию beat
    beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
    logger.info(f"=== Beat Schedule ({len(beat_schedule)} tasks) ===")
    for name, config in beat_schedule.items():
        task_name = config.get('task', 'Unknown')
        schedule = config.get('schedule', 'Unknown')
        registered = "✅" if task_name in sender.tasks else "❌"
        logger.info(f"  {registered} {name}: {task_name} every {schedule}s")
    
    # Критическая проверка inventory задач
    required_tasks = [
        'inventory.tasks.inventory_daemon_task',
        'inventory.tasks.run_inventory_task'
    ]
    
    missing_tasks = [t for t in required_tasks if t not in sender.tasks]
    if missing_tasks:
        logger.error("❌ CRITICAL: Missing required tasks:")
        for task in missing_tasks:
            logger.error(f"     {task}")
        logger.error("Inventory automation will NOT work!")
    else:
        logger.info("✅ All required inventory tasks are registered")
