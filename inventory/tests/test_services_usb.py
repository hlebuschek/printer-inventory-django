from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer
from inventory.models import InventoryTask, Organization, PageCounter, Printer, USBAgent
from inventory.services_usb import (
    USBReadingError,
    _extract_counters,
    _parse_timestamp,
    hash_token,
    process_usb_reading,
    register_or_get_agent,
)


def _iso(dt):
    return dt.isoformat()


class HashTokenTests(SimpleTestCase):
    def test_deterministic_sha256_hex(self):
        self.assertEqual(hash_token("secret"), hash_token("secret"))
        self.assertEqual(len(hash_token("secret")), 64)

    def test_different_inputs_differ(self):
        self.assertNotEqual(hash_token("a"), hash_token("b"))


class ParseTimestampTests(SimpleTestCase):
    def test_empty_raises(self):
        with self.assertRaises(USBReadingError):
            _parse_timestamp("")

    def test_invalid_raises(self):
        with self.assertRaises(USBReadingError):
            _parse_timestamp("not-a-date")

    def test_naive_made_aware(self):
        ts = _parse_timestamp("2026-01-01T10:00:00")
        self.assertFalse(timezone.is_naive(ts))


class ExtractCountersTests(SimpleTestCase):
    def test_non_dict_returns_empty(self):
        self.assertEqual(_extract_counters("nope"), {})

    def test_only_known_keys_and_ints(self):
        result = _extract_counters({"total_pages": "100", "bw_a4": 50, "unknown": 9})
        self.assertEqual(result, {"total_pages": 100, "bw_a4": 50})

    def test_non_integer_raises(self):
        with self.assertRaises(USBReadingError):
            _extract_counters({"total_pages": "abc"})


class ProcessUsbReadingErrorPathsTests(SimpleTestCase):
    """Ветки, отсекаемые до обращения к БД."""

    def setUp(self):
        self.agent = SimpleNamespace(agent_id="agent-1")

    def test_empty_serial(self):
        res = process_usb_reading(self.agent, {"serial_number": {"value": ""}})
        self.assertEqual(res["status"], "error")
        self.assertIn("serial_number", res["error"])

    def test_bad_timestamp(self):
        res = process_usb_reading(self.agent, {"serial_number": {"value": "SN1"}, "timestamp": "bad"})
        self.assertEqual(res["status"], "error")

    def test_replay_window(self):
        old = timezone.now() - timedelta(hours=100)
        res = process_usb_reading(
            self.agent,
            {"serial_number": {"value": "SN1"}, "timestamp": _iso(old), "counters": {"total_pages": 10}},
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("replay", res["error"])

    def test_future_timestamp(self):
        future = timezone.now() + timedelta(hours=1)
        res = process_usb_reading(
            self.agent,
            {"serial_number": {"value": "SN1"}, "timestamp": _iso(future), "counters": {"total_pages": 10}},
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("future", res["error"])

    def test_no_counters(self):
        now = timezone.now()
        res = process_usb_reading(
            self.agent,
            {"serial_number": {"value": "SN1"}, "timestamp": _iso(now), "counters": {}},
        )
        self.assertEqual(res["status"], "error")
        self.assertIn("no counters", res["error"])


class ProcessUsbReadingDbTests(TestCase):
    def setUp(self):
        self.agent = SimpleNamespace(agent_id="agent-1")
        self.org = Organization.objects.create(name="Org A")
        self.city = City.objects.create(name="Иркутск")
        self.mfr = Manufacturer.objects.create(name="HP")
        self.model = DeviceModel.objects.create(manufacturer=self.mfr, name="LaserJet")
        self.status = ContractStatus.objects.create(name="Активен")

    def _reading(self, serial, **counters):
        return {
            "serial_number": {"value": serial},
            "timestamp": _iso(timezone.now()),
            "counters": counters or {"total_pages": 100},
            "model": "LaserJet",
        }

    def test_serial_not_in_contracts_errors(self):
        res = process_usb_reading(self.agent, self._reading("UNKNOWN-SN"))
        self.assertEqual(res["status"], "error")
        self.assertIn("не найден", res["error"])

    def test_auto_creates_printer_and_counter(self):
        ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина 1",
            model=self.model,
            status=self.status,
            serial_number="USB-SN-1",
        )
        res = process_usb_reading(self.agent, self._reading("USB-SN-1", total_pages=500, bw_a4=500))
        self.assertEqual(res["status"], "success")
        printer = Printer.objects.get(serial_number="USB-SN-1")
        self.assertEqual(printer.connection_type, "USB")
        task = InventoryTask.objects.get(pk=res["task_id"])
        self.assertEqual(task.status, "SUCCESS")
        self.assertEqual(PageCounter.objects.get(task=task).total_pages, 500)


class RegisterOrGetAgentTests(TestCase):
    KEY = "master-key"

    def test_missing_expected_key_raises(self):
        with self.assertRaises(USBReadingError):
            register_or_get_agent(self.KEY, "", "a1", "host", "1.0")

    def test_wrong_key_raises(self):
        with self.assertRaises(USBReadingError):
            register_or_get_agent("wrong", self.KEY, "a1", "host", "1.0")

    def test_empty_agent_id_raises(self):
        with self.assertRaises(USBReadingError):
            register_or_get_agent(self.KEY, self.KEY, "", "host", "1.0")

    def test_new_agent_created_with_hashed_token(self):
        agent, plaintext = register_or_get_agent(self.KEY, self.KEY, "a1", "host", "1.0")
        self.assertIsNotNone(plaintext)
        self.assertEqual(agent.token_hash, hash_token(plaintext))
        self.assertTrue(agent.is_active)

    def test_existing_agent_rotates_token(self):
        agent, first = register_or_get_agent(self.KEY, self.KEY, "a1", "host", "1.0")
        old_hash = agent.token_hash
        agent2, second = register_or_get_agent(self.KEY, self.KEY, "a1", "host", "1.1")
        self.assertEqual(agent.pk, agent2.pk)
        self.assertNotEqual(first, second)
        self.assertNotEqual(old_hash, agent2.token_hash)
        self.assertEqual(agent2.agent_version, "1.1")

    def test_deactivated_agent_raises(self):
        USBAgent.objects.create(agent_id="a1", token_hash=hash_token("x"), is_active=False)
        with self.assertRaises(USBReadingError):
            register_or_get_agent(self.KEY, self.KEY, "a1", "host", "1.0")
