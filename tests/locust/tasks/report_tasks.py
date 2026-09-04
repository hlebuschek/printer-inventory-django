"""
Задачи для тестирования функционала месячных отчетов
"""

import logging
import random

from locust import TaskSet, between, task

logger = logging.getLogger(__name__)


class ReportTaskSet(TaskSet):
    """
    Набор задач для работы с месячными отчетами.

    Страница списка месяцев — Vue SPA, данные подгружаются
    через /monthly-report/api/months/.
    """

    wait_time = between(2, 5)

    report_months = []  # Хранит даты в формате YYYY-MM

    def _refresh_months(self):
        """
        Кэширует доступные месяцы через API.

        Ответ — {"ok": true, "months": [{"month_str": "YYYY-MM", ...}], ...}.
        """
        with self.client.get(
            "/monthly-report/api/months/", name="/monthly-report/api/months/", catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                try:
                    months = response.json().get("months", [])
                    self.report_months = [m["month_str"] for m in months if m.get("month_str")][:50]
                    logger.debug(f"Cached {len(self.report_months)} report months")
                except Exception as e:
                    logger.error(f"Failed to parse months API response: {e}")
            else:
                response.failure(f"Got status {response.status_code}")

    @task(10)
    def view_reports_list(self):
        """
        Просмотр страницы списка месячных отчетов (Vue SPA).
        """
        self.client.get("/monthly-report/", name="/monthly-report/ [list page]")

    @task(5)
    def view_report_detail(self):
        """
        Просмотр страницы отчета за месяц.
        """
        if not self.report_months:
            self._refresh_months()
            return

        report_month = random.choice(self.report_months)
        self.client.get(f"/monthly-report/{report_month}/", name="/monthly-report/[YYYY-MM]/ [detail]")

    @task(3)
    def api_month_detail(self):
        """
        Данные отчета за месяц через API (то, что грузит фронтенд).
        """
        if not self.report_months:
            self._refresh_months()
            return

        report_month = random.choice(self.report_months)
        year, month = report_month.split("-")
        self.client.get(
            f"/monthly-report/api/month/{year}/{int(month)}/",
            name="/monthly-report/api/month/[y]/[m]/",
        )

    @task(1)
    def export_report(self):
        """
        Экспорт отчета в Excel.
        """
        if not self.report_months:
            self._refresh_months()
            return

        report_month = random.choice(self.report_months)
        year, month = report_month.split("-")

        with self.client.get(
            f"/monthly-report/{year}/{int(month)}/export-excel/",
            name="/monthly-report/[year]/[month]/export-excel/ [excel]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                logger.debug(f"Report export completed, size: {len(response.content)} bytes")
            else:
                response.failure(f"Export failed: {response.status_code}")

    @task(2)
    def rotate(self):
        """Выход из TaskSet — без interrupt() пользователь навсегда остаётся в одном сценарии."""
        self.interrupt()

    def on_start(self):
        """
        Инициализация TaskSet.
        """
        logger.info("Starting ReportTaskSet")
        self._refresh_months()
