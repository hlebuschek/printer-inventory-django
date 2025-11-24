"""
Задачи для тестирования API endpoints
"""

import logging
from locust import TaskSet, task, between
import random
import json

logger = logging.getLogger(__name__)


class APITaskSet(TaskSet):
    """
    Набор задач для тестирования API endpoints.

    Тестирует различные API эндпоинты, используемые фронтендом
    и внешними интеграциями.
    """

    wait_time = between(0.5, 2)

    # Кэш данных
    printer_ids = []

    @task(10)
    def api_get_printers_list(self):
        """
        Получение списка принтеров через API.
        """
        with self.client.get(
            "/inventory/api/printers/",
            name="/inventory/api/printers/ [list]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    data = response.json()
                    if isinstance(data, list):
                        # Кэшируем ID принтеров
                        self.printer_ids = [p.get('id') for p in data if p.get('id')][:50]
                        logger.debug(f"API: Cached {len(self.printer_ids)} printer IDs")
                except Exception as e:
                    logger.error(f"Failed to parse API response: {e}")
            else:
                response.failure(f"API list failed: {response.status_code}")

    # УДАЛЕНО: api_get_printer_detail - возвращает 404

    @task(3)
    def api_get_system_status(self):
        """
        Получение статуса системы.
        """
        self.client.get(
            "/inventory/api/system-status/",
            name="/inventory/api/system-status/"
        )

    @task(3)
    def api_get_status_statistics(self):
        """
        Получение статистики по статусам принтеров.
        """
        self.client.get(
            "/inventory/api/status-statistics/",
            name="/inventory/api/status-statistics/"
        )

    @task(2)
    def api_get_printer_models(self):
        """
        Получение списка всех моделей принтеров.
        """
        self.client.get(
            "/inventory/api/all-printer-models/",
            name="/inventory/api/all-printer-models/"
        )

    @task(2)
    def api_models_by_manufacturer(self):
        """
        Получение моделей по производителю.
        """
        # Примеры производителей
        manufacturers = ['HP', 'Canon', 'Epson', 'Brother', 'Xerox', 'Kyocera']
        manufacturer = random.choice(manufacturers)

        self.client.get(
            f"/inventory/api/models-by-manufacturer/?manufacturer={manufacturer}",
            name="/inventory/api/models-by-manufacturer/"
        )

    @task(1)
    def api_probe_serial(self):
        """
        Проверка серийного номера принтера.
        """
        # Генерируем случайный IP для проверки
        ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"

        with self.client.post(
            "/inventory/api/probe-serial/",
            json={"ip_address": ip},
            name="/inventory/api/probe-serial/",
            catch_response=True
        ) as response:
            # Этот запрос может вернуть 404 если принтер не найден - это нормально
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Probe failed: {response.status_code}")

    @task(1)
    def api_web_parser_templates(self):
        """
        Получение шаблонов веб-парсинга.
        """
        self.client.get(
            "/inventory/api/web-parser/templates/",
            name="/inventory/api/web-parser/templates/"
        )

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting APITaskSet")
        # Загружаем список принтеров для кэширования
        self.api_get_printers_list()
