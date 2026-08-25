"""
Тесты интеграции с M4.

Доступа к M4 нет, поэтому всё написано по спецификации и проверяется на моках:
важно не «работает ли M4», а собираем ли мы правильный JSON-RPC и правильно ли
разбираем его ответы.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from access.models import UserM4Token
from contracts.models import City, ContractDevice, ContractStatus, DeviceModel, Manufacturer, ServiceProvider
from integrations.m4 import auth, services
from integrations.m4.client import M4Client
from integrations.m4.errors import M4AuthError, M4Error, M4NotConfigured
from integrations.models import M4Connection, M4Issue, OkdeskIssue
from integrations.services_request_dispatch import dispatch_service_request
from inventory.models import Organization

API_URL = "https://m4.test/api.php"


def make_connection(provider, *, token="", api_url=API_URL, **fields):
    """Подключение подрядчика к M4. Токен идёт через сеттер — в базе он шифруется."""
    connection = M4Connection(provider=provider, api_url=api_url, **fields)
    connection.set_token(token)
    connection.save()
    return connection


class FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._payload


class M4CredentialsTests(TestCase):
    def setUp(self):
        self.provider = ServiceProvider.objects.get(code="tonex")
        self.user = get_user_model().objects.create_user(username="m4user", password="p")

    def test_service_token_is_encrypted_at_rest(self):
        connection = make_connection(self.provider, token="tok")

        connection.refresh_from_db()
        self.assertNotIn("tok", connection.encrypted_token)
        self.assertEqual(connection.get_token(), "tok")

    def test_missing_connection_is_not_configured(self):
        with self.assertRaises(M4NotConfigured):
            auth.get_credentials(self.user, self.provider)

    def test_personal_token_wins_over_service_token(self):
        make_connection(self.provider, token="service-token")
        token = UserM4Token(user=self.user)
        token.set_token("personal-token")
        token.save()

        creds = auth.get_credentials(self.user, self.provider)

        self.assertEqual(creds.token, "personal-token")
        self.assertEqual(creds.api_url, API_URL)

    def test_service_token_used_without_personal(self):
        """Служебный токен — для работы без пользователя: сбора заявок и статусов."""
        make_connection(self.provider, token="service-token")

        creds = auth.get_credentials(self.user, self.provider)

        self.assertEqual(creds.token, "service-token")

    def test_connection_without_token_is_not_configured(self):
        make_connection(self.provider)

        with self.assertRaises(M4NotConfigured):
            auth.get_credentials(self.user, self.provider)


class M4ClientTests(SimpleTestCase):
    def setUp(self):
        self.creds = auth.M4Credentials(token="t", api_url="https://sd.test/api.php")

    @patch("integrations.m4.client.requests.post")
    def test_call_posts_jsonrpc_envelope_to_single_url(self, post):
        post.return_value = FakeResponse(payload={"jsonrpc": "2.0", "id": 1, "result": {"taskId": 42}})

        result = M4Client(credentials=self.creds).call("M4CreateTask", {"caption": "x"})

        self.assertEqual(result, {"taskId": 42})
        (url,) = post.call_args[0]
        self.assertEqual(url, "https://sd.test/api.php")
        body = post.call_args[1]["json"]
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["method"], "M4CreateTask")
        self.assertEqual(body["params"], {"caption": "x"})
        self.assertEqual(post.call_args[1]["headers"]["Authorization"], "Bearer t")

    @patch("integrations.m4.client.requests.post")
    def test_jsonrpc_error_becomes_m4_error(self, post):
        post.return_value = FakeResponse(payload={"error": {"code": -32602, "message": "Bad params"}})

        with self.assertRaises(M4Error) as ctx:
            M4Client(credentials=self.creds).call("M4CreateTask", {})

        self.assertIn("Bad params", str(ctx.exception))

    @patch("integrations.m4.client.requests.post")
    def test_401_is_not_retried(self, post):
        """Перевыпустить чужой токен нечем — повтор только зря дёргает M4."""
        post.return_value = FakeResponse(status_code=401)

        with self.assertRaises(M4AuthError):
            M4Client(credentials=self.creds).call("M4GetTaskType")

        self.assertEqual(post.call_count, 1)

    @patch("integrations.m4.client.requests.post")
    def test_non_json_response(self, post):
        post.return_value = FakeResponse(json_error=True)

        with self.assertRaises(M4Error):
            M4Client(credentials=self.creds).call("M4GetTaskType")


class DeviceFixtureMixin:
    def _fixture(self, provider):
        org = Organization.objects.create(name="Org M4")
        city = City.objects.create(name="Братск")
        model = DeviceModel.objects.create(manufacturer=Manufacturer.objects.create(name="Kyocera"), name="P2040")
        status = ContractStatus.objects.create(name="Активен")
        return ContractDevice.objects.create(
            organization=org,
            city=city,
            address="ул. Мира, 1",
            room_number="404",
            model=model,
            status=status,
            serial_number="SN-M4",
            service_provider=provider,
        )


class M4TaskParamsTests(DeviceFixtureMixin, TestCase):
    def setUp(self):
        self.provider = ServiceProvider.objects.get(code="amb")
        self.device = self._fixture(self.provider)

    def test_empty_optionals_are_omitted(self):
        params = services.build_task_params(self.device, title="t", description="d", requester="", phone="")

        self.assertEqual(set(params), {"caption", "fullcaption", "address"})

    def test_contact_person_collected(self):
        params = services.build_task_params(
            self.device, title="t", description="d", requester="Иванов Иван", phone="+79001112233"
        )

        self.assertEqual(params["contactPerson"], {"name": "Иванов Иван", "phone": "+79001112233"})

    def test_description_skips_blank_rows(self):
        text = services.build_description(
            self.device, cartridge="", service_type="Ремонт", comment="", requester="Иванов Иван", phone=""
        )

        self.assertIn("Серийный номер: SN-M4", text)
        self.assertNotIn("Картридж", text)
        self.assertNotIn("Комментарий", text)


class M4CreateTaskTests(DeviceFixtureMixin, TestCase):
    def setUp(self):
        self.provider = ServiceProvider.objects.get(code="amb")
        make_connection(self.provider, api_url="https://sd.test/api.php", token="service-token")
        self.device = self._fixture(self.provider)
        self.user = get_user_model().objects.create_user(
            username="ivanov", password="p", first_name="Иван Иванович", last_name="Иванов"
        )

    @patch("integrations.m4.services.M4Client")
    def test_task_is_saved_locally(self, client_cls):
        client_cls.return_value.call.return_value = {"taskId": "1234"}

        result = services.create_task_for_device(self.user, self.device, service_type="Ремонт")

        self.assertEqual(result, {"task_id": 1234})
        issue = M4Issue.objects.get(task_id=1234)
        self.assertEqual(issue.contract_device_id, self.device.id)
        self.assertEqual(issue.serial_number, "SN-M4")
        self.assertEqual(issue.created_by_id, self.user.id)
        self.assertEqual(issue.author_name, "Иванов Иван Иванович")

    @patch("integrations.m4.services.M4Client")
    def test_missing_task_id_is_an_error(self, client_cls):
        client_cls.return_value.call.return_value = {}

        with self.assertRaises(M4Error):
            services.create_task_for_device(self.user, self.device)

        self.assertFalse(M4Issue.objects.exists())

    @patch("integrations.m4.services.M4Client")
    def test_requester_falls_back_to_username(self, client_cls):
        client_cls.return_value.call.return_value = {"taskId": 1}
        nameless = get_user_model().objects.create_user(username="nameless", password="p")

        services.create_task_for_device(nameless, self.device, phone="+7900")

        params = client_cls.return_value.call.call_args[0][1]
        self.assertEqual(params["contactPerson"]["name"], "nameless")


class DispatchTests(DeviceFixtureMixin, TestCase):
    """Канал выбирается по подрядчику устройства, а не по настройкам."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dispatcher", password="p")
        self.m4_provider = ServiceProvider.objects.get(code="tonex")
        self.m4_provider.issue_tracker = ServiceProvider.M4
        self.m4_provider.save(update_fields=["issue_tracker"])

    @patch("integrations.services_request_dispatch.m4_services.create_task_for_device")
    @patch("integrations.services_request_dispatch.create_issue_for_device")
    def test_m4_provider_goes_to_m4(self, okdesk, m4):
        m4.return_value = {"task_id": 555}

        result = dispatch_service_request(self.user, self._fixture(self.m4_provider))

        self.assertEqual(result, {"channel": ServiceProvider.M4, "issue_id": 555})
        okdesk.assert_not_called()

    @patch("integrations.services_request_dispatch.m4_services.create_task_for_device")
    @patch("integrations.services_request_dispatch.create_issue_for_device")
    def test_okdesk_provider_goes_to_okdesk(self, okdesk, m4):
        okdesk.return_value = {"issue_id": 777}

        result = dispatch_service_request(self.user, self._fixture(ServiceProvider.objects.get(code="amb")))

        self.assertEqual(result, {"channel": ServiceProvider.OKDESK, "issue_id": 777})
        m4.assert_not_called()

    @patch("integrations.services_request_dispatch.m4_services.create_task_for_device")
    def test_phone_is_remembered_on_the_profile(self, m4):
        m4.return_value = {"task_id": 1}

        dispatch_service_request(self.user, self._fixture(self.m4_provider), phone="+79001112233")

        self.assertEqual(self.user.profile.phone, "+79001112233")


