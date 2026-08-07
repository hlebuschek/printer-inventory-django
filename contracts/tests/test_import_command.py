import tempfile
from pathlib import Path

from openpyxl import Workbook

from django.core.management import CommandError, call_command
from django.test import TestCase

from contracts.models import (
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    ImportSession,
    Manufacturer,
    ServiceProvider,
)
from inventory.models import Organization

HEADER = ["Организация", "Город", "Адрес", "№ кабинета", "Производитель", "Модель оборудования", "Серийный номер"]


class ImportCommandTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.other_org = Organization.objects.create(name="ООО Лютик")
        self.city = City.objects.create(name="Иркутск")
        manufacturer = Manufacturer.objects.create(name="Avision")
        self.model = DeviceModel.objects.create(manufacturer=manufacturer, name="Avision AM4032in")
        self.status = ContractStatus.objects.create(name="На обслуживании")
        self.provider = ServiceProvider.objects.create(name="АМБ", code="amb")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _xlsx(self, rows, name="devices.xlsx"):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(HEADER)
        for row in rows:
            worksheet.append(row)
        path = Path(self.tmp.name) / name
        workbook.save(path)
        return str(path)

    def _row(self, sn, org="ООО Ромашка", city="Иркутск"):
        return [org, city, "ул. Ленина, д. 1", "101", "Avision", "Avision AM4032in", sn]

    def test_creates_devices_with_selected_status(self):
        call_command("contracts_import_xlsx", self._xlsx([self._row("SN-1")]), status="На обслуживании", provider="amb")

        device = ContractDevice.objects.get()
        self.assertEqual(device.serial_number, "SN-1")
        self.assertEqual(device.status, self.status)
        self.assertEqual(device.service_provider, self.provider)
        self.assertEqual(ImportSession.objects.get().state, ImportSession.APPLIED)

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command("contracts_import_xlsx", self._xlsx([self._row("SN-1")]), status="Нет такого", provider="amb")

    def test_dry_run_writes_nothing_and_leaves_no_session(self):
        call_command(
            "contracts_import_xlsx",
            self._xlsx([self._row("SN-1")]),
            status="На обслуживании",
            provider="amb",
            dry_run=True,
        )

        self.assertFalse(ContractDevice.objects.exists())
        self.assertFalse(ImportSession.objects.exists())

    def test_new_city_requires_create_cities_flag(self):
        path = self._xlsx([self._row("SN-1", city="Ангарск")])

        with self.assertRaises(CommandError):
            call_command("contracts_import_xlsx", path, status="На обслуживании", provider="amb")
        self.assertFalse(ImportSession.objects.exists())

        call_command("contracts_import_xlsx", path, status="На обслуживании", provider="amb", create_cities=True)
        self.assertTrue(City.objects.filter(name="Ангарск").exists())

    def test_conflict_row_moves_device_only_with_flag(self):
        device = ContractDevice.objects.create(
            organization=self.other_org,
            city=self.city,
            address="ул. Мира, д. 2",
            model=self.model,
            serial_number="SN-1",
            status=self.status,
        )
        path = self._xlsx([self._row("SN-1")])

        with self.assertRaises(CommandError):
            call_command("contracts_import_xlsx", path, status="На обслуживании", provider="amb")

        call_command("contracts_import_xlsx", path, status="На обслуживании", provider="amb", apply_conflicts=True)

        device.refresh_from_db()
        self.assertEqual(device.organization, self.org)
        self.assertEqual(ContractDevice.objects.filter(serial_number="SN-1").count(), 1)

    def test_two_files_in_one_session(self):
        first = self._xlsx([self._row("SN-1")], name="a.xlsx")
        second = self._xlsx([self._row("SN-2")], name="b.xlsx")

        call_command("contracts_import_xlsx", first, second, status="На обслуживании", provider="amb")

        self.assertEqual(ContractDevice.objects.count(), 2)
        self.assertEqual(ImportSession.objects.get().files.count(), 2)
