from django.apps import AppConfig
class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    def ready(self):
        # Убираем устаревший start_scheduler() - теперь используем Celery Beat
        # from .services import start_scheduler
        # start_scheduler()
        # Импортируем задачи для регистрации в Celery
        try:
            from . import tasks  # noqa
        except ImportError:
            pass