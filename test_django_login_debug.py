"""
Тестовый файл для отладки Django логина
"""
import os
from locust import HttpUser, task, between
from tests.locust.tasks.auth_tasks import DjangoAuthMixin
from tests.locust.tasks.inventory_tasks import InventoryTaskSet


class DjangoAuthUserDebug(DjangoAuthMixin, HttpUser):
    """Пользователь с Django авторизацией для отладки"""
    wait_time = between(1, 2)

    # Credentials из переменных окружения или дефолтные
    username = os.getenv('LOCUST_DJANGO_USER', 'locust_test')
    password = os.getenv('LOCUST_DJANGO_PASSWORD', 'locust_password_123')

    def on_start(self):
        """Выполняется при старте пользователя"""
        print(f"\n{'='*80}")
        print(f"Starting Django auth user: {self.username}")
        print(f"{'='*80}\n")
        self.login()

    @task
    def view_printers(self):
        """Просмотр списка принтеров"""
        self.client.get("/printers/", name="/printers/ [authenticated]")
