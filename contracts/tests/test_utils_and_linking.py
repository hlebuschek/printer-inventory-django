from django.http import Http404
from django.test import SimpleTestCase, TestCase

from contracts.models import (
    Cartridge,
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    DeviceModelCartridge,
    Manufacturer,
    ServiceProvider,
)
from contracts.services_linking import link_all_unlinked_devices
from contracts.utils import SupportEmailNotConfigured, generate_email_for_device
from inventory.models import Organization, Printer


class GenerateEmailArgValidationTests(SimpleTestCase):
    def test_requires_device_id_or_serial(self):
        with self.assertRaises(ValueError):
            generate_email_for_device()


class GenerateEmailForDeviceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.city = City.objects.create(name="Иркутск")
        self.mfr = Manufacturer.objects.create(name="Kyocera")
        self.model = DeviceModel.objects.create(manufacturer=self.mfr, name="ECOSYS M2040")
        self.status = ContractStatus.objects.create(name="Активен")
        self.amb = ServiceProvider.objects.create(
            name="АМБ", code="amb", issue_tracker=ServiceProvider.OKDESK, support_email="sd@abi.com.ru"
        )
        self.device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина 1",
            model=self.model,
            status=self.status,
            serial_number="SN-CART-1",
            service_provider=self.amb,
        )
        cartridge = Cartridge.objects.create(name="TK-1170", part_number="1T02S50NL0")
        DeviceModelCartridge.objects.create(device_model=self.model, cartridge=cartridge, is_primary=True)

    def _body(self, response):
        import email

        raw = b"".join(response.streaming_content)
        msg = email.message_from_bytes(raw)
        parts = []
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload:
                parts.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(parts)

    def _headers(self, response):
        import email

        return email.message_from_bytes(b"".join(response.streaming_content))

    def test_by_device_id_contains_data(self):
        response = generate_email_for_device(device_id=self.device.id)
        body = self._body(response)
        self.assertIn("SN-CART-1", body)
        self.assertIn("TK-1170", body)
        self.assertEqual(response["Content-Type"], "message/rfc822")

    def test_recipient_taken_from_provider(self):
        self.amb.support_email = "desk@amb.example"
        self.amb.save(update_fields=["support_email"])

        response = generate_email_for_device(device_id=self.device.id)

        self.assertEqual(self._headers(response)["To"], "desk@amb.example")

    def test_provider_without_email_refuses(self):
        tonex = ServiceProvider.objects.create(name="Tonex", code="tonex", issue_tracker=ServiceProvider.NONE)
        self.device.service_provider = tonex
        self.device.save(update_fields=["service_provider"])

        with self.assertRaises(SupportEmailNotConfigured):
            generate_email_for_device(device_id=self.device.id)

    def test_by_serial_number(self):
        response = generate_email_for_device(serial_number="sn-cart-1")
        self.assertIn("SN-CART-1", self._body(response))

    def test_unknown_serial_raises_404(self):
        with self.assertRaises(Http404):
            generate_email_for_device(serial_number="DOES-NOT-EXIST")


class LinkAllUnlinkedDevicesTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org L")
        self.city = City.objects.create(name="Иркутск")
        self.mfr = Manufacturer.objects.create(name="HP")
        self.model = DeviceModel.objects.create(manufacturer=self.mfr, name="M1")
        self.status = ContractStatus.objects.create(name="Активен")

    def _device(self, serial):
        return ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="addr",
            model=self.model,
            status=self.status,
            serial_number=serial,
        )

    def _printer(self, ip, serial):
        return Printer.objects.create(ip_address=ip, serial_number=serial, snmp_community="public")

    def test_no_devices(self):
        stats = link_all_unlinked_devices()
        self.assertEqual(stats["total_devices"], 0)

    def test_links_by_serial_case_insensitive(self):
        device = self._device("SN-100")
        printer = self._printer("10.0.0.1", "sn-100")
        stats = link_all_unlinked_devices()
        self.assertEqual(stats["linked"], 1)
        device.refresh_from_db()
        self.assertEqual(device.printer_id, printer.id)

    def test_serial_without_printer_not_found(self):
        self._device("SN-200")
        stats = link_all_unlinked_devices()
        self.assertEqual(stats["linked"], 0)
        self.assertEqual(stats["not_found"], 1)

    def test_already_linked_device_skipped(self):
        printer = self._printer("10.0.0.2", "SN-300")
        device = self._device("SN-300")
        device.printer = printer
        device.save(update_fields=["printer"])
        stats = link_all_unlinked_devices()
        self.assertEqual(stats["total_devices"], 0)
