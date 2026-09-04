"""
Задачи для тестирования функционала контрактов
"""

import logging
import random

from locust import TaskSet, between, task

logger = logging.getLogger(__name__)


class ContractTaskSet(TaskSet):
    """
    Набор задач для работы с контрактами устройств.

    Страница /contracts/ — Vue SPA, данные подгружаются через
    /contracts/api/devices/ и /contracts/api/filters/.
    Отдельных страниц /contracts/new/ и /contracts/<id>/edit/ не существует.
    """

    wait_time = between(1, 4)

    device_ids = []

    @task(10)
    def view_contracts_page(self):
        """
        Просмотр страницы контрактных устройств (Vue SPA).
        """
        self.client.get("/contracts/", name="/contracts/ [page]")

    @task(5)
    def api_devices_list(self):
        """
        Получение списка устройств через API (то, что делает фронтенд).

        Ответ — {"devices": [...], "pagination": {...}}.
        """
        with self.client.get(
            "/contracts/api/devices/", name="/contracts/api/devices/ [list]", catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    devices = response.json().get("devices", [])
                    self.device_ids = [d["id"] for d in devices if d.get("id")][:50]
                    logger.debug(f"Cached {len(self.device_ids)} device IDs")
                except Exception as e:
                    logger.error(f"Failed to parse devices API response: {e}")
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def api_devices_paginated(self):
        """
        Список устройств со случайной страницей и размером страницы.
        """
        page = random.randint(1, 3)
        self.client.get(
            f"/contracts/api/devices/?page={page}&per_page=50",
            name="/contracts/api/devices/ [paginated]",
        )

    @task(2)
    def api_filters(self):
        """
        Данные для фильтров (организации, города, модели) — кэшируются на сервере.
        """
        self.client.get("/contracts/api/filters/", name="/contracts/api/filters/")

    @task(2)
    def rotate(self):
        """Выход из TaskSet — без interrupt() пользователь навсегда остаётся в одном сценарии."""
        self.interrupt()

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting ContractTaskSet")
        self.api_devices_list()
