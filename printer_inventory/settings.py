import os
import platform
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# БАЗА
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "REPLACE_ME_WITH_SECURE_KEY")
DEBUG = os.getenv("DEBUG", "False").strip().lower() == "true"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

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

CELERY_TASK_ROUTES = {
    'inventory.tasks.run_inventory_task': {'queue': 'inventory'},
    'inventory.tasks.inventory_daemon_task': {'queue': 'daemon'},
}

CELERY_BEAT_SCHEDULE = {
    'inventory-daemon': {
        'task': 'inventory.tasks.inventory_daemon_task',
        'schedule': 60.0 * int(os.getenv("POLL_INTERVAL_MINUTES", "60")),
    },
}

CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'default': {'exchange': 'default', 'routing_key': 'default'},
    'inventory': {'exchange': 'inventory', 'routing_key': 'inventory'},
    'daemon': {'exchange': 'daemon', 'routing_key': 'daemon'},
}

# ──────────────────────────────────────────────────────────────────────────────
# I18N / STATIC
# ──────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'ru'
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Irkutsk')
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}', 'style': '{'},
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
        'file': {'class': 'logging.FileHandler', 'filename': LOGS_DIR / 'django.log', 'formatter': 'verbose'},
        'error_file': {'class': 'logging.FileHandler', 'filename': LOGS_DIR / 'errors.log', 'formatter': 'verbose', 'level': 'ERROR'},
        'redis_file': {'class': 'logging.FileHandler', 'filename': LOGS_DIR / 'redis.log', 'formatter': 'verbose'},
        'celery_file': {'class': 'logging.FileHandler', 'filename': LOGS_DIR / 'celery.log', 'formatter': 'verbose'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['error_file'], 'level': 'ERROR', 'propagate': False},
        'printer_inventory': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        'redis': {'handlers': ['redis_file'], 'level': 'INFO', 'propagate': False},
        'celery': {'handlers': ['celery_file', 'console'], 'level': 'INFO', 'propagate': False},
        'inventory.tasks': {'handlers': ['celery_file', 'console'], 'level': 'INFO', 'propagate': False},
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
OIDC_RP_SCOPES = 'openid profile email'
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60
OIDC_TOKEN_USE_BASIC_AUTH = False
OIDC_DEFAULT_GROUPS = ['Наблюдатель']

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
