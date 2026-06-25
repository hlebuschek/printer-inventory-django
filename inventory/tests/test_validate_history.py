from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from inventory.models import InventoryTask, PageCounter, Printer
from inventory.utils import validate_against_history


class ValidateAgainstHistoryTests(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            ip_address="10.0.0.10",
            serial_number="SN-HIST-1",
            snmp_community="public",
        )

    def _add_success(self, counters, age_hours=1):
        """Создаёт успешный InventoryTask + PageCounter с заданным возрастом."""
        task = InventoryTask.objects.create(printer=self.printer, status="SUCCESS")
        ts = timezone.now() - timedelta(hours=age_hours)
        InventoryTask.objects.filter(pk=task.pk).update(task_timestamp=ts)
        PageCounter.objects.create(task=task, **counters)
        return task

    def test_no_history_accepts(self):
        ok, err, rule = validate_against_history(self.printer, {"total_pages": 100})
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertIsNone(rule)

    def test_tasks_without_counters_accepts(self):
        task = InventoryTask.objects.create(printer=self.printer, status="SUCCESS")
        self.assertTrue(InventoryTask.objects.filter(pk=task.pk).exists())
        ok, _, _ = validate_against_history(self.printer, {"total_pages": 100})
        self.assertTrue(ok)

    def test_stable_a3_missing_in_new_rejected(self):
        for _ in range(5):
            self._add_success({"bw_a3": 100, "bw_a4": 1000, "total_pages": 1100})
        ok, err, rule = validate_against_history(self.printer, {"bw_a4": 1200, "total_pages": 1200})
        self.assertFalse(ok)
        self.assertEqual(rule, "HISTORICAL_INCONSISTENCY")
        self.assertIn("A3", err)

    def test_stable_color_missing_in_new_rejected(self):
        for _ in range(5):
            self._add_success({"color_a4": 100, "bw_a4": 1000, "total_pages": 1100})
        ok, err, rule = validate_against_history(self.printer, {"bw_a4": 1200, "total_pages": 1200})
        self.assertFalse(ok)
        self.assertEqual(rule, "HISTORICAL_INCONSISTENCY")
        self.assertIn("цветные", err.lower())

    def test_significant_decrease_rejected(self):
        self._add_success({"bw_a4": 1000, "total_pages": 1000})
        ok, err, rule = validate_against_history(self.printer, {"bw_a4": 500, "total_pages": 500})
        self.assertFalse(ok)
        self.assertEqual(rule, "HISTORICAL_INCONSISTENCY")
        self.assertIn("уменьшение", err)

    def test_kyocera_jump_recent_poll_rejected(self):
        self._add_success({"bw_a4": 1000, "total_pages": 1000}, age_hours=2)
        ok, err, rule = validate_against_history(self.printer, {"bw_a4": 7000, "total_pages": 7000})
        self.assertFalse(ok)
        self.assertEqual(rule, "HISTORICAL_INCONSISTENCY")
        self.assertIn("скачок", err)

    def test_large_jump_after_old_poll_accepted(self):
        # Последний опрос > 30 дней назад → проверка скачка пропускается.
        self._add_success({"bw_a4": 1000, "total_pages": 1000}, age_hours=24 * 40)
        ok, err, rule = validate_against_history(self.printer, {"bw_a4": 7000, "total_pages": 7000})
        self.assertTrue(ok, msg=err)

    def test_normal_increase_recent_poll_accepted(self):
        self._add_success({"bw_a4": 1000, "total_pages": 1000}, age_hours=2)
        ok, err, _ = validate_against_history(self.printer, {"bw_a4": 1200, "total_pages": 1200})
        self.assertTrue(ok, msg=err)
