import os
import platform
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from kombu import Queue, Exchange
from celery.schedules import crontab

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# БАЗА
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "REPLACE_ME_WITH_SECURE_KEY")
DEBUG = os.getenv("DEBUG", "False").strip().lower() == "true"

# Определяем окружение (production использует HTTPS)
USE_HTTPS = os.getenv("USE_HTTPS", "False").strip().lower() == "true"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# CSRF настройки (из переменных окружения)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:8000,https://localhost:8000"
    ).split(",")
    if origin.strip()
]

# Настройки для HTTPS (только для production)
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True  # Только через HTTPS
    CSRF_COOKIE_SECURE = True     # Только через HTTPS
    CSRF_COOKIE_HTTPONLY = False  # Должно быть False для работы с JavaScript
    SESSION_COOKIE_HTTPONLY = True
else:
    # Для development (HTTP)
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False
    SESSION_COOKIE_HTTPONLY = True

CSRF_FAILURE_VIEW = 'printer_inventory.errors.custom_csrf_failure'

# Базовые URL / Keycloak
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')
KEYCLOAK_SERVER_URL = os.getenv('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'printer-inventory')

# ──────────────────────────────────────────────────────────────────────────────
# REDIS (общая часть)
# ──────────────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

def _build_redis_url(host: str, port: int, db: int = 0, password: str | None = None) -> str:
    if password:
        return f"redis://:{quote(password)}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"

REDIS_URL = _build_redis_url(REDIS_HOST, REDIS_PORT, 0, REDIS_PASSWORD or None)
REDIS_CHANNEL_URL = _build_redis_url(REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD or None)

# ──────────────────────────────────────────────────────────────────────────────
# APPS / MIDDLEWARE
# ──────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'channels',
    'mozilla_django_oidc',

    # Project
    'inventory.apps.InventoryConfig',
    'contracts',
    'access',
    'monthly_report.apps.MonthlyReportConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

# Добавляем WhiteNoise только в production
if not DEBUG:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE += [
    'printer_inventory.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mozilla_django_oidc.middleware.SessionRefresh',
    'access.middleware.AppAccessMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'printer_inventory.auth_backends.CustomOIDCAuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'printer_inventory.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'printer_inventory.wsgi.application'
ASGI_APPLICATION = 'printer_inventory.asgi.application'

# ──────────────────────────────────────────────────────────────────────────────
# CHANNELS / REDIS (без ключа "password" в CONFIG!)
# ──────────────────────────────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_CHANNEL_URL],  # пароль вшит в URL при необходимости
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

# Фоллбэк на InMemory, если Redis недоступен
try:
    import redis as _redis_check  # noqa
    _rc = _redis_check.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD or None,
        socket_connect_timeout=0.3,
    )
    _rc.ping()
except Exception:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ──────────────────────────────────────────────────────────────────────────────
# DATABASES
# ──────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME", "printer_inventory"),
        'USER': os.getenv("DB_USER", "postgres"),
        'PASSWORD': os.getenv("DB_PASSWORD", ""),
        'HOST': os.getenv("DB_HOST", "localhost"),
        'PORT': os.getenv("DB_PORT", "5432"),
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# CACHES (обязательно есть алиас 'sessions')
# ──────────────────────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_url(REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD or None),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'CONNECTION_POOL_KWARGS': {'max_connections': 50, 'retry_on_timeout': True},
            'SERIALIZER': 'django_redis.serializers.pickle.PickleSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        },
        'KEY_PREFIX': 'printer_inventory',
        'VERSION': 1,
        'TIMEOUT': 60 * 15,
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_url(REDIS_HOST, REDIS_PORT, REDIS_DB + 1, REDIS_PASSWORD or None),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'sessions',
        'TIMEOUT': 60 * 60 * 24 * 7,
    },
    'inventory': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': _build_redis_url(REDIS_HOST, REDIS_PORT, REDIS_DB + 2, REDIS_PASSWORD or None),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'inventory_cache',
        'TIMEOUT': 60 * 30,
    },
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
SESSION_SAVE_EVERY_REQUEST = True

