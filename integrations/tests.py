import json
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from access.models import UserOkdeskToken
from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer, ServiceProvider
from integrations.glpi.client import GLPIClient
from integrations.glpi.services import check_device_in_glpi, check_multiple_devices_in_glpi
from integrations.models import GLPISync, OkdeskInstance, OkdeskIssue
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
        # Инстанс для «АМБ» может уже существовать: его создаёт data-миграция 0014
        self.instance, _ = OkdeskInstance.objects.get_or_create(
            service_provider=ServiceProvider.objects.get(code="amb"),
            defaults={"api_url": "https://abikom.okdesk.ru/api/v1"},
        )

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
        issue = OkdeskIssue.objects.create(
            instance=self.instance, issue_id=555, title="Заявка", serial_numbers="SN-1, SN-2"
        )
        cloned = relink_orphan_row(issue, [(d1.id, "SN-1"), (d2.id, "SN-2")])
        self.assertEqual(cloned, 1)
        self.assertEqual(OkdeskIssue.objects.filter(issue_id=555).count(), 2)
        issue.refresh_from_db()
        self.assertEqual(issue.contract_device_id, d1.id)
        self.assertEqual(issue.serial_numbers, "SN-1")

    def test_relink_orphan_row_empty_match_noop(self):
        issue = OkdeskIssue.objects.create(instance=self.instance, issue_id=556, title="Заявка")
        self.assertEqual(relink_orphan_row(issue, []), 0)

    def test_same_issue_id_allowed_in_different_instances(self):
        # У двух подрядчиков независимые Okdesk: номера заявок могут совпадать
        other, _ = OkdeskInstance.objects.get_or_create(
            service_provider=ServiceProvider.objects.get(code="tonex"),
            defaults={"api_url": "https://tonex.okdesk.ru/api/v1"},
        )
        OkdeskIssue.objects.create(instance=self.instance, issue_id=777, title="Абиком")
        OkdeskIssue.objects.create(instance=other, issue_id=777, title="Тонекс")
        self.assertEqual(OkdeskIssue.objects.filter(issue_id=777).count(), 2)

    def test_same_issue_id_same_instance_orphan_rejected(self):
        from django.db import IntegrityError, transaction

        OkdeskIssue.objects.create(instance=self.instance, issue_id=778, title="Первая")
        with self.assertRaises(IntegrityError), transaction.atomic():
            OkdeskIssue.objects.create(instance=self.instance, issue_id=778, title="Дубль")


class CreateIssueProviderGateTests(TestCase):
    """Заявка в Okdesk заводится только по устройствам подрядчика, работающего через Okdesk."""

    def setUp(self):
        self.org = Organization.objects.create(name="Org O")
        self.city = City.objects.create(name="Иркутск")
        self.model = DeviceModel.objects.create(manufacturer=Manufacturer.objects.create(name="HP"), name="M1")
        self.status = ContractStatus.objects.create(name="Активен")
        # Подрядчики заводятся миграцией 0008 — заново создавать нельзя, name/code уникальны
        self.amb = ServiceProvider.objects.get(code="amb")
        self.tonex = ServiceProvider.objects.get(code="tonex")
        self.amb_instance, _ = OkdeskInstance.objects.get_or_create(
            service_provider=self.amb,
            defaults={"api_url": "https://abikom.okdesk.ru/api/v1"},
        )

        user = get_user_model().objects.create_user(username="u", password="p")
        user.user_permissions.add(Permission.objects.get(codename="create_okdesk_issue"))
        token = UserOkdeskToken(user=user, instance=self.amb_instance)
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

    def test_provider_without_okdesk_is_rejected(self):
        response = self._post(self._device(self.tonex))

        self.assertEqual(response.status_code, 403)
        self.assertIn("Tonex", response.json()["error"])

    def test_provider_gate_runs_before_token_check(self):
        UserOkdeskToken.objects.all().delete()

        response = self._post(self._device(self.tonex))

        self.assertIn("Tonex", response.json()["error"])

    def test_okdesk_provider_passes_the_gate(self):
        # Дальше запрос упирается в Okdesk API, поэтому проверяем только сам гейт
        response = self._post(self._device(self.amb))

        self.assertNotIn("не через Okdesk", response.json()["error"])


