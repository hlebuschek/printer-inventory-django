import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "REPLACE_ME_WITH_SECURE_KEY")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
CSRF_FAILURE_VIEW = 'printer_inventory.errors.custom_csrf_failure'

# Базовые URL из переменных окружения
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
KEYCLOAK_SERVER_URL = os.getenv('KEYCLOAK_SERVER_URL', 'http://localhost:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'printer-inventory')

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

# GLPI settings
GLPI_PATH = r"C:\Program Files\GLPI-Agent"
HTTP_CHECK = True
POLL_INTERVAL_MINUTES = 60