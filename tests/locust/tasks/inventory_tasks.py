"""
Задачи для тестирования функционала инвентаризации принтеров
"""

import logging
from locust import TaskSet, task, between
import random

logger = logging.getLogger(__name__)


class InventoryTaskSet(TaskSet):
    """
    Набор задач для работы с инвентарем принтеров.

    Эмулирует типичное поведение пользователя:
    - Просмотр списка принтеров
    - Просмотр деталей принтера
    - Просмотр истории опросов
    - Запуск опроса принтера
    - Экспорт данных
    """

    wait_time = between(1, 3)

    # Кэш для хранения ID принтеров
    printer_ids = []

    @task(10)
    def view_printer_list(self):
        """
        Просмотр списка принтеров (самая частая операция).

        Также кэширует ID принтеров для использования в других задачах.
        """
        with self.client.get(
            "/inventory/",
            name="/inventory/ [list]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()

                # Пытаемся извлечь ID принтеров из ответа
                import re
                printer_links = re.findall(r'/inventory/(\d+)/', response.text)
                if printer_links:
                    self.printer_ids = [int(pid) for pid in printer_links[:50]]  # Лимит 50
                    logger.debug(f"Cached {len(self.printer_ids)} printer IDs")
            else:
                response.failure(f"Got status {response.status_code}")

    # УДАЛЕНО: view_printer_edit - теперь модальное окно
    # УДАЛЕНО: view_printer_history - теперь модальное окно

    @task(2)
    def run_printer_poll(self):
        """
        Запуск опроса конкретного принтера.

        ВНИМАНИЕ: Это тяжелая операция, которая запускает реальный опрос SNMP/Web.
        Используйте с осторожностью при больших нагрузках!
        """
        if not self.printer_ids:
            self.view_printer_list()
            return

        printer_id = random.choice(self.printer_ids)

        # Обычно это POST запрос или специальный endpoint
        with self.client.post(
            f"/inventory/{printer_id}/poll/",
            name="/inventory/[id]/poll/ [run poll]",
            catch_response=True
        ) as response:
            # Опрос может быть асинхронным и вернуть 202 Accepted
            if response.status_code in [200, 201, 202]:
                response.success()
                logger.debug(f"Poll initiated for printer {printer_id}")
            else:
                response.failure(f"Poll failed: {response.status_code}")

    @task(1)
    def export_excel(self):
        """
        Экспорт данных в Excel.

        Это может быть тяжелая операция на сервере.
        """
        with self.client.get(
            "/inventory/export/",
            name="/inventory/export/ [excel]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Excel export completed, size: {len(response.content)} bytes")
            else:
                response.failure(f"Export failed: {response.status_code}")

    # УДАЛЕНО: view_web_parser_setup - теперь модальное окно

    def on_start(self):
        """
        Выполняется при старте TaskSet.
        Загружаем список принтеров для кэширования ID.
        """
        logger.info("Starting InventoryTaskSet")
        self.view_printer_list()
