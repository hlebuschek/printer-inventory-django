"""
Тесты для совмещённого опроса (HYBRID polling).

Проверяет функции объединения данных SNMP + Web:
- _is_cartridge_error()
- _is_counter_error()
- _merge_snmp_web_data()
"""

from django.test import SimpleTestCase

from inventory.services import (
    _is_cartridge_error,
    _is_counter_error,
    _merge_snmp_web_data,
)


class IsCartridgeErrorTests(SimpleTestCase):
    """Тесты определения ошибочных значений картриджей."""

    def test_none_and_empty_are_errors(self):
        """None и пустые значения считаются ошибкой."""
        self.assertTrue(_is_cartridge_error(None))
        self.assertTrue(_is_cartridge_error(""))
        self.assertTrue(_is_cartridge_error("   "))

    def test_zero_is_error(self):
        """Значение '0' считается ошибкой (перезаправлен без замены чипа)."""
        self.assertTrue(_is_cartridge_error("0"))
        self.assertTrue(_is_cartridge_error(0))

    def test_explicit_error_values(self):
        """Явные ошибочные значения."""
        self.assertTrue(_is_cartridge_error("none"))
        self.assertTrue(_is_cartridge_error("n/a"))
        self.assertTrue(_is_cartridge_error("null"))
        self.assertTrue(_is_cartridge_error("--"))

    def test_error_indicators_substring(self):
        """Подстроки-индикаторы ошибки."""
        self.assertTrue(_is_cartridge_error("WARNING: low toner"))
        self.assertTrue(_is_cartridge_error("ERROR: replace cartridge"))
        self.assertTrue(_is_cartridge_error("Replace soon"))
        self.assertTrue(_is_cartridge_error("Low toner level"))
        self.assertTrue(_is_cartridge_error("Empty cartridge"))
        self.assertTrue(_is_cartridge_error("End of life"))
        self.assertTrue(_is_cartridge_error("----"))
        self.assertTrue(_is_cartridge_error("____"))

    def test_valid_percentages(self):
        """Валидные процентные значения НЕ считаются ошибкой."""
        self.assertFalse(_is_cartridge_error("50%"))
        self.assertFalse(_is_cartridge_error("100%"))
        self.assertFalse(_is_cartridge_error("25%"))
        self.assertFalse(_is_cartridge_error("0%"))  # Граничный случай

    def test_valid_numeric_values(self):
        """Числовые значения уровня."""
        self.assertFalse(_is_cartridge_error("50"))
        self.assertFalse(_is_cartridge_error("100"))
        self.assertFalse(_is_cartridge_error("75"))


class IsCounterErrorTests(SimpleTestCase):
    """Тесты определения ошибочных значений счётчиков."""

    def test_none_and_empty_are_errors(self):
        """None и пустые значения считаются ошибкой."""
        self.assertTrue(_is_counter_error(None))
        self.assertTrue(_is_counter_error(""))
        self.assertTrue(_is_counter_error("   "))

    def test_negative_is_error(self):
        """Отрицательные значения считаются ошибкой."""
        self.assertTrue(_is_counter_error("-1"))
        self.assertTrue(_is_counter_error("-100"))

    def test_non_numeric_is_error(self):
        """Нечисловые значения считаются ошибкой."""
        self.assertTrue(_is_counter_error("not-a-number"))
        self.assertTrue(_is_counter_error("ERROR"))
        self.assertTrue(_is_counter_error("----"))

    def test_zero_and_positive_are_valid(self):
        """Ноль и положительные числа валидны."""
        self.assertFalse(_is_counter_error("0"))
        self.assertFalse(_is_counter_error("1"))
        self.assertFalse(_is_counter_error("1000"))
        self.assertFalse(_is_counter_error(0))
        self.assertFalse(_is_counter_error(500))


