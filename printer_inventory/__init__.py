# Импортируем Celery app для автоматического обнаружения задач
from .celery import app as celery_app

__all__ = ('celery_app',)