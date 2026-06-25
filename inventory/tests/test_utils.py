from django.test import SimpleTestCase

from inventory.utils import (
    extract_mac_address,
    extract_page_counters,
    mac_equal,
    normalize_mac,
    validate_inventory,
)


def _device(**device):
    return {"CONTENT": {"DEVICE": device}}


class NormalizeMacTests(SimpleTestCase):
    def test_plain_hex(self):
        self.assertEqual(normalize_mac("aabbccddeeff"), "AA:BB:CC:DD:EE:FF")

    def test_colon_separated(self):
        self.assertEqual(normalize_mac("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")

    def test_dash_separated_uppercased(self):
        self.assertEqual(normalize_mac("AA-BB-CC-DD-EE-FF"), "AA:BB:CC:DD:EE:FF")

    def test_too_short_returns_none(self):
        self.assertIsNone(normalize_mac("aabbcc"))

    def test_too_long_returns_none(self):
        self.assertIsNone(normalize_mac("aabbccddeeff00"))

    def test_empty_and_none(self):
        self.assertIsNone(normalize_mac(""))
        self.assertIsNone(normalize_mac(None))


class MacEqualTests(SimpleTestCase):
    def test_equal_across_formats(self):
        self.assertTrue(mac_equal("aabbccddeeff", "AA:BB:CC:DD:EE:FF"))

    def test_not_equal(self):
        self.assertFalse(mac_equal("aabbccddeeff", "aabbccddee00"))

    def test_none_is_never_equal(self):
        self.assertFalse(mac_equal(None, "AA:BB:CC:DD:EE:FF"))
        self.assertFalse(mac_equal("AA:BB:CC:DD:EE:FF", None))


class ExtractMacAddressTests(SimpleTestCase):
    def test_prefers_ethernet_port(self):
        data = _device(
            PORTS={
                "PORT": [
                    {"IFDESCR": "Loopback", "MAC": "00:00:00:00:00:01"},
                    {"IFDESCR": "Gigabit Ethernet", "MAC": "aa:bb:cc:dd:ee:ff"},
                ]
            }
        )
        self.assertEqual(extract_mac_address(data), "AA:BB:CC:DD:EE:FF")

    def test_falls_back_to_info_mac(self):
        data = _device(INFO={"MAC": "aa:bb:cc:dd:ee:ff"}, PORTS={"PORT": []})
        self.assertEqual(extract_mac_address(data), "AA:BB:CC:DD:EE:FF")

    def test_single_port_as_dict(self):
        data = _device(PORTS={"PORT": {"IFNAME": "eth0", "MAC": "aa:bb:cc:dd:ee:ff"}})
        self.assertEqual(extract_mac_address(data), "AA:BB:CC:DD:EE:FF")

    def test_no_mac_returns_none(self):
        self.assertIsNone(extract_mac_address(_device(PORTS={"PORT": []})))


class ValidateInventoryTests(SimpleTestCase):
    def test_serial_and_mac_match(self):
        data = _device(
            INFO={"SERIAL": "SN123"},
            PORTS={"PORT": {"IFDESCR": "eth", "MAC": "aabbccddeeff"}},
        )
        ok, err, rule = validate_inventory(data, "10.0.0.1", "SN123", "aa:bb:cc:dd:ee:ff")
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(rule, "SN_MAC")

    def test_mac_only_when_serial_differs(self):
        data = _device(
            INFO={"SERIAL": "OTHER"},
            PORTS={"PORT": {"IFDESCR": "eth", "MAC": "aabbccddeeff"}},
        )
        ok, _, rule = validate_inventory(data, "10.0.0.1", "SN123", "aa:bb:cc:dd:ee:ff")
        self.assertTrue(ok)
        self.assertEqual(rule, "MAC_ONLY")

    def test_serial_only_when_no_expected_mac(self):
        data = _device(INFO={"SERIAL": "SN123"}, PORTS={"PORT": []})
        ok, _, rule = validate_inventory(data, "10.0.0.1", "SN123")
        self.assertTrue(ok)
        self.assertEqual(rule, "SN_ONLY")

    def test_full_mismatch(self):
        data = _device(
            INFO={"SERIAL": "OTHER"},
            PORTS={"PORT": {"IFDESCR": "eth", "MAC": "001122334455"}},
        )
        ok, err, rule = validate_inventory(data, "10.0.0.1", "SN123", "aa:bb:cc:dd:ee:ff")
        self.assertFalse(ok)
        self.assertIsNone(rule)
        self.assertIn("SN123", err)


class ExtractPageCountersTests(SimpleTestCase):
    def test_mono_printer_total_goes_to_bw_a4(self):
        data = _device(PAGECOUNTERS={"TOTAL": "1000"})
        result = extract_page_counters(data)
        self.assertEqual(result["bw_a4"], 1000)
        self.assertEqual(result["bw_a3"], 0)
        self.assertEqual(result["color_a4"], 0)
        self.assertEqual(result["total_pages"], 1000)

    def test_color_counters_detected_as_color(self):
        data = _device(PAGECOUNTERS={"TOTAL": "500", "COLOR_A4": "200", "BW_A4": "300"})
        result = extract_page_counters(data)
        self.assertEqual(result["bw_a4"], 0)
        self.assertEqual(result["color_a4"], 500)
        self.assertEqual(result["total_pages"], 500)

    def test_color_supplies_force_color_classification(self):
        data = _device(
            PAGECOUNTERS={"TOTAL": "400", "BW_A4": "400"},
            CARTRIDGES={"TONERCYAN": "80"},
        )
        result = extract_page_counters(data)
        self.assertEqual(result["bw_a4"], 0)
        self.assertEqual(result["color_a4"], 400)

    def test_supply_levels_extracted_and_truncated(self):
        data = _device(
            PAGECOUNTERS={"TOTAL": "10"},
            CARTRIDGES={"TONERBLACK": "x" * 30, "DRUMBLACK": "50"},
        )
        result = extract_page_counters(data)
        self.assertEqual(len(result["toner_black"]), 20)
        self.assertEqual(result["drum_black"], "50")

    def test_invalid_counter_value_ignored(self):
        data = _device(PAGECOUNTERS={"TOTAL": "not-a-number"})
        result = extract_page_counters(data)
        self.assertEqual(result["total_pages"], 0)
