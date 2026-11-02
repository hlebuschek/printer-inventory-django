import os
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase, modify_settings, override_settings
from django.urls import reverse

from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer
from inventory.forms import ScanNetworkForm
from inventory.models import DiscoveredDevice, NetworkScanRun, Organization, Printer, PrinterChangeLog, ScanNetwork
from inventory.services_netscan import finish_run, network_chunks, reconcile_device, scan_chunk, start_run

MAC_A = "AA:BB:CC:00:00:01"
MAC_B = "AA:BB:CC:00:00:02"


def found(ip, serial="", mac="", type_="PRINTER"):
    return {
        "ip": ip,
        "serial": serial,
        "mac": mac,
        "type": type_,
        "manufacturer": "Sindoh",
        "model": "D332e",
        "name": "",
    }


class ChunkTests(TestCase):
    @override_settings(NETSCAN_CHUNK_PREFIX=26)
    def test_24_split_into_four_26_without_network_and_broadcast(self):
        self.assertEqual(
            network_chunks("10.1.2.0/24"),
            [
                ("10.1.2.1", "10.1.2.63"),
                ("10.1.2.64", "10.1.2.127"),
                ("10.1.2.128", "10.1.2.191"),
                ("10.1.2.192", "10.1.2.254"),
            ],
        )

    @override_settings(NETSCAN_CHUNK_PREFIX=26)
    def test_small_network_is_one_chunk(self):
        self.assertEqual(network_chunks("10.1.2.16/28"), [("10.1.2.17", "10.1.2.30")])

    def test_form_normalizes_cidr_and_rejects_huge(self):
        form = ScanNetworkForm(
            data={"name": "A", "cidr": "10.1.2.77/24", "snmp_community": "public", "scan_interval_hours": 24}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cidr"], "10.1.2.0/24")

        form = ScanNetworkForm(
            data={"name": "B", "cidr": "10.0.0.0/8", "snmp_community": "public", "scan_interval_hours": 24}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("cidr", form.errors)


class ReconcileBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.city = City.objects.create(name="Иркутск")
        self.model = DeviceModel.objects.create(
            manufacturer=Manufacturer.objects.create(name="Sindoh"), name="D332e", has_network_port=True
        )
        self.status = ContractStatus.objects.create(name="На обслуживании")
        self.network = ScanNetwork.objects.create(name="VLAN 10", cidr="10.1.2.0/24", snmp_community="public")

    def add_device(self, serial, printer=None, org=None):
        return ContractDevice.objects.create(
            organization=org or self.org,
            city=self.city,
            address="ул. Ленина, д. 1",
            model=self.model,
            serial_number=serial,
            status=self.status,
            printer=printer,
        )

    def add_printer(self, ip, serial, mac=None):
        return Printer.objects.create(
            ip_address=ip, serial_number=serial, mac_address=mac, snmp_community="public", organization=self.org
        )


@patch("inventory.services_netscan._queue_poll")
class ReconcileTests(ReconcileBase):
    def test_same_ip_is_ok(self, _poll):
        self.add_printer("10.1.2.10", "SN1", MAC_A)
        record = reconcile_device(self.network, found("10.1.2.10", "sn1", MAC_A))
        self.assertEqual(record.status, DiscoveredDevice.OK)

    @patch("inventory.services_netscan._device_answers_at", return_value=False)
    def test_moved_with_same_mac_and_old_ip_silent_is_moved(self, answers, poll):
        printer = self.add_printer("10.1.2.10", "SN1", MAC_A)
        record = reconcile_device(self.network, found("10.1.2.20", "SN1", MAC_A))

        self.assertEqual(record.status, DiscoveredDevice.IP_CHANGED)
        printer.refresh_from_db()
        self.assertEqual(printer.ip_address, "10.1.2.20")
        answers.assert_called_once_with("10.1.2.10", "public", "SN1", MAC_A)
        log = PrinterChangeLog.objects.get(printer=printer)
        self.assertEqual((log.action, log.triggered_by), ("ip_change", "net_scan"))
        poll.assert_called_once()

    @patch("inventory.services_netscan._device_answers_at", return_value=False)
    def test_reflashed_serial_matched_by_mac_is_moved(self, _answers, _poll):
        printer = self.add_printer("10.1.2.10", "SN-OLD", MAC_A)
        record = reconcile_device(self.network, found("10.1.2.20", "SN-NEW", MAC_A))
        self.assertEqual(record.status, DiscoveredDevice.IP_CHANGED)
        printer.refresh_from_db()
        self.assertEqual(printer.ip_address, "10.1.2.20")

    @patch("inventory.services_netscan._device_answers_at", return_value=True)
    def test_old_ip_still_answers_is_pending(self, _answers, _poll):
        printer = self.add_printer("10.1.2.10", "SN1", MAC_A)
        record = reconcile_device(self.network, found("10.1.2.20", "SN1", MAC_A))
        self.assertEqual(record.status, DiscoveredDevice.IP_CHANGE_PENDING)
        printer.refresh_from_db()
        self.assertEqual(printer.ip_address, "10.1.2.10")

    @patch("inventory.services_netscan._device_answers_at", return_value=False)
    def test_mac_mismatch_or_missing_is_pending(self, answers, _poll):
        self.add_printer("10.1.2.10", "SN1", MAC_A)
        self.add_printer("10.1.2.11", "SN2", None)

        r1 = reconcile_device(self.network, found("10.1.2.20", "SN1", MAC_B))
        r2 = reconcile_device(self.network, found("10.1.2.21", "SN2", MAC_B))

        self.assertEqual(r1.status, DiscoveredDevice.IP_CHANGE_PENDING)
        self.assertIn("MAC не совпадает", r1.message)
        self.assertEqual(r2.status, DiscoveredDevice.IP_CHANGE_PENDING)
        self.assertIn("нет MAC", r2.message)
        answers.assert_not_called()

    def test_contract_device_is_auto_added(self, poll):
        device = self.add_device("SN-NEW")
        record = reconcile_device(self.network, found("10.1.2.30", "sn-new", MAC_B))

        self.assertEqual(record.status, DiscoveredDevice.ADDED)
        printer = Printer.objects.get(serial_number="sn-new")
        self.assertEqual((printer.ip_address, printer.mac_address), ("10.1.2.30", MAC_B))
        self.assertEqual(printer.organization, self.org)
        device.refresh_from_db()
        self.assertEqual(device.printer, printer)
        poll.assert_called_once_with(printer)

    def test_contract_device_on_busy_ip_is_conflict(self, poll):
        self.add_device("SN-NEW")
        self.add_printer("10.1.2.30", "SN-OTHER", MAC_A)
        record = reconcile_device(self.network, found("10.1.2.30", "SN-NEW", MAC_B))
        self.assertEqual(record.status, DiscoveredDevice.CONFLICT)
        self.assertFalse(Printer.objects.filter(serial_number="SN-NEW").exists())
        poll.assert_not_called()

    def test_ambiguous_serial_uses_network_organizations(self, _poll):
        other = Organization.objects.create(name="ООО Лютик")
        third = Organization.objects.create(name="ООО Василёк")
        self.add_device("SN-DUP")
        self.add_device("SN-DUP", org=other)

        record = reconcile_device(self.network, found("10.1.2.40", "SN-DUP"))
        self.assertEqual(record.status, DiscoveredDevice.CONFLICT)
        self.assertIn("ООО Лютик", record.message)

        # в сети несколько организаций, из спорных — только одна
        self.network.organizations.set([other, third])
        record = reconcile_device(self.network, found("10.1.2.40", "SN-DUP"))
        self.assertEqual(record.status, DiscoveredDevice.ADDED)
        self.assertEqual(Printer.objects.get(serial_number="SN-DUP").organization, other)

    def test_one_vlan_several_organizations_from_contract(self, _poll):
        other = Organization.objects.create(name="ООО Лютик")
        self.add_device("SN-A")
        self.add_device("SN-B", org=other)
        reconcile_device(self.network, found("10.1.2.41", "SN-A"))
        reconcile_device(self.network, found("10.1.2.42", "SN-B"))
        self.assertEqual(Printer.objects.get(serial_number="SN-A").organization, self.org)
        self.assertEqual(Printer.objects.get(serial_number="SN-B").organization, other)

    def test_unknown_printer_is_not_in_contract_and_non_printers_skipped(self, _poll):
        record = reconcile_device(self.network, found("10.1.2.50", "SN-X", MAC_A))
        self.assertEqual(record.status, DiscoveredDevice.NOT_IN_CONTRACT)
        self.assertIsNone(reconcile_device(self.network, found("10.1.2.51", "SW-1", MAC_B, type_="NETWORKING")))
        self.assertIsNone(reconcile_device(self.network, found("10.1.2.52")))

    def test_rescan_updates_same_record(self, _poll):
        reconcile_device(self.network, found("10.1.2.50", "SN-X", MAC_A))
        reconcile_device(self.network, found("10.1.2.60", "SN-X", MAC_A))
        self.assertEqual(DiscoveredDevice.objects.count(), 1)
        self.assertEqual(DiscoveredDevice.objects.get().ip_address, "10.1.2.60")


@override_settings(NETSCAN_CHUNK_PREFIX=25, NETSCAN_MISSING_AFTER=2)
@patch("inventory.services_netscan._queue_poll")
class RunTests(ReconcileBase):
    def scan(self, devices_by_chunk):
        run = start_run(self.network)
        with patch("inventory.services_netscan.run_range_discovery", side_effect=devices_by_chunk):
            for i in range(run.chunks_total):
                scan_chunk(run, i)
        return finish_run(run)

    def test_missing_after_n_scans_and_failed_chunk_not_counted(self, _poll):
        seen = self.add_printer("10.1.2.10", "SN1", MAC_A)
        silent = self.add_printer("10.1.2.20", "SN2", MAC_B)
        in_failed_chunk = self.add_printer("10.1.2.200", "SN3", None)
        ok = [(True, [found("10.1.2.10", "SN1", MAC_A)], ""), (False, [], "timeout")]

        run = self.scan(list(ok))
        self.assertEqual(run.status, NetworkScanRun.SUCCESS)
        self.assertEqual(run.stats["missing"], 0)
        record = DiscoveredDevice.objects.get(printer=silent)
        self.assertEqual(record.missed_scans, 1)

        run = self.scan(list(ok))
        self.assertEqual(run.stats["missing"], 1)
        record.refresh_from_db()
        self.assertEqual((record.status, record.missed_scans), (DiscoveredDevice.MISSING, 2))
        self.assertFalse(DiscoveredDevice.objects.filter(printer=in_failed_chunk).exists())
        self.assertEqual(DiscoveredDevice.objects.get(printer=seen).status, DiscoveredDevice.OK)

        # снова ответил — счётчик сброшен
        self.scan([(True, [found("10.1.2.10", "SN1", MAC_A), found("10.1.2.20", "SN2", MAC_B)], ""), ok[1]])
        record.refresh_from_db()
        self.assertEqual((record.status, record.missed_scans), (DiscoveredDevice.OK, 0))

    def test_parallel_run_not_started(self, _poll):
        self.assertIsNotNone(start_run(self.network))
        self.assertIsNone(start_run(self.network))


# OIDC SessionRefresh без токена в сессии уводит на Keycloak — для тестов страниц он не нужен
@modify_settings(
    MIDDLEWARE={
        "remove": [
            "mozilla_django_oidc.middleware.SessionRefresh",
            "printer_inventory.middleware.AjaxSessionRefreshMiddleware",
        ]
    }
)
class ViewsTests(ReconcileBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("u", password="p")
        for code in ("access_inventory_app", "manage_network_scan"):
            self.user.user_permissions.add(Permission.objects.get(codename=code))
        self.client.force_login(self.user)

    def test_pages_render(self):
        DiscoveredDevice.objects.create(
            network=self.network, identity="sn:x", ip_address="10.1.2.5", serial_number="X", status="not_in_contract"
        )
        for url in (
            reverse("inventory:netscan_list"),
            reverse("inventory:netscan_add"),
            reverse("inventory:netscan_detail", args=[self.network.pk]),
            reverse("inventory:netscan_detail", args=[self.network.pk]) + "?tab=all",
            reverse("inventory:netscan_edit", args=[self.network.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_no_permission_forbidden(self):
        self.user.user_permissions.remove(Permission.objects.get(codename="manage_network_scan"))
        self.assertEqual(self.client.get(reverse("inventory:netscan_list")).status_code, 403)

    @override_settings(NETSCAN_CHUNK_PREFIX=26)
    def test_status_shows_live_progress(self):
        url = reverse("inventory:netscan_run_status", args=[self.network.pk])
        self.assertIsNone(self.client.get(url).json()["run"])

        run = start_run(self.network)
        page = self.client.get(reverse("inventory:netscan_detail", args=[self.network.pk]))
        self.assertContains(page, 'data-running="1"')
        data = self.client.get(url).json()["run"]
        self.assertTrue(data["waiting_for_worker"])
        self.assertEqual((data["addresses_done"], data["addresses_total"]), (0, 254))

        with patch(
            "inventory.services_netscan.run_range_discovery",
            return_value=(True, [found("10.1.2.10", "SN-X", MAC_A)], ""),
        ):
            scan_chunk(run, 0)
        data = self.client.get(url).json()["run"]
        self.assertFalse(data["waiting_for_worker"])
        self.assertEqual((data["chunks_done"], data["addresses_done"]), (1, 63))
        self.assertEqual(data["counts"]["not_in_contract"]["value"], 1)
        self.assertEqual(data["devices"][0]["serial"], "SN-X")
        self.assertEqual(data["status"], "running")

    @patch("inventory.tasks.scan_network_chunk_task.apply_async")
    def test_run_now_queues_first_chunk(self, apply_async):
        self.client.post(reverse("inventory:netscan_run", args=[self.network.pk]))
        run = NetworkScanRun.objects.get()
        apply_async.assert_called_once_with((run.id, 0), queue="netscan")

    @patch("inventory.services_netscan._queue_poll")
    def test_manual_move(self, _poll):
        printer = self.add_printer("10.1.2.10", "SN1", None)
        device = DiscoveredDevice.objects.create(
            network=self.network,
            identity="sn:sn1",
            ip_address="10.1.2.20",
            serial_number="SN1",
            status=DiscoveredDevice.IP_CHANGE_PENDING,
            printer=printer,
        )
        self.client.post(reverse("inventory:netscan_device_move_ip", args=[device.pk]))
        printer.refresh_from_db()
        device.refresh_from_db()
        self.assertEqual(printer.ip_address, "10.1.2.20")
        self.assertEqual(device.status, DiscoveredDevice.IP_CHANGED)
        self.assertEqual(PrinterChangeLog.objects.get(printer=printer).triggered_by, "manual")

    def test_data_migration_created_group_without_bootstrap_roles(self):
        from django.contrib.auth.models import Group

        codes = set(Group.objects.get(name="Сканирование сетей").permissions.values_list("codename", flat=True))
        self.assertEqual(
            codes,
            {
                "access_inventory_app",
                "manage_network_scan",
                "view_scannetwork",
                "add_scannetwork",
                "change_scannetwork",
                "delete_scannetwork",
                "view_networkscanrun",
                "view_discovereddevice",
            },
        )

    def test_bootstrap_roles_creates_separate_netscan_group(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command("bootstrap_roles", stdout=open(os.devnull, "w"))
        group = Group.objects.get(name="Сканирование сетей")
        codes = set(group.permissions.values_list("codename", flat=True))
        self.assertTrue({"manage_network_scan", "access_inventory_app"} <= codes)
        others = Group.objects.exclude(pk=group.pk).filter(permissions__codename="manage_network_scan")
        self.assertFalse(others.exists())

        user = User.objects.create_user("scanner")
        user.groups.add(group)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("inventory:netscan_list")).status_code, 200)
