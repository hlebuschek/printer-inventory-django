from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone

from inventory.models import DiscoveredDevice, NetworkScanRun, Printer, ScanNetwork
from inventory.services_netscan import finish_run, reconcile_device, scan_chunk, start_run
from inventory.services_netscan_glpi import check_batch, probe_device, start_check

from .test_netscan import MAC_A, MAC_B, ReconcileBase, found

MAC_C = "AA:BB:CC:00:00:03"


@patch("inventory.services_netscan._queue_poll")
class DuplicateSerialTests(ReconcileBase):
    def test_same_serial_two_macs_kept_apart_and_no_auto_actions(self, poll):
        self.add_device("SAME")  # в договоре — но заводить нельзя: не понять, какое из устройств
        r1 = reconcile_device(self.network, found("10.1.2.10", "SAME", MAC_A))
        self.assertEqual(r1.status, DiscoveredDevice.ADDED)  # пока он один — обычный путь
        Printer.objects.all().delete()

        r2 = reconcile_device(self.network, found("10.1.2.11", "SAME", MAC_B))
        r3 = reconcile_device(self.network, found("10.1.2.12", "same", MAC_C))

        records = DiscoveredDevice.objects.filter(network=self.network).order_by("ip_address")
        self.assertEqual(records.count(), 3)  # не схлопнулись в одну запись
        self.assertEqual({r.status for r in records}, {DiscoveredDevice.DUPLICATE_SERIAL})
        self.assertEqual(r2.status, DiscoveredDevice.DUPLICATE_SERIAL)
        self.assertIn("перепрошивка", r3.message)
        self.assertFalse(Printer.objects.exists())

    def test_duplicate_does_not_match_polled_printer_by_serial(self, poll):
        printer = self.add_printer("10.1.2.10", "SAME", MAC_A)
        reconcile_device(self.network, found("10.1.2.10", "SAME", MAC_A))
        record = reconcile_device(self.network, found("10.1.2.20", "SAME", MAC_B))
        self.assertEqual(record.status, DiscoveredDevice.DUPLICATE_SERIAL)
        self.assertIsNone(record.printer)
        printer.refresh_from_db()
        self.assertEqual(printer.ip_address, "10.1.2.10")  # никаких переносов IP
        own = DiscoveredDevice.objects.get(mac_address=MAC_A)
        self.assertEqual((own.status, own.printer), (DiscoveredDevice.DUPLICATE_SERIAL, printer))

    def test_same_serial_in_other_network_counts(self, poll):
        other = ScanNetwork.objects.create(name="VLAN 20", cidr="10.1.3.0/24")
        reconcile_device(other, found("10.1.3.10", "SAME", MAC_A))
        record = reconcile_device(self.network, found("10.1.2.10", "SAME", MAC_B))
        self.assertEqual(record.status, DiscoveredDevice.DUPLICATE_SERIAL)
        self.assertEqual(DiscoveredDevice.objects.get(network=other).status, DiscoveredDevice.DUPLICATE_SERIAL)

    def test_new_mac_in_same_network_from_previous_run_is_not_duplicate(self, poll):
        """Заменили сетевую карту: старый MAC отвечал в прошлом прогоне этой же сети — это тот же принтер."""
        reconcile_device(self.network, found("10.1.2.10", "SN1", MAC_A))
        record = reconcile_device(
            self.network, found("10.1.2.10", "SN1", MAC_B), since=timezone.now() + timedelta(seconds=1)
        )
        self.assertEqual(record.status, DiscoveredDevice.NOT_IN_CONTRACT)
        self.assertEqual(DiscoveredDevice.objects.count(), 1)

    @override_settings(NETSCAN_CHUNK_PREFIX=24)
    def test_polled_printer_with_duplicate_serial_not_marked_missing(self, poll):
        self.add_printer("10.1.2.10", "SAME", None)
        run = start_run(self.network)
        devices = [found("10.1.2.10", "SAME", MAC_A), found("10.1.2.11", "SAME", MAC_B)]
        with patch("inventory.services_netscan.run_range_discovery", return_value=(True, devices, "")):
            scan_chunk(run, 0)
        run = finish_run(run)
        self.assertEqual(run.status, NetworkScanRun.SUCCESS)
        self.assertFalse(DiscoveredDevice.objects.filter(status=DiscoveredDevice.MISSING).exists())
        statuses = set(DiscoveredDevice.objects.values_list("status", flat=True))
        self.assertEqual(statuses, {DiscoveredDevice.DUPLICATE_SERIAL})