def _resp(status, body):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


class FakeGLPI:
    """Подменяет requests в GLPIClient: считает входы/выходы, выдаёт новый токен на каждый вход."""

    def __init__(self, expire_first_search=False):
        self.logins = 0
        self.logouts = 0
        self.searches = []  # Session-Token каждого поиска
        self.expire_first_search = expire_first_search

    def get(self, url, **kwargs):
        if url.endswith("/initSession"):
            self.logins += 1
            return _resp(200, {"session_token": f"tok{self.logins}"})
        if url.endswith("/killSession"):
            self.logouts += 1
            return _resp(200, {})
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, **kwargs):
        return _resp(200, {})  # changeActiveEntities

    def request(self, method, url, **kwargs):
        self.searches.append(kwargs["headers"].get("Session-Token"))
        if self.expire_first_search and len(self.searches) == 1:
            return _resp(401, ["ERROR_SESSION_TOKEN_INVALID", "session_token seems invalid"])
        return _resp(200, {"totalcount": 1, "data": [{"2": 10, "1": "P", "31": "Актив", "3": "Loc"}]})

    def patches(self):
        return [
            patch("integrations.glpi.client.requests.get", side_effect=self.get),
            patch("integrations.glpi.client.requests.post", side_effect=self.post),
            patch("integrations.glpi.client.requests.request", side_effect=self.request),
        ]


@override_settings(GLPI_API_URL="https://glpi.test/apirest.php", GLPI_USER_TOKEN="t", GLPI_APP_TOKEN="")
class GLPISingleSessionTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org G")
        city = City.objects.create(name="Город")
        model = DeviceModel.objects.create(manufacturer=Manufacturer.objects.create(name="HP"), name="M1")
        status = ContractStatus.objects.create(name="Активен")
        self.devices = [
            ContractDevice.objects.create(
                organization=org, city=city, address="a", model=model, status=status, serial_number=f"SN{i}"
            )
            for i in range(3)
        ]
        self.fake = FakeGLPI()
        for p in self.fake.patches():
            p.start()
            self.addCleanup(p.stop)

    def test_bulk_check_logs_in_once(self):
        stats = check_multiple_devices_in_glpi([d.id for d in self.devices])
        self.assertEqual(stats["found_single"], 3)
        self.assertEqual((self.fake.logins, self.fake.logouts), (1, 1))
        self.assertEqual(set(self.fake.searches), {"tok1"})

    def test_sync_glpi_command_logs_in_once(self):
        call_command("sync_glpi", "--delay", "0", "--force", stdout=StringIO())
        self.assertEqual(GLPISync.objects.filter(status="FOUND_SINGLE").count(), 3)
        self.assertEqual((self.fake.logins, self.fake.logouts), (1, 1))

    def test_single_check_without_client_keeps_own_session(self):
        sync = check_device_in_glpi(self.devices[0], force_check=True)
        self.assertEqual(sync.status, "FOUND_SINGLE")
        self.assertEqual((self.fake.logins, self.fake.logouts), (1, 1))

    def test_passed_client_is_not_closed(self):
        client = GLPIClient()
        check_device_in_glpi(self.devices[0], force_check=True, client=client)
        check_device_in_glpi(self.devices[1], force_check=True, client=client)
        self.assertEqual((self.fake.logins, self.fake.logouts), (1, 0))
        self.assertEqual(client.session_token, "tok1")

    def test_expired_token_relogin_and_retry(self):
        self.fake.expire_first_search = True
        client = GLPIClient()
        status, items, error = client.search_printer_by_serial("SN0")
        self.assertEqual(status, "FOUND_SINGLE")
        self.assertEqual(self.fake.logins, 2)
        self.assertEqual(self.fake.searches, ["tok1", "tok2"])
        self.assertEqual(client.session_token, "tok2")
