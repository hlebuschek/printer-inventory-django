import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, SimpleTestCase, TestCase

from access.models import UserOkdeskToken
from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer, ServiceProvider
from integrations.models import OkdeskIssue
from integrations.okdesk_enrichment import (
    _is_valid_serial,
    build_contract_device_map,
    build_reference_serials,
    deduplicate_serials,
    find_serials_in_text,
    normalize_serial,
    parse_html_table,
    relink_orphan_row,
    resolve_devices,
)
from inventory.models import Organization


class NormalizeSerialTests(SimpleTestCase):
    def test_strips_separators_and_uppercases(self):
        self.assertEqual(normalize_serial("ab-12_34 56"), "AB123456")


class IsValidSerialTests(SimpleTestCase):
    def test_too_short(self):
        self.assertFalse(_is_valid_serial("ab"))

    def test_junk_words(self):
        self.assertFalse(_is_valid_serial("отсутствует"))
        self.assertFalse(_is_valid_serial("н/д"))

    def test_double_pipe_is_junk(self):
        self.assertFalse(_is_valid_serial("Усть-Илимск||"))

    def test_long_cyrillic_word_rejected(self):
        self.assertFalse(_is_valid_serial("Иркутск"))

    def test_too_many_spaces(self):
        self.assertFalse(_is_valid_serial("a b c d e"))

    def test_valid_serial(self):
        self.assertTrue(_is_valid_serial("VNB3R12345"))


class FindSerialsInTextTests(SimpleTestCase):
    def test_finds_reference_serial_case_insensitive(self):
        refs = ["VNB3R12345", "ABC999"]
        found = find_serials_in_text("Принтер vnb3r12345 сломан", refs)
        self.assertEqual(found, ["VNB3R12345"])

    def test_strips_html_and_markup(self):
        refs = ["ABC999"]
        found = find_serials_in_text("<b>S/N: abc999</b>", refs)
        self.assertIn("ABC999", found)

    def test_empty_inputs(self):
        self.assertEqual(find_serials_in_text("", ["X"]), [])
        self.assertEqual(find_serials_in_text("text", []), [])


class ParseHtmlTableTests(SimpleTestCase):
    def test_extracts_serial_column_with_reference_fix(self):
        lookup = {"VNB3R12345": "VNB3R12345"}
        html_doc = """
        <table>
          <tr><th>Модель</th><th>Серийный номер</th></tr>
          <tr><td>HP</td><td>vnb3r-12345</td></tr>
        </table>
        """
        self.assertEqual(parse_html_table(html_doc, lookup), ["VNB3R12345"])

    def test_skips_junk_cells(self):
        html_doc = """
        <table>
          <tr><th>Серийный номер</th></tr>
          <tr><td>отсутствует</td></tr>
          <tr><td>-</td></tr>
          <tr><td>GOODSN123</td></tr>
        </table>
        """
        self.assertEqual(parse_html_table(html_doc, {}), ["GOODSN123"])

    def test_no_serial_column(self):
        html_doc = "<table><tr><th>Модель</th></tr><tr><td>HP</td></tr></table>"
        self.assertEqual(parse_html_table(html_doc, {}), [])

    def test_empty_description(self):
        self.assertEqual(parse_html_table("", {}), [])


class DeduplicateSerialsTests(SimpleTestCase):
    def test_preserves_order_and_dedupes(self):
        self.assertEqual(deduplicate_serials(["A", "B", "A", "C"]), "A, B, C")

    def test_empty(self):
        self.assertEqual(deduplicate_serials([]), "")


class OkdeskDbTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org O")
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

    def test_build_reference_serials(self):
        self._device("SN-1")
        self._device("SN-2")
        self._device("")  # пустые игнорируются
        serials, lookup = build_reference_serials()
        self.assertEqual(serials, {"SN-1", "SN-2"})
        self.assertEqual(lookup["SN1"], "SN-1")

    def test_build_contract_device_map(self):
        dev = self._device("AB-12_34")
        mapping = build_contract_device_map()
        self.assertEqual(mapping["AB1234"], (dev.id, "AB-12_34"))

    def test_resolve_devices_dedupes_and_orders(self):
        d1 = self._device("SN-1")
        d2 = self._device("SN-2")
        mapping = build_contract_device_map()
        matched = resolve_devices(["sn-2", "sn 1", "SN-2"], mapping)
        self.assertEqual(matched, [(d2.id, "SN-2"), (d1.id, "SN-1")])

    def test_relink_orphan_row_splits(self):
        d1 = self._device("SN-1")
        d2 = self._device("SN-2")
        issue = OkdeskIssue.objects.create(issue_id=555, title="Заявка", serial_numbers="SN-1, SN-2")
        cloned = relink_orphan_row(issue, [(d1.id, "SN-1"), (d2.id, "SN-2")])
        self.assertEqual(cloned, 1)
        self.assertEqual(OkdeskIssue.objects.filter(issue_id=555).count(), 2)
        issue.refresh_from_db()
        self.assertEqual(issue.contract_device_id, d1.id)
        self.assertEqual(issue.serial_numbers, "SN-1")

    def test_relink_orphan_row_empty_match_noop(self):
        issue = OkdeskIssue.objects.create(issue_id=556, title="Заявка")
        self.assertEqual(relink_orphan_row(issue, []), 0)


class CreateIssueProviderGateTests(TestCase):
    """Заявка уходит только тем подрядчикам, у которых подключён приём заявок."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org O")
        self.city = City.objects.create(name="Иркутск")
        self.model = DeviceModel.objects.create(manufacturer=Manufacturer.objects.create(name="HP"), name="M1")
        self.status = ContractStatus.objects.create(name="Активен")
        # Подрядчики заводятся миграцией 0008 — заново создавать нельзя, name/code уникальны
        self.amb = ServiceProvider.objects.get(code="amb")
        self.tonex = ServiceProvider.objects.get(code="tonex")

        user = get_user_model().objects.create_user(username="u", password="p")
        user.user_permissions.add(Permission.objects.get(codename="create_okdesk_issue"))
        token = UserOkdeskToken(user=user)
        token.set_token("test-token")
        token.save()

        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

    def _device(self, provider):
        return ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="addr",
            model=self.model,
            status=self.status,
            serial_number="SN-1",
            service_provider=provider,
        )

    def _post(self, device):
        return self.client.post(
            "/integrations/okdesk/create-issue/",
            data=json.dumps({"device_id": device.id}),
            content_type="application/json",
        )

    def test_provider_without_tracker_is_rejected(self):
        response = self._post(self._device(self.tonex))

        self.assertEqual(response.status_code, 409)
        self.assertIn("Tonex", response.json()["error"])

    def test_provider_gate_runs_before_token_check(self):
        UserOkdeskToken.objects.all().delete()

        response = self._post(self._device(self.tonex))

        self.assertIn("Tonex", response.json()["error"])

    def test_inactive_provider_is_rejected(self):
        self.amb.is_active = False
        self.amb.save(update_fields=["is_active"])

        response = self._post(self._device(self.amb))

        self.assertEqual(response.status_code, 409)
        self.assertIn("отключён", response.json()["error"])

    def test_okdesk_provider_passes_the_gate(self):
        # Дальше запрос упирается в Okdesk API, поэтому проверяем только сам гейт
        response = self._post(self._device(self.amb))

        self.assertNotIn("не подключён приём заявок", response.json()["error"])