# ──────────────────────────────────────────────────────────────────────────────
# CELERY
# ──────────────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = _build_redis_url(REDIS_HOST, REDIS_PORT, REDIS_DB + 3, REDIS_PASSWORD or None)
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = os.getenv('CELERY_TIMEZONE', 'Asia/Irkutsk')
CELERY_ENABLE_UTC = True

# Настройки очередей с приоритетами
CELERY_TASK_DEFAULT_QUEUE = 'low_priority'

# Определяем exchanges
default_exchange = Exchange('default', type='direct')
priority_exchange = Exchange('priority', type='direct')

CELERY_TASK_ROUTES = {
    # Пользовательские задачи - высокий приоритет
    'inventory.tasks.run_inventory_task_priority': {'queue': 'high_priority'},

    # Периодические задачи - низкий приоритет
    'inventory.tasks.run_inventory_task': {'queue': 'low_priority'},

    # Демон
    'inventory.tasks.inventory_daemon_task': {'queue': 'daemon'},
}

# settings.py

CELERY_BEAT_SCHEDULE = {
    'inventory-daemon-every-hour': {
        'task': 'inventory.tasks.inventory_daemon_task',
        'schedule': crontab(minute=0),  # Каждый час
        'options': {
            'queue': 'daemon',
            'priority': 5
        }
    },
    'cleanup-old-data-daily': {
        'task': 'inventory.tasks.cleanup_old_inventory_data',
        'schedule': crontab(hour=3, minute=0),  # 03:00 каждый день
        'options': {
            'queue': 'low_priority',
            'priority': 1
        }
    },
}

# ===== ОПРЕДЕЛЕНИЕ ОЧЕРЕДЕЙ =====
CELERY_TASK_QUEUES = (
    # Высокий приоритет - для пользовательских запросов
    Queue('high_priority',
          exchange=priority_exchange,
          routing_key='high',
          queue_arguments={'x-max-priority': 10}),

    # Низкий приоритет - для периодических задач
    Queue('low_priority',
          exchange=default_exchange,
          routing_key='low',
          queue_arguments={'x-max-priority': 10}),

    # Отдельная очередь для демона
    Queue('daemon',
          exchange=default_exchange,
          routing_key='daemon'),
)

