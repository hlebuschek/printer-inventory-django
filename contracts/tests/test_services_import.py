from io import BytesIO

from openpyxl import Workbook

from django.test import TestCase

from contracts.models import (
    City,
    Contract,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    ImportRow,
    ImportSession,
    Manufacturer,
    ServiceProvider,
)
from contracts.services_import import (
    ImportFileError,
    analyze_file,
    apply_session,
    find_missing_devices,
    session_summary,
)
from inventory.models import Organization, Printer

HEADER = ["Организация", "Город", "Адрес", "№ кабинета", "Производитель", "Модель оборудования", "Серийный номер"]


def make_xlsx(rows, header=None):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(header if header is not None else HEADER)
    for row in rows:
        worksheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


class ImportAnalysisTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.other_org = Organization.objects.create(name="ООО Лютик")
        self.city = City.objects.create(name="Иркутск")
        self.manufacturer = Manufacturer.objects.create(name="Avision")
        self.model = DeviceModel.objects.create(manufacturer=self.manufacturer, name="Avision AM4032in")
        self.status = ContractStatus.objects.create(name="На обслуживании")
        self.session = ImportSession.objects.create(target_status=self.status)

    def _row(self, sn, org="ООО Ромашка", city="Иркутск", model="Avision AM4032in"):
        return [org, city, "ул. Ленина, д. 1", "101", "Avision", model, sn]

    def test_header_not_in_first_row_is_rejected(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Приложение №1 к Техническому Заданию"])
        worksheet.append(HEADER)
        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)

        with self.assertRaises(ImportFileError) as ctx:
            analyze_file(self.session, stream, "preamble.xlsx")
        self.assertIn("шапка", str(ctx.exception).lower())

    def test_row_without_serial_is_error(self):
        analyze_file(self.session, make_xlsx([self._row("")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.ERROR)
        self.assertEqual([e["code"] for e in row.errors], ["NO_SERIAL"])

    def test_unknown_organization_is_error_and_listed(self):
        analyze_file(self.session, make_xlsx([self._row("SN1", org="ООО Неизвестная")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.ERROR)
        self.assertIn("UNKNOWN_ORGANIZATION", [e["code"] for e in row.errors])
        self.assertEqual(session_summary(self.session)["unknown_organizations"], ["ООО Неизвестная"])

    def test_unknown_model_is_error(self):
        analyze_file(self.session, make_xlsx([self._row("SN1", model="Avision AM4032n")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.ERROR)
        self.assertIn("UNKNOWN_MODEL", [e["code"] for e in row.errors])

    def test_model_matched_case_insensitively(self):
        """Регистр не должен плодить дубли справочника — «AM4032IN» это та же модель."""
        analyze_file(self.session, make_xlsx([self._row("SN1", model="Avision AM4032IN")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.NEW)
        self.assertEqual(row.resolved["model_id"], self.model.id)

    def test_new_city_is_warning_not_error(self):
        analyze_file(self.session, make_xlsx([self._row("SN1", city="Тайшет")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.NEW)
        self.assertIn("NEW_CITY", [w["code"] for w in row.warnings])
        self.assertEqual(session_summary(self.session)["new_cities"], ["Тайшет"])

    def test_existing_serial_in_same_organization_is_match(self):
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина, д. 1",
            model=self.model,
            serial_number="sn1",
            status=self.status,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.MATCH)
        self.assertEqual(row.matched_device_id, device.id)

    def test_serial_in_another_organization_is_moved(self):
        ContractDevice.objects.create(
            organization=self.other_org,
            city=self.city,
            address="ул. Мира, д. 2",
            model=self.model,
            serial_number="SN1",
            status=self.status,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")

        row = self.session.rows.get()
        self.assertEqual(row.classification, ImportRow.MOVED)

    def test_duplicate_serial_across_two_files(self):
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "a.xlsx")
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "b.xlsx")

        self.assertEqual(self.session.rows.count(), 2)
        for row in self.session.rows.all():
            self.assertEqual(row.classification, ImportRow.DUP_IN_FILE)

    def test_reupload_of_same_file_replaces_its_rows(self):
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "a.xlsx")
        analyze_file(self.session, make_xlsx([self._row("SN2")]), "a.xlsx")

        self.assertEqual(self.session.files.count(), 1)
        self.assertEqual([r.sn_lower for r in self.session.rows.all()], ["sn2"])
        self.assertEqual(self.session.rows.get().classification, ImportRow.NEW)

    def test_serial_whitespace_is_normalized(self):
        analyze_file(self.session, make_xlsx([self._row("SN1\t")]), "f.xlsx")

        self.assertEqual(self.session.rows.get().sn_lower, "sn1")


class ImportApplyTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.other_org = Organization.objects.create(name="ООО Лютик")
        self.city = City.objects.create(name="Иркутск")
        self.manufacturer = Manufacturer.objects.create(name="Avision")
        self.model = DeviceModel.objects.create(manufacturer=self.manufacturer, name="Avision AM4032in")
        self.old_status = ContractStatus.objects.create(name="Старый договор")
        self.status = ContractStatus.objects.create(name="На обслуживании")
        # Подрядчики заводятся миграцией 0008 — заново создавать нельзя, name/code уникальны
        self.amb = ServiceProvider.objects.get(code="amb")
        self.tonex = ServiceProvider.objects.get(code="tonex")
        self.session = ImportSession.objects.create(target_status=self.status, service_provider=self.tonex)

    def _row(self, sn, org="ООО Ромашка", city="Иркутск"):
        return [org, city, "ул. Ленина, д. 1", "101", "Avision", "Avision AM4032in", sn]

    def test_existing_comment_is_preserved_on_update(self):
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Старая, д. 9",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
            comment="Стоит у бухгалтерии, ключ у Петровой",
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(self.session)

        device.refresh_from_db()
        self.assertEqual(device.comment, "Стоит у бухгалтерии, ключ у Петровой")
        self.assertEqual(device.address, "ул. Ленина, д. 1")
        self.assertEqual(device.status, self.status)

    def test_new_device_created_with_session_status(self):
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        result = apply_session(self.session)

        self.assertEqual((result["created"], result["updated"]), (1, 0))
        device = ContractDevice.objects.get(serial_number="SN1")
        self.assertEqual(device.status, self.status)
        self.assertEqual(device.comment, "")

    def test_service_provider_from_session_is_assigned(self):
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Старая, д. 9",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
            service_provider=self.amb,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1"), self._row("SN2")]), "f.xlsx")
        apply_session(self.session)

        device.refresh_from_db()
        self.assertEqual(device.service_provider, self.tonex)
        self.assertEqual(ContractDevice.objects.get(serial_number="SN2").service_provider, self.tonex)

    def test_contract_from_session_is_assigned(self):
        contract = Contract.objects.create(number="42/2026", provider=self.tonex, price_a4_bw="0.9")
        self.session.contract = contract
        self.session.save(update_fields=["contract"])

        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(self.session)

        self.assertEqual(ContractDevice.objects.get(serial_number="SN1").contract, contract)

    def test_session_without_contract_keeps_existing_one(self):
        contract = Contract.objects.create(number="42/2026", provider=self.amb)
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Старая, д. 9",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
            contract=contract,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(self.session)

        device.refresh_from_db()
        self.assertEqual(device.contract, contract)

    def test_session_without_provider_keeps_existing_one(self):
        device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Старая, д. 9",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
            service_provider=self.amb,
        )
        session = ImportSession.objects.create(target_status=self.status)
        analyze_file(session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(session)

        device.refresh_from_db()
        self.assertEqual(device.service_provider, self.amb)

    def test_printer_linked_by_serial(self):
        printer = Printer.objects.create(ip_address="10.0.0.1", serial_number="SN1", organization=self.org)
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(self.session)

        self.assertEqual(ContractDevice.objects.get(serial_number="SN1").printer_id, printer.id)

    def test_conflict_row_is_not_applied_without_decision(self):
        ContractDevice.objects.create(
            organization=self.other_org,
            city=self.city,
            address="ул. Мира, д. 2",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        result = apply_session(self.session)

        self.assertEqual(result["total"], 0)
        self.assertEqual(ContractDevice.objects.get(serial_number="SN1").organization, self.other_org)

    def test_conflict_row_applied_after_explicit_decision(self):
        device = ContractDevice.objects.create(
            organization=self.other_org,
            city=self.city,
            address="ул. Мира, д. 2",
            model=self.model,
            serial_number="SN1",
            status=self.old_status,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        self.session.rows.update(decision=ImportRow.APPLY)
        apply_session(self.session)

        device.refresh_from_db()
        self.assertEqual(device.organization, self.org)

    def test_new_city_requires_confirmation(self):
        analyze_file(self.session, make_xlsx([self._row("SN1", city="Тайшет")]), "f.xlsx")

        with self.assertRaises(ImportFileError):
            apply_session(self.session)
        self.assertFalse(City.objects.filter(name="Тайшет").exists())

        apply_session(self.session, create_cities=True)
        self.assertEqual(ContractDevice.objects.get(serial_number="SN1").city.name, "Тайшет")

    def test_error_rows_are_never_applied(self):
        analyze_file(self.session, make_xlsx([self._row(""), self._row("SN1")]), "f.xlsx")
        result = apply_session(self.session)

        self.assertEqual(result["created"], 1)
        self.assertEqual(ContractDevice.objects.count(), 1)

    def test_missing_devices_scoped_to_session_organizations(self):
        stale = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Забытая, д. 3",
            model=self.model,
            serial_number="OLD1",
            status=self.old_status,
        )
        untouched_org_device = ContractDevice.objects.create(
            organization=self.other_org,
            city=self.city,
            address="ул. Чужая, д. 4",
            model=self.model,
            serial_number="OTHER1",
            status=self.old_status,
        )
        analyze_file(self.session, make_xlsx([self._row("SN1")]), "f.xlsx")
        apply_session(self.session)

        missing = list(find_missing_devices(self.session))
        self.assertIn(stale, missing)
        self.assertNotIn(untouched_org_device, missing)
