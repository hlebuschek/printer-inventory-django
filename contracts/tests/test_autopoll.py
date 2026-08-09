from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from contracts.models import (
    AutoPollCandidate,
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    ImportFile,
    ImportRow,
    ImportSession,
    Manufacturer,
)
from contracts.services_autopoll import can_create, collect_devices, create_printers, probe_session, verify_candidate
from inventory.models import Organization, Printer


def probe_result(status, ip="10.99.0.11", printer_id=1, counter=100, age_hours=1):
    return {
        "status": status,
        "glpi_printer_id": printer_id,
        "glpi_name": "printer-01",
        "glpi_counter": counter,
        "glpi_date": timezone.now() - timedelta(hours=age_hours),
        "glpi_state": "",
        "glpi_ip": ip,
        "error": "",
    }


class AutoPollBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.city = City.objects.create(name="Иркутск")
        self.manufacturer = Manufacturer.objects.create(name="Sindoh")
        self.model = DeviceModel.objects.create(manufacturer=self.manufacturer, name="D332e", has_network_port=True)
        self.usb_model = DeviceModel.objects.create(manufacturer=self.manufacturer, name="D200", has_network_port=False)
        self.status = ContractStatus.objects.create(name="На обслуживании")
        self.session = ImportSession.objects.create(target_status=self.status, state=ImportSession.APPLIED)
        self.file = ImportFile.objects.create(session=self.session, original_name="f.xlsx")

    def add_device(self, serial, model=None, printer=None):
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина, д. 1",
            model=model or self.model,
            serial_number=serial,
            status=self.status,
            printer=printer,
        )
        ImportRow.objects.create(
            session=self.session,
            file=self.file,
            row_number=ContractDevice.objects.count(),
            raw={"serial": serial},
            sn_lower=serial.lower(),
            applied_device=device,
        )
        return device


class CollectDevicesTests(AutoPollBase):
    def test_only_network_devices_without_active_printer(self):
        wanted = self.add_device("SN-NET")
        self.add_device("SN-USB", model=self.usb_model)

        printer = Printer.objects.create(
            ip_address="10.0.0.5", serial_number="SN-LINKED", snmp_community="public", organization=self.org
        )
        self.add_device("SN-LINKED", printer=printer)

        self.assertEqual([d.id for d in collect_devices(self.session)], [wanted.id])

    def test_serial_already_known_to_inventory_is_skipped(self):
        Printer.objects.create(
            ip_address="10.0.0.6", serial_number="SN-NET", snmp_community="public", organization=self.org
        )
        self.add_device("SN-NET")

        self.assertEqual(collect_devices(self.session), [])

    def test_serial_matched_ignoring_case(self):
        Printer.objects.create(
            ip_address="10.0.0.8", serial_number="sn-net", snmp_community="public", organization=self.org
        )
        self.add_device("SN-NET")

        self.assertEqual(collect_devices(self.session), [])

    def test_inactive_printer_does_not_block(self):
        printer = Printer.objects.create(
            ip_address="10.0.0.7",
            serial_number="SN-OLD",
            snmp_community="public",
            organization=self.org,
            is_active=False,
        )
        device = self.add_device("SN-OLD", printer=printer)

        self.assertEqual([d.id for d in collect_devices(self.session)], [device.id])


class ProbeSessionTests(AutoPollBase):
    def _run(self, side_effect):
        with (
            patch("contracts.services_autopoll.GLPIClient"),
            patch("contracts.services_autopoll.probe_serial_in_glpi", side_effect=side_effect),
        ):
            return probe_session(self.session)

    def test_fresh_device_with_ip_becomes_active_candidate(self):
        self.add_device("SN-NET")
        stats = self._run(lambda *a, **kw: probe_result("GLPI_ACTIVE"))

        candidate = self.session.autopoll_candidates.get()
        self.assertEqual(candidate.status, AutoPollCandidate.GLPI_ACTIVE)
        self.assertEqual(candidate.glpi_ip, "10.99.0.11")
        self.assertEqual(stats[AutoPollCandidate.GLPI_ACTIVE], 1)

    def test_device_without_ip_in_glpi(self):
        self.add_device("SN-NET")
        self._run(lambda *a, **kw: probe_result("GLPI_ACTIVE", ip=None))

        self.assertEqual(self.session.autopoll_candidates.get().status, AutoPollCandidate.NO_IP)

    def test_busy_ip_gives_conflict(self):
        Printer.objects.create(
            ip_address="10.99.0.11", serial_number="OTHER", snmp_community="public", organization=self.org
        )
        self.add_device("SN-NET")
        self._run(lambda *a, **kw: probe_result("GLPI_ACTIVE"))

        candidate = self.session.autopoll_candidates.get()
        self.assertEqual(candidate.status, AutoPollCandidate.IP_CONFLICT)
        self.assertFalse(can_create(candidate)[0])

    def test_probe_exception_is_recorded_per_device(self):
        self.add_device("SN-NET")
        self._run(lambda *a, **kw: 1 / 0)

        candidate = self.session.autopoll_candidates.get()
        self.assertEqual(candidate.status, AutoPollCandidate.ERROR)
        self.assertIn("ZeroDivisionError", candidate.error)

    def test_reprobe_keeps_already_created_candidates(self):
        device = self.add_device("SN-NET")
        printer = Printer.objects.create(
            ip_address="10.99.0.99", serial_number="SN-NET", snmp_community="public", organization=self.org
        )
        AutoPollCandidate.objects.create(
            session=self.session,
            contract_device=device,
            serial_number="SN-NET",
            status=AutoPollCandidate.GLPI_ACTIVE,
            created_printer=printer,
        )

        self._run(lambda *a, **kw: probe_result("GLPI_ACTIVE"))

        candidate = self.session.autopoll_candidates.get()
        self.assertEqual(candidate.created_printer_id, printer.id)


