from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from dashboard.services import _cache_key, _parse_percent, get_poll_stats, get_printer_status
from inventory.models import InventoryTask, Organization, Printer


class ParsePercentTests(SimpleTestCase):
    def test_percent_string(self):
        self.assertEqual(_parse_percent("75%"), 75)

    def test_bare_number(self):
        self.assertEqual(_parse_percent("75"), 75)

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_parse_percent("N/A"))

    def test_empty_returns_none(self):
        self.assertIsNone(_parse_percent(""))


class CacheKeyTests(SimpleTestCase):
    def test_with_org_and_period(self):
        self.assertEqual(_cache_key("status", 5, 7), "dashboard:status:org:5:period:7")

    def test_without_org_uses_all(self):
        self.assertEqual(_cache_key("status", None), "dashboard:status:org:all")

    def test_period_zero_is_included(self):
        self.assertEqual(_cache_key("trend", 1, 0), "dashboard:trend:org:1:period:0")


class DashboardAggregationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(name="Org D")

    def _printer(self, ip, serial):
        return Printer.objects.create(
            ip_address=ip, serial_number=serial, snmp_community="public", organization=self.org
        )

    def _task(self, printer, status, age_hours=1):
        task = InventoryTask.objects.create(printer=printer, status=status)
        ts = timezone.now() - timedelta(hours=age_hours)
        InventoryTask.objects.filter(pk=task.pk).update(task_timestamp=ts)
        return task

    def test_printer_status_online_offline(self):
        p_online = self._printer("10.0.0.1", "S1")
        p_offline = self._printer("10.0.0.2", "S2")
        self._task(p_online, "SUCCESS", age_hours=1)
        self._task(p_offline, "SUCCESS", age_hours=48)  # вне окна 24ч
        result = get_printer_status()
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["online"], 1)
        self.assertEqual(result["offline"], 1)
        self.assertEqual(result["percentage"], 50)

    def test_printer_status_empty(self):
        self.assertEqual(get_printer_status()["percentage"], 0)

    def test_poll_stats_counts_by_status(self):
        p = self._printer("10.0.0.3", "S3")
        self._task(p, "SUCCESS", age_hours=1)
        self._task(p, "SUCCESS", age_hours=2)
        self._task(p, "FAILED", age_hours=3)
        self._task(p, "SUCCESS", age_hours=24 * 30)  # вне окна 7 дней
        stats = {row["status"]: row["count"] for row in get_poll_stats(period_days=7)}
        self.assertEqual(stats["SUCCESS"], 2)
        self.assertEqual(stats["FAILED"], 1)
