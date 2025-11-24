"""
Задачи для тестирования функционала месячных отчетов
"""

import logging
from locust import TaskSet, task, between
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ReportTaskSet(TaskSet):
    """
    Набор задач для работы с месячными отчетами.

    Эмулирует работу с модулем ежемесячной отчетности.
    """

    wait_time = between(2, 5)

    report_months = []  # Хранит даты в формате YYYY-MM

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

                # Пытаемся извлечь месяцы отчетов (формат YYYY-MM)
                import re
                report_links = re.findall(r'/monthly-report/(\d{4}-\d{2})/', response.text)
                if report_links:
                    self.report_months = list(set(report_links[:50]))  # Уникальные значения
                    logger.debug(f"Cached {len(self.report_months)} report months")
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def view_report_detail(self):
        """
        Просмотр детальной информации об отчете.
        """
        if not self.report_months:
            self.view_reports_list()
            return

        report_month = random.choice(self.report_months)
        self.client.get(
            f"/monthly-report/{report_month}/",
            name="/monthly-report/[YYYY-MM]/ [detail]"
        )

    @task(2)
    def view_upload_page(self):
        """
        Просмотр страницы загрузки отчетов.
        """
        self.client.get(
            "/monthly-report/upload/",
            name="/monthly-report/upload/"
        )

    @task(1)
    def export_report(self):
        """
        Экспорт отчета в Excel.
        """
        if not self.report_months:
            self.view_reports_list()
            return

        report_month = random.choice(self.report_months)
        year, month = report_month.split('-')

        with self.client.get(
            f"/monthly-report/{year}/{month}/export-excel/",
            name="/monthly-report/[year]/[month]/export-excel/ [excel]",
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
