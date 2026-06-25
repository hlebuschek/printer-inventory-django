from django.test import SimpleTestCase

from inventory.web_parser import (
    apply_regex_processing,
    extract_numeric_value,
    normalize_mac_address,
    safe_eval_formula,
)


class ApplyRegexProcessingTests(SimpleTestCase):
    def test_empty_pattern_returns_value_unchanged(self):
        self.assertEqual(apply_regex_processing("abc", "", ""), "abc")

    def test_replacement_then_uppercased(self):
        self.assertEqual(apply_regex_processing("abc123", r"\d+", "X"), "ABCX")

    def test_search_returns_first_group(self):
        self.assertEqual(apply_regex_processing("abc123def", r"(\d+)", ""), "123")

    def test_no_match_returns_uppercased_value(self):
        self.assertEqual(apply_regex_processing("abc", r"\d+", ""), "ABC")

    def test_invalid_pattern_returns_original(self):
        self.assertEqual(apply_regex_processing("abc", "(", ""), "abc")


class ExtractNumericValueTests(SimpleTestCase):
    def test_strips_spaces(self):
        self.assertEqual(extract_numeric_value("1 234 pages"), 1234)

    def test_strips_commas_and_decimal_tail(self):
        self.assertEqual(extract_numeric_value("12,345.67"), 12345)

    def test_no_digits_returns_zero(self):
        self.assertEqual(extract_numeric_value("no digits"), 0)

    def test_decimal_truncated(self):
        self.assertEqual(extract_numeric_value("1.999"), 1)


class NormalizeMacAddressTests(SimpleTestCase):
    def test_plain_hex(self):
        self.assertEqual(normalize_mac_address("aabbccddeeff"), "AA:BB:CC:DD:EE:FF")

    def test_already_formatted(self):
        self.assertEqual(normalize_mac_address("AA:BB:CC:DD:EE:FF"), "AA:BB:CC:DD:EE:FF")

    def test_invalid_returns_none(self):
        self.assertIsNone(normalize_mac_address("zz"))


class SafeEvalFormulaTests(SimpleTestCase):
    def test_addition(self):
        self.assertEqual(safe_eval_formula("a + b", {"a": 2, "b": 3}), 5)

    def test_integer_division_truncates(self):
        self.assertEqual(safe_eval_formula("total / 4", {"total": 10}), 2)

    def test_unresolved_variable_raises(self):
        with self.assertRaises(ValueError):
            safe_eval_formula("a + x", {"a": 1})

    def test_division_by_zero_raises(self):
        with self.assertRaises(ValueError):
            safe_eval_formula("a / b", {"a": 1, "b": 0})
