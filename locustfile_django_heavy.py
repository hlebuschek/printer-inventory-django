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

    # Кэш реальных ID принтеров и контрактов
    printer_ids = []
    contract_ids = []

    def on_start(self):
        """Выполняется при старте пользователя"""
        logger.info(f"Starting heavy Django user: {self.username}")
        self.login()
        # Получаем реальные ID из API
        self._load_printer_ids()
        self._load_contract_ids()

    def _load_printer_ids(self):
        """Загружает реальные ID принтеров из API"""
        try:
            response = self.client.get("/inventory/api/printers/", name="/inventory/api/printers/ [init-cache]")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    # Берем до 50 случайных ID
                    import random
                    self.printer_ids = [p.get('id') for p in data if p.get('id')][:50]
                    random.shuffle(self.printer_ids)
                    logger.info(f"Loaded {len(self.printer_ids)} real printer IDs")
        except Exception as e:
            logger.warning(f"Failed to load printer IDs: {e}")
            # Fallback - используем случайные ID
            self.printer_ids = list(range(1, 11))

    def _load_contract_ids(self):
        """Загружает реальные ID контрактов"""
        # Fallback - используем небольшой диапазон
        self.contract_ids = list(range(1, 11))

    def _get_random_printer_id(self):
        """Возвращает случайный реальный ID принтера"""
        if self.printer_ids:
            import random
            return random.choice(self.printer_ids)
        # Fallback если нет кэша
        return (hash(self.username) % 100) + 1

    def _get_random_contract_id(self):
        """Возвращает случайный реальный ID контракта"""
        if self.contract_ids:
            import random
            return random.choice(self.contract_ids)
        # Fallback если нет кэша
        return (hash(self.username) % 50) + 1

    # Распределение задач с весами (чем больше число, тем чаще выполняется)
    @task(10)
    def view_printer_list(self):
        """Просмотр списка принтеров (самая частая операция)"""
        with self.client.get("/inventory/", catch_response=True, name="/inventory/ [list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def view_printer_edit(self):
        """Просмотр страницы редактирования принтера (Vue.js форма)"""
        printer_id = self._get_random_printer_id()
        with self.client.get(f"/inventory/{printer_id}/edit-form/", catch_response=True,
                            name="/inventory/[id]/edit-form/ [edit]") as response:
            if response.status_code in [200, 404]:  # 404 ok если принтера нет
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def view_printer_history(self):
        """Просмотр истории опросов принтера"""
        printer_id = self._get_random_printer_id()
        with self.client.get(f"/inventory/{printer_id}/history/", catch_response=True,
                            name="/inventory/[id]/history/ [history]") as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def api_get_printers(self):
        """API: Получение списка принтеров"""
        with self.client.get("/inventory/api/printers/", catch_response=True,
                            name="/inventory/api/printers/ [api-list]") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def api_get_printer_detail(self):
        """API: Получение деталей принтера"""
        printer_id = self._get_random_printer_id()
        with self.client.get(f"/inventory/api/printer/{printer_id}/", catch_response=True,
                            name="/inventory/api/printer/[id]/ [api-detail]") as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(2)
    def api_system_status(self):
        """API: Статус системы"""
        with self.client.get("/inventory/api/system-status/", catch_response=True,
                            name="/inventory/api/system-status/ [api-status]") as response:
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
        device_id = self._get_random_contract_id()
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
        """Просмотр веб-парсера для принтера (Vue.js)"""
        printer_id = self._get_random_printer_id()
        with self.client.get(f"/inventory/{printer_id}/web-parser/", catch_response=True,
                            name="/inventory/[id]/web-parser/ [parser]") as response:
            if response.status_code in [200, 404, 403]:  # 404 если принтера нет, 403 если нет прав
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def search_printers(self):
        """Поиск принтеров"""
        search_terms = ['HP', 'Canon', 'Epson', 'Brother', '192.168']
        search_term = search_terms[hash(self.username) % len(search_terms)]
        with self.client.get(f"/inventory/?search={search_term}", catch_response=True,
                            name="/inventory/?search=[term] [search]") as response:
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
        with self.client.get("/inventory/", catch_response=True,
                            name="/inventory/ [anon-unauthorized]") as response:
            # Страница может быть публичной (200) или редиректить на логин (302) или возвращать 403
            if response.status_code in [200, 302, 403]:
                response.success()
            else:
                response.failure(f"Expected 200/302/403, got {response.status_code}")


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
