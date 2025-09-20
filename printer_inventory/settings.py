import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "REPLACE_ME_WITH_SECURE_KEY")
DEBUG = "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CSRF_FAILURE_VIEW = 'printer_inventory.errors.custom_csrf_failure'

# Базовые URL из переменных окружения
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
KEYCLOAK_SERVER_URL = os.getenv('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'printer-inventory')

# Redis настройки
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Формируем Redis URL
REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}" if REDIS_PASSWORD else f"redis://{REDIS_HOST}:{REDIS_PORT}"

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'inventory.apps.InventoryConfig',
    "contracts",
    "access",
    "monthly_report.apps.MonthlyReportConfig",
    'mozilla_django_oidc',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

# OIDC/Keycloak settings
OIDC_RP_CLIENT_ID = os.getenv('OIDC_CLIENT_ID', '')
OIDC_RP_CLIENT_SECRET = os.getenv('OIDC_CLIENT_SECRET', '')
OIDC_OP_AUTHORIZATION_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth'
OIDC_OP_TOKEN_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token'
OIDC_OP_USER_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo'
OIDC_OP_JWKS_ENDPOINT = f'{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs'

# Дополнительные настройки OIDC
OIDC_RP_SIGN_ALGO = 'RS256'
OIDC_RP_SCOPES = 'openid profile email'

# Настройки сессии для Keycloak
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60  # 15 минут
OIDC_TOKEN_USE_BASIC_AUTH = False

# Кастомные настройки для нашего backend
OIDC_DEFAULT_GROUPS = ['Наблюдатель']

# OIDC настройки с динамическими URL
OIDC_RP_POST_LOGOUT_REDIRECT_URI = f'{BASE_URL}/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

APP_ACCESS_RULES = {
    "inventory": "inventory.access_inventory_app",
    "contracts": "contracts.access_contracts_app",
}

ROOT_URLCONF = 'printer_inventory.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [ BASE_DIR / "templates" ],
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

# Redis Channel Layer для WebSocket
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "password": REDIS_PASSWORD if REDIS_PASSWORD else None,
            "capacity": 1500,  # Максимум сообщений в канале
            "expiry": 60,      # Время жизни сообщений в секундах
        },
    },
}

# Если Redis недоступен, fallback на InMemory
if not DEBUG:
    try:
        import redis
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, password=REDIS_PASSWORD or None)
        redis_client.ping()
    except Exception:
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels.layers.InMemoryChannelLayer',
            },
        }

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

# Кэширование с Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/{REDIS_DB}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,  # Не падать если Redis недоступен
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SERIALIZER': 'django_redis.serializers.pickle.PickleSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        },
        'KEY_PREFIX': 'printer_inventory',
        'VERSION': 1,
        'TIMEOUT': 60 * 15,  # 15 минут по умолчанию
    },
    # Отдельный кэш для сессий
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/{REDIS_DB + 1}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'sessions',
        'TIMEOUT': 60 * 60 * 24 * 7,  # 7 дней
    },
    # Кэш для инвентаризации
    'inventory': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/{REDIS_DB + 2}',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'inventory_cache',
        'TIMEOUT': 60 * 30,  # 30 минут
    }
}

# Использовать Redis для сессий
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 дней
SESSION_SAVE_EVERY_REQUEST = True

# Celery настройки
CELERY_BROKER_URL = f'{REDIS_URL}/{REDIS_DB + 3}'
CELERY_RESULT_BACKEND = f'{REDIS_URL}/{REDIS_DB + 3}'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Irkutsk'
CELERY_ENABLE_UTC = True

# Настройки задач Celery
CELERY_TASK_ROUTES = {
    'inventory.tasks.run_inventory_task': {'queue': 'inventory'},
    'inventory.tasks.inventory_daemon_task': {'queue': 'daemon'},
}

CELERY_BEAT_SCHEDULE = {
    'inventory-daemon': {
        'task': 'inventory.tasks.inventory_daemon_task',
        'schedule': 60.0 * int(os.getenv("POLL_INTERVAL_MINUTES", "60")),  # Каждые N минут
    },
}

# Настройки очередей Celery
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'inventory': {
        'exchange': 'inventory',
        'routing_key': 'inventory',
    },
    'daemon': {
        'exchange': 'daemon',
        'routing_key': 'daemon',
    },
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Irkutsk'
USE_I18N = True
USE_L10N = True
USE_TZ = True

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Создаём директорию для логов
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Логирование с учетом Redis
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
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
        },
        'error_file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'formatter': 'verbose',
            'level': 'ERROR',
        },
        'redis_file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'redis.log',
            'formatter': 'verbose',
        },
        'celery_file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'celery.log',
            'formatter': 'verbose',
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
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'inventory.tasks': {
            'handlers': ['celery_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# GLPI settings
GLPI_PATH = r"C:\Program Files\GLPI-Agent"
HTTP_CHECK = True
POLL_INTERVAL_MINUTES = 60

# Redis monitoring
REDIS_STATS_ENABLED = DEBUG