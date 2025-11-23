"""
Задачи для тестирования функционала месячных отчетов
"""

import logging
from locust import TaskSet, task, between
import random

logger = logging.getLogger(__name__)


class ReportTaskSet(TaskSet):
    """
    Набор задач для работы с месячными отчетами.

    Эмулирует работу с модулем ежемесячной отчетности.
    """

    wait_time = between(2, 5)

    report_ids = []

    @task(10)
    def view_reports_list(self):
        """
        Просмотр списка месячных отчетов.
        """
        with self.client.get(
            "/monthly-report/",
            name="/monthly-report/ [list]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()

                # Пытаемся извлечь ID отчетов
                import re
                report_links = re.findall(r'/monthly-report/(\d+)/', response.text)
                if report_links:
                    self.report_ids = [int(rid) for rid in report_links[:50]]
                    logger.debug(f"Cached {len(self.report_ids)} report IDs")
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def view_report_detail(self):
        """
        Просмотр детальной информации об отчете.
        """
        if not self.report_ids:
            self.view_reports_list()
            return

        report_id = random.choice(self.report_ids)
        self.client.get(
            f"/monthly-report/{report_id}/",
            name="/monthly-report/[id]/ [detail]"
        )

    @task(2)
    def view_sync_page(self):
        """
        Просмотр страницы синхронизации отчетов.
        """
        self.client.get(
            "/monthly-report/sync/",
            name="/monthly-report/sync/"
        )

    @task(1)
    def export_report(self):
        """
        Экспорт отчета в Excel.
        """
        with self.client.get(
            "/monthly-report/export/",
            name="/monthly-report/export/ [excel]",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Report export completed, size: {len(response.content)} bytes")
            else:
                response.failure(f"Export failed: {response.status_code}")

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting ReportTaskSet")
        self.view_reports_list()
