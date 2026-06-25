from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from monthly_report.models_modelspec import PaperFormat
from monthly_report.services_inventory_sync import _month_bounds_utc
from monthly_report.specs import _norm_model_name, allowed_counter_fields


class NormModelNameTests(SimpleTestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(_norm_model_name("  HP   LaserJet\tPro "), "HP LaserJet Pro")

    def test_none_returns_empty(self):
        self.assertEqual(_norm_model_name(None), "")


class AllowedCounterFieldsTests(SimpleTestCase):
    ALL_FIELDS = {
        "a4_bw_start",
        "a4_bw_end",
        "a4_color_start",
        "a4_color_end",
        "a3_bw_start",
        "a3_bw_end",
        "a3_color_start",
        "a3_color_end",
    }

    def test_no_spec_allows_everything(self):
        self.assertEqual(allowed_counter_fields(None), self.ALL_FIELDS)

    def test_disabled_enforce_allows_everything(self):
        spec = SimpleNamespace(enforce=False, is_color=True, paper_format=PaperFormat.A4_ONLY)
        self.assertEqual(allowed_counter_fields(spec), self.ALL_FIELDS)

    def test_mono_a4_only(self):
        spec = SimpleNamespace(enforce=True, is_color=False, paper_format=PaperFormat.A4_ONLY)
        self.assertEqual(allowed_counter_fields(spec), {"a4_bw_start", "a4_bw_end"})

    def test_color_a4_a3(self):
        spec = SimpleNamespace(enforce=True, is_color=True, paper_format=PaperFormat.A4_A3)
        self.assertEqual(
            allowed_counter_fields(spec),
            {"a4_color_start", "a4_color_end", "a3_color_start", "a3_color_end"},
        )

    def test_mono_a3_only(self):
        spec = SimpleNamespace(enforce=True, is_color=False, paper_format=PaperFormat.A3_ONLY)
        self.assertEqual(allowed_counter_fields(spec), {"a3_bw_start", "a3_bw_end"})


class MonthBoundsUtcTests(SimpleTestCase):
    def test_past_month_full_range(self):
        start, end = _month_bounds_utc(date(2025, 3, 1))
        ls = timezone.localtime(start)
        le = timezone.localtime(end)
        self.assertEqual((ls.month, ls.day, ls.hour, ls.minute, ls.second), (3, 1, 0, 0, 0))
        self.assertEqual((le.month, le.day, le.hour, le.minute, le.second), (3, 31, 23, 59, 59))

    def test_december_wraps_to_next_year(self):
        start, end = _month_bounds_utc(date(2025, 12, 1))
        le = timezone.localtime(end)
        self.assertEqual((le.year, le.month, le.day), (2025, 12, 31))
