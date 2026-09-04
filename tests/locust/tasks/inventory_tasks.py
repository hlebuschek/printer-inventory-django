"""
Задачи для тестирования функционала инвентаризации принтеров
"""

import logging
import random

from locust import TaskSet, between, task

logger = logging.getLogger(__name__)


class InventoryTaskSet(TaskSet):
    """
    Набор задач для работы с инвентарем принтеров.

    Эмулирует типичное поведение пользователя:
    - Просмотр списка принтеров (Vue SPA страница)
    - Просмотр формы редактирования принтера
    - Просмотр истории опросов
    - Постановка опроса принтера в очередь
    - Экспорт данных
    """

    wait_time = between(1, 3)

    # Кэш для хранения ID принтеров
    printer_ids = []

    def _refresh_printer_ids(self):
        """
        Кэширует ID принтеров через API.

        Страница /inventory/ — Vue SPA: в её HTML нет ссылок на принтеры,
        поэтому ID берём из JSON-ответа /inventory/api/printers/.
        """
        with self.client.get(
            "/inventory/api/printers/",
            name="/inventory/api/printers/ [cache ids]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    printers = response.json().get("printers", [])
                    self.printer_ids = [p["id"] for p in printers if p.get("id")][:50]
                    logger.debug(f"Cached {len(self.printer_ids)} printer IDs")
                except Exception as e:
                    logger.error(f"Failed to parse printers API response: {e}")
            else:
                response.failure(f"Got status {response.status_code}")

    def _csrf_headers(self):
        """Заголовки для POST-запросов (CSRF-токен из cookie сессии)."""
        token = self.client.cookies.get("csrftoken", "")
        return {"X-CSRFToken": token, "Referer": self.client.base_url + "/inventory/"}

    @task(10)
    def view_printer_list(self):
        """
        Просмотр страницы списка принтеров (самая частая операция).
        """
        self.client.get("/inventory/", name="/inventory/ [list page]")

    @task(5)
    def view_printer_edit(self):
        """
        Просмотр страницы редактирования принтера (Vue.js форма).
        """
        if not self.printer_ids:
            self._refresh_printer_ids()
            return

        printer_id = random.choice(self.printer_ids)
        self.client.get(f"/inventory/{printer_id}/edit-form/", name="/inventory/[id]/edit-form/ [edit]")

    @task(3)
    def view_printer_history(self):
        """
        Просмотр истории опросов принтера.

        Endpoint отвечает JSON только на AJAX-запросы,
        без заголовка X-Requested-With возвращает 400.
        """
        if not self.printer_ids:
            self._refresh_printer_ids()
            return

        printer_id = random.choice(self.printer_ids)
        self.client.get(
            f"/inventory/{printer_id}/history/",
            headers={"X-Requested-With": "XMLHttpRequest"},
            name="/inventory/[id]/history/ [history]",
        )

    @task(2)
    def run_printer_poll(self):
        """
        Постановка опроса принтера в очередь Celery (high_priority).

        ВНИМАНИЕ: это реальный опрос — нагрузка уйдёт на Celery-воркеры.
        Используйте с осторожностью при больших нагрузках!
        """
        if not self.printer_ids:
            self._refresh_printer_ids()
            return

        printer_id = random.choice(self.printer_ids)

        with self.client.post(
            f"/inventory/{printer_id}/run/",
            headers=self._csrf_headers(),
            name="/inventory/[id]/run/ [queue poll]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Poll queued for printer {printer_id}")
            else:
                response.failure(f"Poll failed: {response.status_code}")

    @task(1)
    def export_excel(self):
        """
        Экспорт данных в Excel.

        Это может быть тяжелая операция на сервере.
        """
        with self.client.get("/inventory/export/", name="/inventory/export/ [excel]", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Excel export completed, size: {len(response.content)} bytes")
            else:
                response.failure(f"Export failed: {response.status_code}")

    @task(1)
    def view_web_parser_setup(self):
        """
        Просмотр настроек веб-парсинга для принтера.
        """
        if not self.printer_ids:
            self._refresh_printer_ids()
            return

        printer_id = random.choice(self.printer_ids)
        self.client.get(f"/inventory/{printer_id}/web-parser/", name="/inventory/[id]/web-parser/ [setup]")

    @task(2)
    def rotate(self):
        """Выход из TaskSet — без interrupt() пользователь навсегда остаётся в одном сценарии."""
        self.interrupt()

    def on_start(self):
        """
        Выполняется при старте TaskSet.
        Загружаем список принтеров для кэширования ID.
        """
        logger.info("Starting InventoryTaskSet")
        self._refresh_printer_ids()
