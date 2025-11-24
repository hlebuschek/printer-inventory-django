"""
Locust Load Testing для Printer Inventory Django

Этот файл содержит сценарии нагрузочного тестирования для веб-приложения
управления инвентаризацией принтеров.

Использование:
    # Запуск с веб-интерфейсом
    locust -f locustfile.py --host=http://localhost:8000

    # Запуск без веб-интерфейса (headless)
    locust -f locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 2 --run-time 1m --headless

    # Выбор конкретного класса пользователей
    locust -f locustfile.py --host=http://localhost:8000 DjangoAuthUser
"""

import os
import logging
from locust import HttpUser, TaskSet, task, between, events
from locust.exception import StopUser
from tests.locust.tasks.auth_tasks import DjangoAuthMixin, KeycloakAuthMixin
from tests.locust.tasks.inventory_tasks import InventoryTaskSet
from tests.locust.tasks.api_tasks import APITaskSet
from tests.locust.tasks.contract_tasks import ContractTaskSet
from tests.locust.tasks.report_tasks import ReportTaskSet

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# ПОЛЬЗОВАТЕЛЬ С АВТОРИЗАЦИЕЙ ЧЕРЕЗ DJANGO
# ============================================================================

class DjangoAuthUser(DjangoAuthMixin, HttpUser):
    """
    Пользователь, авторизующийся через стандартную Django форму.

    Для работы этого пользователя нужно создать тестового пользователя:
        python manage.py shell
        >>> from django.contrib.auth.models import User
        >>> from access.models import AllowedUser
        >>> user = User.objects.create_user('locust_test', password='locust_password_123')
        >>> AllowedUser.objects.create(username='locust_test', is_active=True)
    """

    wait_time = between(1, 3)  # Пауза между задачами: 1-3 секунды

    # Учетные данные для авторизации (можно переопределить через environment)
    username = os.getenv('LOCUST_DJANGO_USER', 'locust_test')
    password = os.getenv('LOCUST_DJANGO_PASSWORD', 'locust_password_123')

    tasks = {
        InventoryTaskSet: 5,  # 50% времени на работу с инвентарем
        APITaskSet: 3,        # 30% времени на API запросы
        ContractTaskSet: 1,   # 10% времени на контракты
        ReportTaskSet: 1,     # 10% времени на отчеты
    }

    def on_start(self):
        """Выполняется при создании пользователя - выполняем вход"""
        logger.info(f"Starting Django auth user: {self.username}")
        self.login()


# ============================================================================
# ПОЛЬЗОВАТЕЛЬ С АВТОРИЗАЦИЕЙ ЧЕРЕЗ KEYCLOAK
# ============================================================================

class KeycloakAuthUser(KeycloakAuthMixin, HttpUser):
    """
    Пользователь, авторизующийся через Keycloak OIDC.

    Требования:
    1. Keycloak должен быть запущен (docker-compose up keycloak)
    2. Пользователь должен существовать в Keycloak realm
    3. Пользователь должен быть в белом списке AllowedUser

    Создание тестового пользователя в whitelist:
        python manage.py shell
        >>> from access.models import AllowedUser
        >>> AllowedUser.objects.create(username='user', is_active=True)
    """

    wait_time = between(2, 5)  # Пауза между задачами: 2-5 секунд

    # Учетные данные Keycloak (можно переопределить через environment)
    keycloak_username = os.getenv('LOCUST_KEYCLOAK_USER', 'user')
    keycloak_password = os.getenv('LOCUST_KEYCLOAK_PASSWORD', '12345678')

    tasks = {
        InventoryTaskSet: 5,  # 50% времени
        APITaskSet: 3,        # 30% времени
        ContractTaskSet: 1,   # 10% времени
        ReportTaskSet: 1,     # 10% времени
    }

    def on_start(self):
        """Выполняется при создании пользователя - выполняем вход через Keycloak"""
        logger.info(f"Starting Keycloak auth user: {self.keycloak_username}")
        self.login()


# ============================================================================
# АНОНИМНЫЙ ПОЛЬЗОВАТЕЛЬ (только публичные страницы)
# ============================================================================

class AnonymousUser(HttpUser):
    """
    Анонимный пользователь, тестирующий только публичные страницы
    (например, страницы входа, статические ресурсы)
    """

    wait_time = between(3, 7)

    @task(10)
    def visit_login_page(self):
        """Посещение страницы выбора способа входа"""
        with self.client.get("/accounts/login/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(5)
    def visit_django_login_page(self):
        """Посещение страницы Django логина"""
        self.client.get("/accounts/django-login/")

    @task(1)
    def load_static_resources(self):
        """Загрузка статических ресурсов"""
        self.client.get("/static/css/vendor/bootstrap.min.css", name="/static/css/[css]")
        self.client.get("/static/js/vendor/alpine.min.js", name="/static/js/[js]")


# ============================================================================
# СМЕШАННЫЙ СЦЕНАРИЙ (разные типы пользователей)
# ============================================================================

class MixedUser(HttpUser):
    """
    Смешанный сценарий:
    - 60% пользователей через Django auth
    - 30% через Keycloak
    - 10% анонимные
    """

    wait_time = between(1, 4)

    def on_start(self):
        import random
        auth_type = random.choices(
            ['django', 'keycloak', 'anonymous'],
            weights=[60, 30, 10]
        )[0]

        if auth_type == 'django':
            self.__class__.__bases__ = (DjangoAuthMixin, HttpUser)
            self.username = os.getenv('LOCUST_DJANGO_USER', 'locust_test')
            self.password = os.getenv('LOCUST_DJANGO_PASSWORD', 'locust_password_123')
            logger.info("Mixed user selected: Django auth")
            self.login()
        elif auth_type == 'keycloak':
            self.__class__.__bases__ = (KeycloakAuthMixin, HttpUser)
            self.keycloak_username = os.getenv('LOCUST_KEYCLOAK_USER', 'user')
            self.keycloak_password = os.getenv('LOCUST_KEYCLOAK_PASSWORD', '12345678')
            logger.info("Mixed user selected: Keycloak auth")
            self.login()
        else:
            logger.info("Mixed user selected: Anonymous")
            self.is_anonymous = True

    @task
    def browse(self):
        """Общий таск для смешанных пользователей"""
        if hasattr(self, 'is_anonymous') and self.is_anonymous:
            # Анонимный пользователь
            self.client.get("/accounts/login/")
        else:
            # Авторизованный пользователь
            self.client.get("/inventory/")


# ============================================================================
# EVENT HOOKS для дополнительной статистики
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Выполняется при старте теста"""
    logger.info("=" * 80)
    logger.info("LOCUST LOAD TEST STARTED")
    logger.info(f"Host: {environment.host}")
    logger.info("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Выполняется при остановке теста"""
    logger.info("=" * 80)
    logger.info("LOCUST LOAD TEST STOPPED")
    logger.info("=" * 80)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Логирование медленных запросов"""
    if response_time > 2000:  # Если запрос занял больше 2 секунд
        logger.warning(
            f"SLOW REQUEST: {request_type} {name} - {response_time}ms"
        )