class FakeGLPI:
    """Минимальный двойник GLPIClient: карточки {id: {serial, macs, ips, log_date, counter, entity}}."""

    def __init__(self, cards, label_serials=None):
        self.cards = cards
        self.label_serials = label_serials or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def search_printer_by_serial(self, serial):
        items = [
            {"2": cid, "5": c["serial"]}
            for cid, c in self.cards.items()
            if serial.lower() in c["serial"].lower() or serial.lower() == self.label_serials.get(cid, "").lower()
        ]
        if not items:
            return "NOT_FOUND", [], None
        return ("FOUND_SINGLE" if len(items) == 1 else "FOUND_MULTIPLE"), items, None

    def search_printer_ids_by_mac(self, mac):
        ids = [cid for cid, c in self.cards.items() if mac.lower() in [m.lower() for m in c.get("macs", [])]]
        if not ids:
            return "NOT_FOUND", [], None
        return ("FOUND_SINGLE" if len(ids) == 1 else "FOUND_MULTIPLE"), ids, None

    def get_printer_ports(self, cid):
        c = self.cards[cid]
        macs = c.get("macs", [])
        ips = c.get("ips", [])
        return [{"mac": m, "ip": ips[i] if i < len(ips) else None} for i, m in enumerate(macs)] or [
            {"mac": "", "ip": ip} for ip in ips
        ]

    def get_printer(self, cid):
        return {"id": cid, "name": f"PRN-{cid}", "entities_id": 5, "last_pages_counter": self.cards[cid].get("counter")}

    def get_entity_name(self, entity_id):
        return "Корень > ГБУЗ Больница"

    def get_printer_log(self, cid):
        c = self.cards[cid]
        if not c.get("log_date"):
            return []
        return [{"date": c["log_date"].strftime("%Y-%m-%d %H:%M:%S"), "total_pages": c.get("counter")}]


class GLPIProbeTests(ReconcileBase):
    def device(self, ip="10.1.2.10", serial="SN1", mac=MAC_A):
        return DiscoveredDevice.objects.create(
            network=self.network,
            identity=f"sn:{serial.lower()}|{mac}",
            ip_address=ip,
            serial_number=serial,
            mac_address=mac,
            status=DiscoveredDevice.NOT_IN_CONTRACT,
            last_seen=timezone.now(),
        )

    def probe(self, cards, device, **kw):
        cutoff = timezone.now() - timedelta(days=7)
        return probe_device(FakeGLPI(cards, **kw), device, cutoff)

    def fresh(self):
        return timezone.localtime() - timedelta(days=1)

    def test_active(self):
        r = self.probe(
            {1: {"serial": "SN1", "macs": [MAC_A], "ips": ["10.1.2.10"], "log_date": self.fresh(), "counter": 500}},
            self.device(),
        )
        self.assertEqual(r["glpi_status"], DiscoveredDevice.GLPI_ACTIVE)
        self.assertEqual(
            (r["glpi_printer_id"], r["glpi_counter"], r["glpi_entity"]), (1, 500, "Корень > ГБУЗ Больница")
        )

    def test_stale_counter(self):
        old = timezone.localtime() - timedelta(days=40)
        r = self.probe({1: {"serial": "SN1", "macs": [MAC_A], "log_date": old, "counter": 500}}, self.device())
        self.assertEqual(r["glpi_status"], DiscoveredDevice.GLPI_STALE)
        self.assertIn("последний опрос", r["glpi_message"])
        r = self.probe({1: {"serial": "SN1", "macs": [MAC_A]}}, self.device(ip="10.1.2.11", serial="SN2", mac=MAC_C))
        self.assertEqual(r["glpi_status"], DiscoveredDevice.GLPI_NOT_FOUND)

    def test_other_ip(self):
        cards = {1: {"serial": "SN1", "macs": [MAC_A], "ips": ["10.9.9.9"], "log_date": self.fresh(), "counter": 5}}
        r = self.probe(cards, self.device())
        self.assertEqual(r["glpi_status"], DiscoveredDevice.GLPI_OTHER_IP)
        self.assertIn("10.9.9.9", r["glpi_message"])

    def test_not_found_by_serial_found_by_mac(self):
        cards = {7: {"serial": "OTHER", "macs": [MAC_A], "ips": ["10.1.2.10"], "log_date": self.fresh(), "counter": 5}}
        r = self.probe(cards, self.device())
        self.assertEqual((r["glpi_status"], r["glpi_printer_id"]), (DiscoveredDevice.GLPI_ACTIVE, 7))
        self.assertIn("MAC", r["glpi_message"])

    def test_label_serial_field(self):
        cards = {3: {"serial": "", "macs": [MAC_B], "log_date": self.fresh(), "counter": 5}}
        r = self.probe(cards, self.device(), label_serials={3: "SN1"})
        self.assertEqual(r["glpi_printer_id"], 3)

    def test_multiple_cards_resolved_by_mac(self):
        cards = {
            1: {"serial": "SAME", "macs": [MAC_B], "log_date": self.fresh(), "counter": 5},
            2: {"serial": "SAME", "macs": [MAC_A], "log_date": self.fresh(), "counter": 9},
        }
        r = self.probe(cards, self.device(serial="SAME"))
        self.assertEqual((r["glpi_status"], r["glpi_printer_id"]), (DiscoveredDevice.GLPI_ACTIVE, 2))
        self.assertIn("серийник + MAC", r["glpi_message"])

        r = self.probe(cards, self.device(ip="10.1.2.11", serial="SAME", mac=MAC_C))
        self.assertEqual(r["glpi_status"], DiscoveredDevice.GLPI_MULTIPLE)

    def test_contains_search_narrowed_to_exact_serial(self):
        cards = {
            1: {"serial": "SN1", "macs": [], "log_date": self.fresh(), "counter": 5},
            2: {"serial": "SN12", "macs": [], "log_date": self.fresh(), "counter": 5},
        }
        r = self.probe(cards, self.device(mac=""))
        self.assertEqual(r["glpi_printer_id"], 1)

    @override_settings(NETSCAN_GLPI_BATCH=2)
    def test_batches_until_done(self):
        for i in range(3):
            self.device(ip=f"10.1.2.{10 + i}", serial=f"SN{i}", mac=f"AA:BB:CC:00:01:0{i}")
        never_answered = DiscoveredDevice.objects.create(
            network=self.network, identity="sn:gone", serial_number="GONE", status=DiscoveredDevice.MISSING
        )
        self.assertTrue(start_check(self.network))
        self.assertFalse(start_check(self.network))  # уже идёт
        cards = {1: {"serial": "SN0", "macs": [], "log_date": self.fresh(), "counter": 5}}
        with patch("integrations.glpi.client.GLPIClient", return_value=FakeGLPI(cards)):
            self.assertTrue(check_batch(self.network))
            self.network.refresh_from_db()
            self.assertEqual((self.network.glpi_check_done, self.network.glpi_check_total), (2, 3))
            self.assertFalse(check_batch(self.network))
        self.network.refresh_from_db()
        self.assertIsNotNone(self.network.glpi_check_finished_at)
        statuses = dict(
            self.network.devices.filter(last_seen__isnull=False).values_list("serial_number", "glpi_status")
        )
        self.assertEqual(statuses, {"SN0": "active", "SN1": "not_found", "SN2": "not_found"})
        never_answered.refresh_from_db()
        self.assertEqual(never_answered.glpi_status, "")


