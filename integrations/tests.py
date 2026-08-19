import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, SimpleTestCase, TestCase

from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer
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


class CreateServiceRequestViewTests(TestCase):
    """View подачи заявки: право, разбор тела и проброс отказов канала.

    Выбор канала по подрядчику проверяется на уровне сервиса, в
    contracts.tests.test_services_requests — здесь только то, что делает сам view.
    """

    URL = "/integrations/requests/create/"

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u", password="p")
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

    def grant_submission_right(self):
        self.user.user_permissions.add(Permission.objects.get(codename="create_service_request"))

    def post(self, **payload):
        return self.client.post(self.URL, data=json.dumps(payload), content_type="application/json")

    def test_permission_is_required(self):
        self.assertEqual(self.post(device_id=1).status_code, 403)

    def test_broken_json_is_rejected(self):
        self.grant_submission_right()

        response = self.client.post(self.URL, data="{", content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_device_id_is_required(self):
        self.grant_submission_right()

        self.assertEqual(self.post().status_code, 400)

    def test_channel_refusal_keeps_its_status(self):
        from contracts.services_requests import SubmissionError

        self.grant_submission_right()
        refusal = SubmissionError("У подрядчика «Tonex» не настроен приём заявок", status=409)

        with patch("contracts.services_requests.submit_service_request", side_effect=refusal):
            response = self.post(device_id=1)

        self.assertEqual(response.status_code, 409)
        self.assertIn("Tonex", response.json()["error"])

    def test_successful_submission_returns_journal_number(self):
        self.grant_submission_right()
        created = SimpleNamespace(number="ЗВ-000123", external_number="555", deadline_at=None)

        with patch("contracts.services_requests.submit_service_request", return_value=created) as submit:
            response = self.post(device_id=42, comment="Не печатает", stops_printing=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_number"], "ЗВ-000123")
        self.assertEqual(response.json()["issue_id"], "555")
        self.assertEqual(submit.call_args.kwargs["device_id"], 42)
