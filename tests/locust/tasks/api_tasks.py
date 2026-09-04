"""
Задачи для тестирования API endpoints
"""

import logging
import random

from locust import TaskSet, between, task

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
    manufacturer_ids = []
    device_model_ids = []

    @task(10)
    def api_get_printers_list(self):
        """
        Получение списка принтеров через API.

        Ответ — объект: {"printers": [...], "manufacturers": [...],
        "device_models": [...], "organizations": [...], пагинация}.
        Кэшируем ID для остальных задач.
        """
        with self.client.get(
            "/inventory/api/printers/", name="/inventory/api/printers/ [list]", catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    data = response.json()
                    printers = data.get("printers", [])
                    self.printer_ids = [p["id"] for p in printers if p.get("id")][:50]
                    self.manufacturer_ids = [m["id"] for m in data.get("manufacturers", []) if m.get("id")]
                    self.device_model_ids = [m["id"] for m in data.get("device_models", []) if m.get("id")]
                    logger.debug(f"API: Cached {len(self.printer_ids)} printer IDs")
                except Exception as e:
                    logger.error(f"Failed to parse API response: {e}")
            else:
                response.failure(f"API list failed: {response.status_code}")

    @task(5)
    def api_get_printer_detail(self):
        """
        Получение детальной информации о принтере через API.
        """
        if not self.printer_ids:
            self.api_get_printers_list()
            return

        printer_id = random.choice(self.printer_ids)
        self.client.get(f"/inventory/api/printer/{printer_id}/", name="/inventory/api/printer/[id]/ [detail]")

    @task(3)
    def api_get_system_status(self):
        """
        Получение статуса системы.
        """
        self.client.get("/inventory/api/system-status/", name="/inventory/api/system-status/")

    @task(3)
    def api_get_status_statistics(self):
        """
        Получение статистики по статусам принтеров.
        """
        self.client.get("/inventory/api/status-statistics/", name="/inventory/api/status-statistics/")

    @task(2)
    def api_get_printer_models(self):
        """
        Получение списка всех моделей принтеров.
        """
        self.client.get("/inventory/api/all-printer-models/", name="/inventory/api/all-printer-models/")

    @task(2)
    def api_models_by_manufacturer(self):
        """
        Получение моделей по производителю.

        Endpoint принимает параметр manufacturer_id (число),
        имена производителей не поддерживаются.
        """
        if not self.manufacturer_ids:
            self.api_get_printers_list()
            return

        manufacturer_id = random.choice(self.manufacturer_ids)
        self.client.get(
            f"/inventory/api/models-by-manufacturer/?manufacturer_id={manufacturer_id}",
            name="/inventory/api/models-by-manufacturer/",
        )

    @task(1)
    def api_replacement_history(self):
        """
        История замен принтера по адресу.
        """
        if not self.printer_ids:
            self.api_get_printers_list()
            return

        printer_id = random.choice(self.printer_ids)
        self.client.get(
            f"/inventory/api/printer/{printer_id}/replacement-history/",
            name="/inventory/api/printer/[id]/replacement-history/",
        )

    @task(1)
    def api_web_parser_templates(self):
        """
        Получение шаблонов веб-парсинга.

        Endpoint требует device_model_id, без него возвращает пустой список.
        """
        if not self.device_model_ids:
            self.api_get_printers_list()
            return

        device_model_id = random.choice(self.device_model_ids)
        self.client.get(
            f"/inventory/api/web-parser/templates/?device_model_id={device_model_id}",
            name="/inventory/api/web-parser/templates/",
        )

    @task(2)
    def rotate(self):
        """Выход из TaskSet — без interrupt() пользователь навсегда остаётся в одном сценарии."""
        self.interrupt()

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting APITaskSet")
        # Загружаем список принтеров для кэширования
        self.api_get_printers_list()
