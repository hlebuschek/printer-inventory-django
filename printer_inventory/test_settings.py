"""Настройки для запуска тестов.

In-memory SQLite + локальные кэши/брокеры, чтобы прогон не зависел от
PostgreSQL/Redis и реальных кредов.

Запуск:
    DJANGO_SETTINGS_MODULE=printer_inventory.test_settings python manage.py test
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


# Часть миграций содержит Postgres-специфичный RunSQL (DO-блоки), несовместимый
# с SQLite. Отключаем миграции в тестах — схема создаётся напрямую из моделей.
class _DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _DisableMigrations()

# Быстрые хэши паролей для тестов.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Кэш и сессии — локальная память вместо Redis.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "sessions": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "inventory": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Channels — in-memory слой.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Celery — синхронное выполнение задач.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
