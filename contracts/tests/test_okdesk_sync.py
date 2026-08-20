from unittest.mock import Mock, patch

import requests

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from contracts.models import ServiceProvider, ServiceRequest, ServiceRequestMessage
from contracts.services_okdesk_import import (
    _clean_description,
    import_issue_with_device,
    resolve_initiator,
    sync_requests,
)
from integrations.models import OkdeskIssue

from .test_service_requests import ServiceRequestBase, dt


def issue_detail(issue_id, *, final=False):
    return {
        "id": issue_id,
        "title": f"Заявка {issue_id}",
        "description": "<p>Не&nbsp;печатает</p>",
        "status": {"code": "completed" if final else "opened"},
        "created_at": "2026-03-02T14:00:00+08:00",
        "completed_at": "2026-03-05T10:00:00+08:00" if final else None,
        "attachments": [],
    }


def fake_get(details):
    def _fake(path, **params):
        if path.endswith("/comments"):
            return []
        issue_id = int(path.rsplit("/", 1)[-1])
        return details[issue_id]

    return _fake


class CleanDescriptionTests(SimpleTestCase):
    def test_site_request_table_becomes_key_value_lines(self):
        raw = (
            "<table><thead><tr><th>№</th><th>Город</th><th>Комментарии</th></tr></thead>"
            "<tbody><tr><td>1</td><td>Братск</td><td>Замена&nbsp;DRUM</td></tr></tbody></table>"
            "<p>С уважением, Николаев</p>"
        )
        self.assertEqual(
            _clean_description(raw),
            "№: 1\nГород: Братск\nКомментарии: Замена DRUM\nС уважением, Николаев",
        )

    def test_plain_text_passes_through(self):
        self.assertEqual(_clean_description("<p>Не&nbsp;печатает</p>"), "Не печатает")


class OkdeskSyncTests(ServiceRequestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Провайдер Okdesk уже посеян миграцией — используем его
        cls.okdesk = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK).first()
        cls.okdesk.is_active = True
        cls.okdesk.save(update_fields=["is_active"])

    def make_issue(self, issue_id, status_name="Открыта", linked=True):
        return OkdeskIssue.objects.create(
            issue_id=issue_id,
            title=f"Заявка {issue_id}",
            contract_device=self.device if linked else None,
            created_at=dt("2026-03-02", 14),
            status_name=status_name,
        )

    def sync(self, details):
        with patch("contracts.services_okdesk_import._get", side_effect=fake_get(details)):
            return sync_requests()

    def test_creates_open_request_with_description_message(self):
        self.make_issue(101)

        stats = self.sync({101: issue_detail(101)})

        self.assertEqual(stats["open"], 1)
        request = ServiceRequest.objects.get(external_number="101")
        self.assertEqual(request.status, ServiceRequest.OPEN)
        self.assertEqual(request.description, "Не печатает")

        message = request.messages.get()
        self.assertEqual(message.channel, ServiceProvider.OKDESK)
        self.assertEqual(message.direction, ServiceRequestMessage.OUTGOING)
        self.assertEqual(message.external_id, "issue-101")
        self.assertEqual(message.body_text, "Не печатает")

    def test_closes_open_request_when_okdesk_went_final(self):
        # Локальная строка ещё «Открыта», но живой Okdesk уже закрыл заявку
        self.make_issue(102)
        request = self.make_request(service_provider=self.okdesk, external_number="102")

        stats = self.sync({102: issue_detail(102, final=True)})

        self.assertEqual(stats["completed"], 1)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequest.CLOSED)
        self.assertEqual(request.closed_at, dt("2026-03-05", 10))
        self.assertEqual(request.restored_at, request.closed_at)

    def test_locally_closed_row_still_checked_for_open_request(self):
        # OkdeskIssue уже помечена закрытой 4-часовым синком, а заявка журнала открыта
        self.make_issue(103, status_name="Закрыта")
        request = self.make_request(service_provider=self.okdesk, external_number="103")

        stats = self.sync({103: issue_detail(103, final=True)})

        self.assertEqual(stats["completed"], 1)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequest.CLOSED)

    def test_rejected_request_is_not_touched(self):
        self.make_issue(104)
        request = self.make_request(service_provider=self.okdesk, external_number="104")
        request.status = ServiceRequest.REJECTED
        request.save(update_fields=["status"])

        stats = self.sync({104: issue_detail(104, final=True)})

        self.assertEqual(stats["completed"], 0)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequest.REJECTED)
        self.assertIsNone(request.closed_at)

    def test_second_run_is_idempotent(self):
        self.make_issue(105)
        details = {105: issue_detail(105)}

        self.sync(details)
        stats = self.sync(details)

        self.assertEqual(stats["open"], 0)
        self.assertEqual(stats["comments"], 0)
        self.assertEqual(ServiceRequest.objects.filter(external_number="105").count(), 1)
        self.assertEqual(ServiceRequestMessage.objects.filter(external_id="issue-105").count(), 1)

    def test_forbidden_issue_is_excluded_from_future_syncs(self):
        issue = self.make_issue(107)

        def forbidden(path, **params):
            raise requests.HTTPError(response=Mock(status_code=403))

        with patch("contracts.services_okdesk_import._get", side_effect=forbidden):
            stats = sync_requests()

        self.assertEqual(stats["errors"], 0)
        issue.refresh_from_db()
        self.assertTrue(issue.journal_excluded)

        # Исключённая заявка больше не дёргает API
        with patch("contracts.services_okdesk_import._get") as get_mock:
            sync_requests()
        get_mock.assert_not_called()

    def test_no_active_okdesk_provider_is_noop(self):
        ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK).update(is_active=False)
        self.make_issue(106)

        stats = self.sync({106: issue_detail(106)})

        self.assertEqual(stats["open"], 0)
        self.assertFalse(ServiceRequest.objects.filter(external_number="106").exists())

    def test_unlinked_row_with_open_request_is_synced(self):
        # Заявка заведена в журнал вручную: зеркало без устройства, связь по external_number
        self.make_issue(108, linked=False)
        request = self.make_request(service_provider=self.okdesk, external_number="108")

        stats = self.sync({108: issue_detail(108, final=True)})

        self.assertEqual(stats["completed"], 1)
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequest.CLOSED)

    def test_unlinked_row_without_request_stays_out_of_journal(self):
        self.make_issue(109, linked=False)

        with patch("contracts.services_okdesk_import._get") as get_mock:
            sync_requests()

        get_mock.assert_not_called()
        self.assertFalse(ServiceRequest.objects.filter(external_number="109").exists())


