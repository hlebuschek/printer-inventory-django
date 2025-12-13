"""
Задачи для тестирования функционала контрактов
"""

import logging
from locust import TaskSet, task, between
import random

logger = logging.getLogger(__name__)


class ContractTaskSet(TaskSet):
    """
    Набор задач для работы с контрактами устройств.

    Эмулирует работу с модулем управления контрактами.
    """

    wait_time = between(1, 4)

    device_ids = []

    @task(10)
    def view_contracts_list(self):
        """
        Просмотр списка контрактных устройств.
        """
        with self.client.get(
            "/contracts/",
            name="/contracts/ [list]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()

                # Пытаемся извлечь ID устройств
                import re
                device_links = re.findall(r'/contracts/(\d+)/edit/', response.text)
                if device_links:
                    self.device_ids = [int(did) for did in device_links[:50]]
                    logger.debug(f"Cached {len(self.device_ids)} device IDs")
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def view_contract_device_edit(self):
        """
        Просмотр страницы редактирования устройства контракта.
        """
        if not self.device_ids:
            self.view_contracts_list()
            return

        device_id = random.choice(self.device_ids)
        self.client.get(
            f"/contracts/{device_id}/edit/",
            name="/contracts/[id]/edit/ [edit]"
        )

    @task(1)
    def view_contract_new_page(self):
        """
        Просмотр страницы создания нового контракта.
        """
        self.client.get(
            "/contracts/new/",
            name="/contracts/new/"
        )

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting ContractTaskSet")
        self.view_contracts_list()