class CreatePrintersTests(AutoPollBase):
    def make_candidate(self, status=AutoPollCandidate.GLPI_ACTIVE, **kwargs):
        device = self.add_device(kwargs.pop("serial", "SN-NET"))
        return AutoPollCandidate.objects.create(
            session=self.session,
            contract_device=device,
            serial_number=device.serial_number,
            status=status,
            glpi_printer_id=1,
            glpi_ip=kwargs.pop("glpi_ip", "10.99.0.11"),
            **kwargs,
        )

    def test_creates_printer_links_device_and_starts_poll(self):
        candidate = self.make_candidate()

        with patch("inventory.tasks.run_inventory_task_priority.delay") as delay:
            results = create_printers([candidate], user=None)

        self.assertTrue(results[0]["created"])
        printer = Printer.objects.get(serial_number="SN-NET")
        self.assertEqual(printer.ip_address, "10.99.0.11")
        self.assertEqual(printer.device_model, self.model)
        self.assertEqual(printer.organization, self.org)
        self.assertEqual(candidate.contract_device.printer_id, printer.id)
        delay.assert_called_once_with(printer.id, None)

    def test_stale_candidate_needs_successful_verification(self):
        candidate = self.make_candidate(status=AutoPollCandidate.GLPI_STALE)

        with patch("inventory.tasks.run_inventory_task_priority.delay") as delay:
            results = create_printers([candidate], user=None)

        self.assertFalse(results[0]["created"])
        self.assertFalse(Printer.objects.exists())
        delay.assert_not_called()

        candidate.verify_ok = True
        candidate.save(update_fields=["verify_ok"])
        with patch("inventory.tasks.run_inventory_task_priority.delay"):
            results = create_printers([candidate], user=None)

        self.assertTrue(results[0]["created"])

    def test_ip_taken_between_probe_and_create(self):
        candidate = self.make_candidate()
        Printer.objects.create(
            ip_address="10.99.0.11", serial_number="OTHER", snmp_community="public", organization=self.org
        )

        with patch("inventory.tasks.run_inventory_task_priority.delay"):
            results = create_printers([candidate], user=None)

        candidate.refresh_from_db()
        self.assertFalse(results[0]["created"])
        self.assertEqual(candidate.status, AutoPollCandidate.IP_CONFLICT)


class VerifyCandidateTests(AutoPollBase):
    def make_candidate(self):
        device = self.add_device("SN-NET")
        return AutoPollCandidate.objects.create(
            session=self.session,
            contract_device=device,
            serial_number="SN-NET",
            status=AutoPollCandidate.GLPI_STALE,
            glpi_ip="10.99.0.11",
        )

    def test_matching_serial_marks_verified(self):
        candidate = self.make_candidate()
        with (
            patch("inventory.services.run_discovery_for_ip", return_value=(True, "/tmp/x.xml")),
            patch(
                "inventory.services.extract_device_info_from_xml",
                return_value={"serial": "sn-net", "manufacturer": "Sindoh", "model": "D332e"},
            ),
        ):
            verify_candidate(candidate)

        self.assertTrue(candidate.verify_ok)
        self.assertTrue(can_create(candidate)[0])

    def test_other_device_on_ip_is_rejected(self):
        candidate = self.make_candidate()
        with (
            patch("inventory.services.run_discovery_for_ip", return_value=(True, "/tmp/x.xml")),
            patch("inventory.services.extract_device_info_from_xml", return_value={"serial": "SOMETHING-ELSE"}),
        ):
            verify_candidate(candidate)

        self.assertFalse(candidate.verify_ok)
        self.assertIn("SOMETHING-ELSE", candidate.verify_message)

    def test_no_answer_is_rejected(self):
        candidate = self.make_candidate()
        with patch("inventory.services.run_discovery_for_ip", return_value=(False, "timeout")):
            verify_candidate(candidate)

        self.assertFalse(candidate.verify_ok)
        self.assertFalse(can_create(candidate)[0])