class M4TokenApiTests(TestCase):
    """Токен вводится в модалке из меню пользователя, поэтому API закрыт отдельным правом."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tokenuser", password="p")
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

    def _grant(self):
        self.user.user_permissions.add(Permission.objects.get(codename="manage_m4_token"))
        self.user = get_user_model().objects.get(pk=self.user.pk)  # сбрасываем кэш прав

    def test_permission_required(self):
        response = self.client.get("/api/m4-token/")

        self.assertEqual(response.status_code, 302)

    def test_get_reports_absence(self):
        self._grant()

        response = self.client.get("/api/m4-token/")

        self.assertEqual(response.json(), {"ok": True, "has_token": False})

    def test_post_saves_encrypted_token(self):
        self._grant()

        response = self.client.post(
            "/api/m4-token/", data=json.dumps({"token": "secret"}), content_type="application/json"
        )

        self.assertTrue(response.json()["ok"])
        saved = UserM4Token.objects.get(user=self.user)
        self.assertEqual(saved.get_token(), "secret")
        self.assertNotIn("secret", saved.encrypted_token)

    def test_empty_token_rejected(self):
        self._grant()

        response = self.client.post("/api/m4-token/", data=json.dumps({"token": "  "}), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserM4Token.objects.exists())


class IssuesModalChannelTests(DeviceFixtureMixin, TestCase):
    """Модалка заявок узнаёт канал и наличие токена именно для него."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="viewer", password="p")
        self.user.user_permissions.add(Permission.objects.get(codename="view_okdesk_issues"))
        self.user = get_user_model().objects.get(pk=self.user.pk)

        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

        self.m4_provider = ServiceProvider.objects.get(code="tonex")
        self.m4_provider.issue_tracker = ServiceProvider.M4
        self.m4_provider.save(update_fields=["issue_tracker"])

    def _get(self, device):
        return self.client.get(f"/integrations/okdesk/issues/{device.id}/").json()

    def test_provider_without_connection_cannot_create(self):
        data = self._get(self._fixture(self.m4_provider))

        self.assertEqual(data["channel"], "m4")
        self.assertFalse(data["has_token"])

    def test_personal_token_needs_the_service_desk_address(self):
        make_connection(self.m4_provider, api_url="")
        token = UserM4Token(user=self.user)
        token.set_token("personal")
        token.save()

        data = self._get(self._fixture(self.m4_provider))

        self.assertFalse(data["has_token"])

    def test_unconfigured_integration_does_not_blame_the_token(self):
        """Токен сохранён, а подключения нет — чинит администратор, и подсказка не должна врать про токен."""
        token = UserM4Token(user=self.user)
        token.set_token("personal")
        token.save()

        data = self._get(self._fixture(self.m4_provider))

        self.assertFalse(data["has_token"])
        self.assertNotIn("токен", data["token_hint"].lower())

    def test_missing_personal_token_is_named_as_such(self):
        make_connection(self.m4_provider)

        data = self._get(self._fixture(self.m4_provider))

        self.assertFalse(data["has_token"])
        self.assertIn("токен", data["token_hint"].lower())

    def test_personal_token_unlocks_the_form(self):
        make_connection(self.m4_provider)
        token = UserM4Token(user=self.user)
        token.set_token("personal")
        token.save()

        data = self._get(self._fixture(self.m4_provider))

        self.assertTrue(data["has_token"])

    def test_service_token_also_unlocks_the_form(self):
        make_connection(self.m4_provider, token="service-token")

        data = self._get(self._fixture(self.m4_provider))

        self.assertTrue(data["has_token"])

    def test_m4_device_shows_m4_history_not_okdesk(self):
        device = self._fixture(self.m4_provider)
        M4Issue.objects.create(task_id=9001, title="Заявка M4", contract_device=device, status_name="Новая")
        OkdeskIssue.objects.create(issue_id=1, title="Заявка Okdesk", contract_device=device)

        data = self._get(device)

        self.assertEqual([i["id"] for i in data["issues"]], [9001])

    def test_okdesk_device_keeps_okdesk_history(self):
        device = self._fixture(ServiceProvider.objects.get(code="amb"))
        OkdeskIssue.objects.create(issue_id=1, title="Заявка Okdesk", contract_device=device)

        data = self._get(device)

        self.assertEqual(data["channel"], "okdesk")
        self.assertEqual([i["id"] for i in data["issues"]], [1])