CELERY_TASK_ANNOTATIONS = {
    'inventory.tasks.run_inventory_task_priority': {
        'rate_limit': '30/m',  # Максимум 30 пользовательских запросов в минуту
        'time_limit': 300,      # 5 минут максимум
    },
    'inventory.tasks.run_inventory_task': {
        'rate_limit': '100/m',  # 100 фоновых задач в минуту
        'time_limit': 600,      # 10 минут максимум
    },
}
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# ──────────────────────────────────────────────────────────────────────────────
# I18N / STATIC
# ──────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'ru'
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Irkutsk')
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Папка со статикой в исходниках
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Куда собирать для production
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATIC_URL = '/static/'

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING (оптимизированное для Celery)
# ──────────────────────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'celery_compact': {
            'format': '{asctime} [{levelname}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'WARNING',  # Только WARNING и выше в консоль
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 3,
            'level': 'INFO',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'formatter': 'verbose',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'level': 'ERROR',
        },
        'redis_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'redis.log',
            'formatter': 'verbose',
            'maxBytes': 5 * 1024 * 1024,  # 5 MB
            'backupCount': 2,
            'level': 'WARNING',  # Только WARNING и выше
        },
        'celery_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'celery.log',
            'formatter': 'celery_compact',
            'maxBytes': 20 * 1024 * 1024,  # 20 MB
            'backupCount': 3,
            'level': 'WARNING',  # ВАЖНО: только WARNING и выше
        },
        'celery_errors': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'celery_errors.log',
            'formatter': 'verbose',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 3,
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'printer_inventory': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'redis': {
            'handlers': ['redis_file'],
            'level': 'WARNING',  # Только WARNING и выше
            'propagate': False,
        },
        # ===== ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ CELERY =====
        'celery': {
            'handlers': ['celery_file', 'celery_errors'],
            'level': 'WARNING',  # Только WARNING и выше
            'propagate': False,
        },
        'celery.worker': {
            'handlers': ['celery_file', 'celery_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['celery_file', 'celery_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery.beat': {
            'handlers': ['celery_file', 'celery_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
        'inventory.tasks': {
            'handlers': ['celery_file', 'celery_errors'],
            'level': 'WARNING',  # Логируем только проблемы
            'propagate': False,
        },
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# OIDC / KEYCLOAK
# ──────────────────────────────────────────────────────────────────────────────
OIDC_RP_CLIENT_ID = os.getenv('OIDC_CLIENT_ID', '')
OIDC_RP_CLIENT_SECRET = os.getenv('OIDC_CLIENT_SECRET', '')
OIDC_OP_AUTHORIZATION_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth'
OIDC_OP_TOKEN_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token'
OIDC_OP_USER_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo'
OIDC_OP_JWKS_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs'

OIDC_RP_SIGN_ALGO = 'RS256'
OIDC_RP_SCOPES = 'openid profile email roles'
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60
OIDC_TOKEN_USE_BASIC_AUTH = False
OIDC_DEFAULT_GROUPS = ['Наблюдатель']

# Отключение проверки SSL для development (может понадобиться для локального Keycloak)
OIDC_VERIFY_SSL = os.getenv('OIDC_VERIFY_SSL', 'True').strip().lower() == 'true'

OIDC_RP_POST_LOGOUT_REDIRECT_URI = f'{BASE_URL}/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

APP_ACCESS_RULES = {
    "inventory": "inventory.access_inventory_app",
    "contracts": "contracts.access_contracts_app",
}

# ──────────────────────────────────────────────────────────────────────────────
# GLPI — КРОССПЛАТФОРМЕННО
# ──────────────────────────────────────────────────────────────────────────────
def _get_default_glpi_path() -> str:
    """
    Возвращает каталог, где лежат glpi-netinventory / glpi-netdiscovery.
    """
    sysname = platform.system().lower()

    if sysname == 'windows':
        candidates = [
            r"C:\Program Files\GLPI-Agent",
            r"C:\Program Files (x86)\GLPI-Agent",
            r"C:\GLPI-Agent",
        ]
        for p in candidates:
            if os.path.isdir(p):
                return p
        return r"C:\Program Files\GLPI-Agent"

    if sysname == 'linux':
        candidates = ["/usr/bin", "/usr/local/bin", "/opt/glpi-agent/bin", "/snap/bin"]
        for p in candidates:
            if os.path.exists(os.path.join(p, "glpi-netinventory")):
                return p
        return "/usr/bin"

    if sysname == 'darwin':  # macOS
        candidates = [
            "/Applications/GLPI-Agent/bin",                      # pkg
            "/Applications/GLPI-Agent.app/Contents/MacOS",       # внутри .app
            "/opt/homebrew/bin",                                 # Homebrew (ARM)
            "/usr/local/bin",                                    # Homebrew (Intel) / make install
            "/usr/bin",
        ]
        for p in candidates:
            if os.path.exists(os.path.join(p, "glpi-netinventory")):
                return p
        return "/Applications/GLPI-Agent/bin"

    raise RuntimeError(f"Неподдерживаемая ОС: {sysname}")

GLPI_PATH = os.getenv("GLPI_PATH", _get_default_glpi_path())
GLPI_PLATFORM = platform.system().lower()

if GLPI_PLATFORM in ('linux', 'darwin'):
    GLPI_USER = os.getenv("GLPI_USER", "").strip()
    GLPI_USE_SUDO = os.getenv("GLPI_USE_SUDO", "False").strip().lower() == "true"
else:
    GLPI_USER = ""
    GLPI_USE_SUDO = False

HTTP_CHECK = os.getenv("HTTP_CHECK", "True").strip().lower() == "true"
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "60"))

# Доп. диагностический флаг
REDIS_STATS_ENABLED = DEBUG

EDGEDRIVER_PATH = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'