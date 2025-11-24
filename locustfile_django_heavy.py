"""
Нагрузочный тест Django Printer Inventory - Heavy Load (только Django users)

Этот файл предназначен для тестирования с большим количеством пользователей (500+)
с использованием только Django аутентификации (без Keycloak).

Запуск:
    locust -f locustfile_django_heavy.py --headless --users 500 --spawn-rate 50 --run-time 10m --host http://localhost:8000
"""

import os
import logging
from locust import HttpUser, task, between, events
from tests.locust.tasks.auth_tasks import DjangoAuthMixin
from tests.locust.tasks.inventory_tasks import InventoryTaskSet
from tests.locust.tasks.api_tasks import APITaskSet
from tests.locust.tasks.contract_tasks import ContractTaskSet
from tests.locust.tasks.report_tasks import ReportTaskSet

logger = logging.getLogger(__name__)


class HeavyDjangoUser(DjangoAuthMixin, HttpUser):
    """
    Тяжелый пользователь с Django авторизацией.
    Тестирует ВСЕ основные функции системы.
    """
    wait_time = between(0.5, 2)  # Быстрее для большей нагрузки

    # Credentials
    username = os.getenv('LOCUST_DJANGO_USER', 'locust_test')
    password = os.getenv('LOCUST_DJANGO_PASSWORD', 'locust_password_123')

    def on_start(self):
        """Выполняется при старте пользователя"""
        logger.info(f"Starting heavy Django user: {self.username}")
        self.login()

    # Распределение задач с весами (чем больше число, тем чаще выполняется)
    @task(10)
    def view_printer_list(self):
        """Просмотр списка принтеров (самая частая операция)"""
        with self.client.get("/printers/", catch_response=True, name="/printers/ [list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def view_printer_edit(self):
        """Просмотр страницы редактирования принтера"""
        # Используем ID из диапазона (предполагаем, что есть принтеры с ID 1-100)
        printer_id = (hash(self.username) % 100) + 1
        with self.client.get(f"/printers/{printer_id}/edit/", catch_response=True,
                            name="/printers/[id]/edit/ [edit]") as response:
            if response.status_code in [200, 404]:  # 404 ok если принтера нет
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def view_printer_history(self):
        """Просмотр истории опросов принтера"""
        printer_id = (hash(self.username) % 100) + 1
        with self.client.get(f"/printers/{printer_id}/history/", catch_response=True,
                            name="/printers/[id]/history/ [history]") as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def api_get_printers(self):
        """API: Получение списка принтеров"""
        with self.client.get("/printers/api/printers/", catch_response=True,
                            name="/printers/api/printers/ [api-list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def api_get_printer_detail(self):
        """API: Получение деталей принтера"""
        printer_id = (hash(self.username) % 100) + 1
        with self.client.get(f"/printers/api/printer/{printer_id}/", catch_response=True,
                            name="/printers/api/printer/[id]/ [api-detail]") as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(2)
    def api_system_status(self):
        """API: Статус системы"""
        with self.client.get("/printers/api/system-status/", catch_response=True,
                            name="/printers/api/system-status/ [api-status]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(4)
    def view_contracts(self):
        """Просмотр списка контрактов"""
        with self.client.get("/contracts/", catch_response=True,
                            name="/contracts/ [contracts-list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(2)
    def view_contract_edit(self):
        """Просмотр страницы редактирования контракта"""
        device_id = (hash(self.username) % 50) + 1
        with self.client.get(f"/contracts/{device_id}/edit/", catch_response=True,
                            name="/contracts/[id]/edit/ [contract-edit]") as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def view_monthly_reports(self):
        """Просмотр ежемесячных отчетов"""
        with self.client.get("/monthly-report/", catch_response=True,
                            name="/monthly-report/ [reports-list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def view_web_parser(self):
        """Просмотр веб-парсера"""
        with self.client.get("/printers/web-parser/", catch_response=True,
                            name="/printers/web-parser/ [parser]") as response:
            if response.status_code in [200, 403]:  # 403 если нет прав
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def search_printers(self):
        """Поиск принтеров"""
        search_terms = ['HP', 'Canon', 'Epson', 'Brother', '192.168']
        search_term = search_terms[hash(self.username) % len(search_terms)]
        with self.client.get(f"/printers/?search={search_term}", catch_response=True,
                            name="/printers/?search=[term] [search]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(2)
    def view_static_files(self):
        """Загрузка статических файлов (CSS/JS)"""
        static_files = [
            '/static/css/vendor/bootstrap.min.css',
            '/static/js/vendor/alpine.min.js',
        ]
        static_file = static_files[hash(self.username) % len(static_files)]
        with self.client.get(static_file, catch_response=True,
                            name="/static/[file] [static]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")


class AnonymousHeavyUser(HttpUser):
    """
    Анонимный пользователь - тестирует публичные страницы
    """
    wait_time = between(1, 3)
    weight = 1  # Меньше анонимных пользователей

    @task(5)
    def view_login_page(self):
        """Просмотр страницы входа"""
        self.client.get("/accounts/login/", name="/accounts/login/ [anon]")

    @task(2)
    def view_django_login(self):
        """Просмотр страницы Django логина"""
        self.client.get("/accounts/django-login/", name="/accounts/django-login/ [anon]")

    @task(1)
    def try_access_printers(self):
        """Попытка доступа к принтерам без авторизации"""
        with self.client.get("/printers/", catch_response=True,
                            name="/printers/ [anon-unauthorized]") as response:
            # Должен редиректить на логин или возвращать 403
            if response.status_code in [302, 403]:
                response.success()
            else:
                response.failure(f"Expected redirect or 403, got {response.status_code}")


# Event handlers
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Вызывается при старте теста"""
    logger.info("="*80)
    logger.info("HEAVY DJANGO LOAD TEST STARTED")
    logger.info(f"Host: {environment.host}")
    logger.info(f"Users: {environment.runner.user_count if hasattr(environment.runner, 'user_count') else 'N/A'}")
    logger.info("="*80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Вызывается при остановке теста"""
    logger.info("="*80)
    logger.info("HEAVY DJANGO LOAD TEST STOPPED")
    logger.info("="*80)


# Распределение пользователей
# 90% авторизованных Django пользователей, 10% анонимных
HeavyDjangoUser.weight = 9
AnonymousHeavyUser.weight = 1