class MergeSnmpWebDataTests(SimpleTestCase):
    """Тесты объединения данных SNMP и Web."""

    def _snmp_data(self, **overrides):
        """Базовые SNMP данные для тестов."""
        base = {
            "CONTENT": {
                "DEVICE": {
                    "INFO": {
                        "SERIAL": "SN123",
                        "MAC": "AA:BB:CC:DD:EE:FF",
                        "MANUFACTURER": "HP",
                        "MODEL": "LaserJet Pro",
                    },
                    "PAGECOUNTERS": {
                        "TOTAL": "10000",
                        "BW_A4": "8000",
                        "BW_A3": "2000",
                    },
                    "CARTRIDGES": {
                        "TONERBLACK": "50%",
                        "TONERCYAN": "30%",
                    },
                }
            }
        }
        if overrides:

            def deep_update(target, updates):
                """Глубокое слияние для вложенных словарей."""
                for k, v in updates.items():
                    if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                        deep_update(target[k], v)
                    else:
                        target[k] = v

            deep_update(base, overrides)
        return base

    def test_successful_merge_with_no_conflicts(self):
        """Успешное объединение без конфликтов."""
        snmp = self._snmp_data()
        web = {"toner_yellow": "40%", "drum_black": "OK"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertIn("toner_black", merged)  # Из SNMP
        self.assertIn("toner_yellow", merged)  # Из Web
        self.assertEqual(merged["toner_black"], "50%")
        self.assertEqual(merged["toner_yellow"], "40%")

    def test_both_sources_give_error_considered_consistent(self):
        """Оба источника дают ошибку → считаются согласованными."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERBLACK"] = "0"
        web = {"toner_black": "ERROR"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        # Web имеет приоритет
        self.assertEqual(merged["toner_black"], "ERROR")

    def test_different_error_formats_considered_consistent(self):
        """Разные форматы ошибок считаются согласованными."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERBLACK"] = "0"
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERCYAN"] = "--"
        web = {"toner_black": "Replace Cartridge", "toner_cyan": "WARNING"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success, f"Should succeed with error formats, got: {error}")
        self.assertEqual(merged["toner_black"], "Replace Cartridge")
        self.assertEqual(merged["toner_cyan"], "WARNING")

    def test_both_normal_but_different_values_fails(self):
        """Оба источника дают нормальные, но разные значения → ошибка."""
        snmp = self._snmp_data()
        web = {"toner_black": "45%"}  # SNMP дал "50%"

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertFalse(success)
        self.assertIn("toner_black", error)
        self.assertIn("50%", error)
        self.assertIn("45%", error)

    def test_serial_number_mismatch_fails(self):
        """Серийник должен совпадать точно."""
        snmp = self._snmp_data()
        web = {"serial_number": "DIFFERENT"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertFalse(success)
        self.assertIn("serial_number", error)

    def test_mac_address_mismatch_fails(self):
        """MAC-адрес должен совпадать точно."""
        snmp = self._snmp_data()
        web = {"mac_address": "00:11:22:33:44:55"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertFalse(success)
        self.assertIn("mac_address", error)

    def test_counter_both_errors_considered_consistent(self):
        """Счётчики: оба источника дают ошибку → согласованы."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["PAGECOUNTERS"]["TOTAL"] = "ERROR"
        web = {"counter": "0"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)

    def test_counter_mismatch_fails(self):
        """Счётчики: разные нормальные значения → ошибка."""
        snmp = self._snmp_data()
        web = {"counter": "9999"}  # SNMP дал "10000"

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertFalse(success)
        self.assertIn("counter", error)

    def test_web_priority_over_snmp(self):
        """Web имеет приоритет при объединении (когда SNMP даёт ошибку)."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERBLACK"] = "0"  # SNMP ошибка
        web = {"toner_black": "75%", "toner_yellow": "25%"}  # Web нормальное

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertEqual(merged["toner_black"], "75%")  # Web перезаписал SNMP ошибку
        self.assertEqual(merged["toner_yellow"], "25%")  # Web добавил

    def test_empty_snmp_data_handled(self):
        """Пустой SNMP данные обрабатываются корректно."""
        snmp = {}
        web = {"serial_number": "SN123", "mac_address": "AA:BB:CC:DD:EE:FF"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertEqual(merged["serial_number"], "SN123")

    def test_empty_web_data_only_snmp_used(self):
        """Пустой Web данные → используется только SNMP."""
        snmp = self._snmp_data()
        web = {}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertEqual(merged["serial_number"], "SN123")
        self.assertEqual(merged["toner_black"], "50%")

    def test_both_error_formats_dashes_considered_consistent(self):
        """Разные форматы с '--' считаются согласованными."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERBLACK"] = "--"
        web = {"toner_black": "----"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)

    def test_one_valid_one_error_takes_valid(self):
        """Один источник даёт нормальное значение, другой ошибку → берём нормальное."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"]["TONERBLACK"] = "0"  # Ошибка
        web = {"toner_black": "50%"}  # Нормальное

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertEqual(merged["toner_black"], "50%")  # Web перезаписал SNMP ошибку

    def test_all_color_cartridges_error_variations(self):
        """Все цветные картриджи с разными форматами ошибок."""
        snmp = self._snmp_data()
        snmp["CONTENT"]["DEVICE"]["CARTRIDGES"] = {
            "TONERBLACK": "50%",
            "TONERCYAN": "0",
            "TONERMAGENTA": "WARNING",
            "TONERYELLOW": "--",
        }
        web = {
            "toner_black": "50%",
            "toner_cyan": "ERROR",
            "toner_magenta": "Replace",
            "toner_yellow": "Low",
        }

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        # toner_black совпали
        self.assertEqual(merged["toner_black"], "50%")
        # Цветные с ошибками — Web перезаписал (приоритет)
        self.assertEqual(merged["toner_cyan"], "ERROR")

    def test_snmp_missing_cartridges_dict(self):
        """CARTRIDGES может отсутствовать в SNMP данных."""
        snmp = {
            "CONTENT": {
                "DEVICE": {
                    "INFO": {"SERIAL": "SN123"},
                    "PAGECOUNTERS": {"TOTAL": "1000"},
                    # Нет CARTRIDGES
                }
            }
        }
        web = {"toner_black": "75%"}

        success, merged, error = _merge_snmp_web_data(snmp, web, "10.0.0.1")

        self.assertTrue(success)
        self.assertEqual(merged["toner_black"], "75%")
