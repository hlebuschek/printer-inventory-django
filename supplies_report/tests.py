from datetime import datetime
from types import SimpleNamespace
from unittest import skipUnless

from django.db import connection
from django.test import SimpleTestCase, TestCase

from inventory.models import InventoryTask, Organization, PageCounter, Printer
from supplies_report.models import ReportGroup, ReportGroupItem
from supplies_report.services import (
    _format_toner_value,
    _multiline_html,
    build_report_data,
    format_subject,
    printer_model_name,
    split_emails,
)


class FormatTonerValueTests(SimpleTestCase):
    def test_none_and_empty(self):
        self.assertEqual(_format_toner_value(None), "-")
        self.assertEqual(_format_toner_value("  "), "-")

    def test_bare_number_becomes_percent(self):
        self.assertEqual(_format_toner_value("79"), "79%")

    def test_text_passthrough(self):
        self.assertEqual(_format_toner_value("1900 стр."), "1900 стр.")


class SplitEmailsTests(SimpleTestCase):
    def test_mixed_separators(self):
        blob = "a@x.ru, b@x.ru; c@x.ru\nd@x.ru"
        self.assertEqual(split_emails(blob), ["a@x.ru", "b@x.ru", "c@x.ru", "d@x.ru"])

    def test_empty(self):
        self.assertEqual(split_emails(""), [])

    def test_strips_and_drops_blanks(self):
        self.assertEqual(split_emails("  a@x.ru ,, "), ["a@x.ru"])


class FormatSubjectTests(SimpleTestCase):
    def test_placeholder_substitution(self):
        group = SimpleNamespace(subject_template="Отчёт {location} за {date}", location_label="Иркутск")
        today = datetime(2026, 6, 25)
        self.assertEqual(format_subject(group, today), "Отчёт Иркутск за 25.06.2026")

    def test_empty_template(self):
        group = SimpleNamespace(subject_template="", location_label="X")
        self.assertEqual(format_subject(group, datetime(2026, 1, 1)), "")


class MultilineHtmlTests(SimpleTestCase):
    def test_empty_returns_mdash(self):
        self.assertEqual(_multiline_html(""), "&mdash;")

    def test_joins_lines_with_br_and_escapes(self):
        self.assertEqual(_multiline_html("a <b>\nc"), "a &lt;b&gt;<br>c")


class PrinterModelNameTests(SimpleTestCase):
    def test_uses_device_model_name(self):
        printer = SimpleNamespace(device_model=SimpleNamespace(name="ECOSYS M5526cdn"), model="old")
        self.assertEqual(printer_model_name(printer), "ECOSYS M5526cdn")

    def test_falls_back_to_model_field(self):
        printer = SimpleNamespace(device_model=None, model="Legacy 100")
        self.assertEqual(printer_model_name(printer), "Legacy 100")


@skipUnless(connection.vendor == "postgresql", "build_report_data использует DISTINCT ON (Postgres)")
class BuildReportDataTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org S")
        self.group = ReportGroup.objects.create(name="Группа 1")

    def _printer(self, ip, serial):
        return Printer.objects.create(
            ip_address=ip, serial_number=serial, snmp_community="public", organization=self.org, model="HP 100"
        )

    def test_row_with_latest_counter_and_consumables(self):
        printer = self._printer("10.0.0.1", "S1")
        task = InventoryTask.objects.create(printer=printer, status="SUCCESS")
        PageCounter.objects.create(task=task, toner_black="80", drum_black="90")
        ReportGroupItem.objects.create(group=self.group, printer=printer, location="5 этаж")

        rows = build_report_data(self.group)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertFalse(row.no_data)
        self.assertEqual(row.ip, "10.0.0.1")
        self.assertEqual(len(row.consumables), 1)
        self.assertEqual(row.consumables[0].toner_text, "80%")

    def test_printer_without_counter_marked_no_data(self):
        printer = self._printer("10.0.0.2", "S2")
        ReportGroupItem.objects.create(group=self.group, printer=printer)
        rows = build_report_data(self.group)
        self.assertTrue(rows[0].no_data)
        self.assertEqual(rows[0].consumables, [])
