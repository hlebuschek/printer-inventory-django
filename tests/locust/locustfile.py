"""
Locustfile для нагрузочного тестирования Printer Inventory Django.

Использование:
    # Веб-интерфейс
    locust -f tests/locust/locustfile.py --host=http://localhost:8000

    # Headless (CI smoke-тест)
    locust -f tests/locust/locustfile.py CISmokeUser \
        --host=http://localhost:8000 \
        --users 5 --spawn-rate 5 --run-time 30s \
        --headless --only-summary
"""

import os

from locust import HttpUser, between

from tasks.api_tasks import APITaskSet
from tasks.auth_tasks import DjangoAuthMixin
from tasks.contract_tasks import ContractTaskSet
from tasks.inventory_tasks import InventoryTaskSet
from tasks.report_tasks import ReportTaskSet


class DjangoAuthUser(DjangoAuthMixin, HttpUser):
    """
    Пользователь с Django авторизацией.
    Выполняет все типы задач: инвентарь, API, контракты, отчёты.
    """

    username = os.environ.get("LOCUST_DJANGO_USER", "locust_test")
    password = os.environ.get("LOCUST_DJANGO_PASSWORD", "locust_password_123")

    wait_time = between(1, 5)

    tasks = {
        InventoryTaskSet: 5,
        APITaskSet: 3,
        ContractTaskSet: 1,
        ReportTaskSet: 1,
    }

    def on_start(self):
        self.login()


class AnonymousUser(HttpUser):
    """
    Анонимный пользователь — только публичные страницы.
    """

    wait_time = between(1, 3)

    @staticmethod
    def _task_login_page(user):
        user.client.get("/accounts/login/", name="/accounts/login/")

    @staticmethod
    def _task_static(user):
        user.client.get("/static/css/vendor/bootstrap.min.css", name="/static/ [css]")

    tasks = {
        _task_login_page: 3,
        _task_static: 1,
    }


class CISmokeUser(DjangoAuthMixin, HttpUser):
    """
    Лёгкий пользователь для CI smoke-теста.
    Без опроса принтеров — только просмотр страниц и API.
    """

    username = os.environ.get("LOCUST_DJANGO_USER", "locust_test")
    password = os.environ.get("LOCUST_DJANGO_PASSWORD", "locust_password_123")

    wait_time = between(0.5, 2)

    tasks = {
        APITaskSet: 3,
        ContractTaskSet: 1,
        ReportTaskSet: 1,
    }

    def on_start(self):
        self.login()