class IssueAuthorColumnTests(DeviceFixtureMixin, TestCase):
    """Колонка «Автор заявки» в списке договоров общая для обоих каналов."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lister", password="p")
        for codename in ("access_contracts_app", "view_contractdevice"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.user = get_user_model().objects.get(pk=self.user.pk)

        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

        self.m4_provider = ServiceProvider.objects.get(code="tonex")
        self.m4_provider.issue_tracker = ServiceProvider.M4
        self.m4_provider.save(update_fields=["issue_tracker"])
        self.device = self._fixture(self.m4_provider)

    def _rows(self, **params):
        return self.client.get("/contracts/api/devices/", params).json()["devices"]

    def test_author_of_the_latest_m4_issue_is_shown(self):
        M4Issue.objects.create(
            task_id=1,
            title="Старая",
            contract_device=self.device,
            author_name="Петров Пётр",
            created_at=timezone.now() - timedelta(days=2),
        )
        M4Issue.objects.create(
            task_id=2,
            title="Свежая",
            contract_device=self.device,
            author_name="Иванов Иван",
            created_at=timezone.now(),
        )

        self.assertEqual(self._rows()[0]["issue_author_name"], "Иванов Иван")

    def test_device_without_issues_has_no_author(self):
        self.assertEqual(self._rows()[0]["issue_author_name"], "")

    def test_filter_by_author_finds_m4_device(self):
        M4Issue.objects.create(task_id=1, title="Заявка", contract_device=self.device, author_name="Иванов Иван")

        self.assertEqual(len(self._rows(issue_author="Иванов Иван")), 1)
        self.assertEqual(len(self._rows(issue_author="Сидоров Сидор")), 0)

    def test_m4_authors_land_in_filter_choices(self):
        M4Issue.objects.create(task_id=1, title="Заявка", contract_device=self.device, author_name="Иванов Иван")

        choices = self.client.get("/contracts/api/filters/").json()["choices"]

        self.assertIn("Иванов Иван", choices["issue_author"])


class M4ConnectionAdminTests(TestCase):
    """Служебный токен задаётся через админку, но обратно не показывается."""

    def setUp(self):
        self.provider = ServiceProvider.objects.get(code="tonex")
        admin_user = get_user_model().objects.create_superuser(username="root", password="p", email="root@test.local")
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(admin_user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

    def _post(self, url, **overrides):
        payload = {"provider": self.provider.pk, "api_url": API_URL, "token": ""}
        payload.update(overrides)
        return self.client.post(url, payload)

    def test_token_is_saved_encrypted_and_never_rendered_back(self):
        self._post("/admin/integrations/m4connection/add/", token="s3cret")

        connection = M4Connection.objects.get(provider=self.provider)
        self.assertEqual(connection.get_token(), "s3cret")
        self.assertNotIn("s3cret", connection.encrypted_token)

        page = self.client.get(f"/admin/integrations/m4connection/{connection.pk}/change/")

        self.assertNotContains(page, "s3cret")
        self.assertNotContains(page, connection.encrypted_token)
        self.assertContains(page, "задан")

    def test_blank_token_keeps_the_previous_one(self):
        self._post("/admin/integrations/m4connection/add/", token="t0ken")
        connection = M4Connection.objects.get(provider=self.provider)

        self._post(f"/admin/integrations/m4connection/{connection.pk}/change/", api_url="https://other.test/api.php")

        connection.refresh_from_db()
        self.assertEqual(connection.api_url, "https://other.test/api.php")
        self.assertEqual(connection.get_token(), "t0ken")

    def test_address_is_required(self):
        """Из токена URL не вывести, поэтому пустой адрес админка принимать не должна."""
        response = self._post("/admin/integrations/m4connection/add/", api_url="", token="t0ken")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(M4Connection.objects.exists())

    def test_address_and_personal_token_are_enough(self):
        """Заявку пользователь подаёт своим токеном — служебный для этого не нужен."""
        user = get_user_model().objects.create_user(username="operator", password="p")
        personal = UserM4Token(user=user)
        personal.set_token("mine")
        personal.save()

        self._post("/admin/integrations/m4connection/add/")

        self.assertTrue(auth.has_credentials(user, self.provider))
        creds = auth.get_credentials(user, self.provider)
        self.assertEqual(creds.token, "mine")
        self.assertEqual(creds.api_url, API_URL)