@modify_settings(
    MIDDLEWARE={
        "remove": [
            "mozilla_django_oidc.middleware.SessionRefresh",
            "printer_inventory.middleware.AjaxSessionRefreshMiddleware",
        ]
    }
)
class GLPIViewsTests(ReconcileBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("u", password="p")
        for code in ("access_inventory_app", "manage_network_scan"):
            self.user.user_permissions.add(Permission.objects.get(codename=code))
        self.client.force_login(self.user)

    @patch("inventory.tasks.check_network_glpi_task.apply_async")
    def test_button_queues_check_and_tab_lists_problems(self, apply_async):
        DiscoveredDevice.objects.create(
            network=self.network,
            identity="sn:x",
            ip_address="10.1.2.5",
            serial_number="X",
            status=DiscoveredDevice.NOT_IN_CONTRACT,
            last_seen=timezone.now(),
            glpi_status=DiscoveredDevice.GLPI_STALE,
            glpi_message="последний опрос 01.01.2026",
        )
        DiscoveredDevice.objects.create(
            network=self.network,
            identity="sn:y",
            ip_address="10.1.2.6",
            serial_number="Y",
            status=DiscoveredDevice.OK,
            last_seen=timezone.now(),
            glpi_status=DiscoveredDevice.GLPI_ACTIVE,
        )
        self.client.post(reverse("inventory:netscan_glpi_check", args=[self.network.pk]))
        apply_async.assert_called_once_with((self.network.pk,), queue="netscan")

        status = self.client.get(reverse("inventory:netscan_glpi_status", args=[self.network.pk])).json()
        self.assertTrue(status["running"])
        self.assertEqual(status["total"], 2)

        page = self.client.get(reverse("inventory:netscan_detail", args=[self.network.pk]) + "?tab=glpi_problem")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "последний опрос 01.01.2026")
        self.assertNotContains(page, "10.1.2.6")
        page = self.client.get(reverse("inventory:netscan_detail", args=[self.network.pk]) + "?tab=duplicate_serial")
        self.assertEqual(page.status_code, 200)