class InitiatorMatchingTests(ServiceRequestBase):
    """Автор заявки в Okdesk — строка «Фамилия Имя»; почты Okdesk не отдаёт,
    поэтому инициатора журнала ищем по ней."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.okdesk = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK).first()
        cls.okdesk.is_active = True
        cls.okdesk.save(update_fields=["is_active"])
        User = get_user_model()
        cls.nefedov = User.objects.create_user(username="nefedov", first_name="Андрей", last_name="Нефёдов")
        cls.vaganov = User.objects.create_user(username="vaganov", first_name="Сергей", last_name="Ваганов")

    def resolve(self, author_name):
        return resolve_initiator(author_name)

    def test_exact_name_is_matched(self):
        self.assertEqual(self.resolve("Ваганов Сергей"), self.vaganov)

    def test_yo_spelling_is_matched(self):
        # В Okdesk «Нефедов», в справочнике «Нефёдов» — это один человек
        self.assertEqual(self.resolve("Нефедов Андрей"), self.nefedov)

    def test_patronymic_is_ignored(self):
        self.assertEqual(self.resolve("Ваганов Сергей Петрович"), self.vaganov)

    def test_case_does_not_matter(self):
        self.assertEqual(self.resolve("ВАГАНОВ СЕРГЕЙ"), self.vaganov)

    def test_email_instead_of_name_is_rejected(self):
        self.assertIsNone(self.resolve("vlasovay@enplus.digital vlasovay@enplus.digital"))

    def test_unknown_person_is_not_matched(self):
        self.assertIsNone(self.resolve("Толстобровов Алексей"))

    def test_other_first_name_is_not_matched(self):
        # Однофамилец с другим именем — не повод приписать заявку
        self.assertIsNone(self.resolve("Ваганов Андрей"))

    def test_namesakes_leave_initiator_empty(self):
        User = get_user_model()
        User.objects.create_user(username="vaganov2", first_name="Сергей", last_name="Ваганов")
        self.assertIsNone(self.resolve("Ваганов Сергей"))

    def test_patronymic_in_our_directory_is_ignored(self):
        # Из Keycloak отчество приезжает в first_name, а Okdesk шлёт только имя
        User = get_user_model()
        kuznetsov = User.objects.create_user(username="kuznetsov", first_name="Алексей Иванович", last_name="Кузнецов")
        self.assertEqual(self.resolve("Кузнецов Алексей"), kuznetsov)

    def test_blocked_namesake_does_not_hide_active_user(self):
        User = get_user_model()
        User.objects.create_user(username="vaganov_old", first_name="Сергей", last_name="Ваганов", is_active=False)
        self.assertEqual(self.resolve("Ваганов Сергей"), self.vaganov)

    def test_single_word_is_rejected(self):
        self.assertIsNone(self.resolve("Ваганов"))
        self.assertIsNone(self.resolve(""))

    def test_import_fills_initiator_from_author(self):
        OkdeskIssue.objects.create(
            issue_id=301,
            title="Заявка 301",
            contract_device=self.device,
            created_at=dt("2026-03-02", 14),
            status_name="Открыта",
            author_name="Ваганов Сергей",
        )

        with patch("contracts.services_okdesk_import._get", side_effect=fake_get({301: issue_detail(301)})):
            sync_requests()

        self.assertEqual(ServiceRequest.objects.get(external_number="301").initiator, self.vaganov)

    def test_sync_fills_initiator_of_earlier_import(self):
        # Заявки, попавшие в журнал до появления сопоставления, добираются обычным синком
        OkdeskIssue.objects.create(
            issue_id=302,
            title="Заявка 302",
            contract_device=self.device,
            created_at=dt("2026-03-02", 14),
            status_name="Открыта",
            author_name="Ваганов Сергей",
        )
        request = self.make_request(service_provider=self.okdesk, external_number="302")
        self.assertIsNone(request.initiator)

        with patch("contracts.services_okdesk_import._get", side_effect=fake_get({302: issue_detail(302)})):
            sync_requests()

        request.refresh_from_db()
        self.assertEqual(request.initiator, self.vaganov)

    def test_sync_does_not_overwrite_our_own_initiator(self):
        OkdeskIssue.objects.create(
            issue_id=303,
            title="Заявка 303",
            contract_device=self.device,
            created_at=dt("2026-03-02", 14),
            status_name="Открыта",
            author_name="Ваганов Сергей",
        )
        request = self.make_request(service_provider=self.okdesk, external_number="303", initiator=self.nefedov)

        with patch("contracts.services_okdesk_import._get", side_effect=fake_get({303: issue_detail(303)})):
            sync_requests()

        request.refresh_from_db()
        self.assertEqual(request.initiator, self.nefedov)


class ManualImportTests(ServiceRequestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.okdesk = ServiceProvider.objects.filter(issue_tracker=ServiceProvider.OKDESK).first()
        cls.okdesk.is_active = True
        cls.okdesk.save(update_fields=["is_active"])

    def test_import_with_device_creates_request(self):
        OkdeskIssue.objects.create(
            issue_id=201, title="Заявка 201", contract_device=None, created_at=dt("2026-03-02", 14)
        )

        with patch("contracts.services_okdesk_import._get", side_effect=fake_get({201: issue_detail(201)})):
            request = import_issue_with_device(201, self.device)

        self.assertEqual(request.device, self.device)
        self.assertEqual(request.external_number, "201")
        self.assertEqual(request.service_provider, self.okdesk)
        self.assertEqual(request.status, ServiceRequest.OPEN)
        self.assertEqual(request.messages.get().external_id, "issue-201")

    def test_import_is_idempotent_when_request_exists(self):
        existing = self.make_request(service_provider=self.okdesk, external_number="202")

        with patch("contracts.services_okdesk_import._get") as get_mock:
            result = import_issue_with_device(202, self.device)

        get_mock.assert_not_called()
        self.assertEqual(result, existing)

    def test_missing_mirror_row_raises(self):
        with self.assertRaises(OkdeskIssue.DoesNotExist):
            import_issue_with_device(999, self.device)

    def test_failure_mid_import_rolls_back_request(self):
        # Okdesk отдал заявку, но упал на комментариях — полузаведённой записи остаться не должно
        OkdeskIssue.objects.create(
            issue_id=203, title="Заявка 203", contract_device=None, created_at=dt("2026-03-02", 14)
        )

        def flaky(path, **params):
            if path.endswith("/comments"):
                raise requests.HTTPError(response=Mock(status_code=500))
            return issue_detail(203)

        with patch("contracts.services_okdesk_import._get", side_effect=flaky):
            with self.assertRaises(requests.HTTPError):
                import_issue_with_device(203, self.device)

        self.assertFalse(ServiceRequest.objects.filter(external_number="203").exists())

    def test_non_issue_payload_raises_and_creates_nothing(self):
        # Живой Okdesk на несуществующий номер отвечает 200 без заявки
        OkdeskIssue.objects.create(
            issue_id=204, title="Заявка 204", contract_device=None, created_at=dt("2026-03-02", 14)
        )

        with patch("contracts.services_okdesk_import._get", return_value={"errors": "not found"}):
            with self.assertRaises(requests.HTTPError):
                import_issue_with_device(204, self.device)

        self.assertFalse(ServiceRequest.objects.filter(external_number="204").exists())
