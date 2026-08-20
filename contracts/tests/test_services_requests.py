from datetime import datetime, time
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from contracts.models import (
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    Manufacturer,
    ServiceProvider,
    ServiceRequest,
    WorkSchedule,
)
from contracts.services_requests import (
    EmailChannel,
    OkdeskChannel,
    SubmissionContext,
    SubmissionError,
    build_description,
    channel_for_device,
    collects_urgency,
    submit_service_request,
)
from inventory.models import Organization


class SubmissionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        WorkSchedule.objects.create(
            name="Тестовый 5/2", work_start=time(8, 0), work_end=time(17, 0), weekdays="12345", is_default=True
        )
        cls.city = City.objects.create(name="Иркутск", timezone="Asia/Irkutsk", sla_standard_hours=8)
        cls.org = Organization.objects.create(name="ООО Тест")
        manufacturer = Manufacturer.objects.create(name="HP")
        cls.model = DeviceModel.objects.create(manufacturer=manufacturer, name="M404")
        cls.status = ContractStatus.objects.create(name="В работе")

        cls.email_provider = ServiceProvider.objects.create(
            name="Новый подрядчик",
            code="new",
            issue_tracker=ServiceProvider.EMAIL,
            support_email="sd@contractor.ru",
        )
        # АМБ заведена seed-миграцией 0008 — второй такой же строке мешает unique по name
        cls.okdesk_provider = ServiceProvider.objects.get(code="amb")

        cls.user = User.objects.create_user(
            username="ivanov", first_name="Иван", last_name="Иванов", email="ivanov@abi.ru"
        )

    def make_device(self, provider):
        return ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина, 1",
            room_number="204",
            model=self.model,
            serial_number="SN001",
            status=self.status,
            service_provider=provider,
        )

    def context(self):
        return SubmissionContext(user=self.user, phone="+7 999 000-00-00", service_type="Ремонт")


class ChannelRoutingTests(SubmissionBase):
    def test_email_provider_gets_email_channel(self):
        device = self.make_device(self.email_provider)
        self.assertIsInstance(channel_for_device(device), EmailChannel)

    def test_okdesk_provider_gets_api_channel(self):
        device = self.make_device(self.okdesk_provider)
        self.assertIsInstance(channel_for_device(device), OkdeskChannel)

    def test_provider_without_integration_is_refused(self):
        provider = ServiceProvider.objects.create(name="Без интеграции", code="manual")
        device = self.make_device(provider)
        with self.assertRaises(SubmissionError):
            channel_for_device(device)

    def test_device_without_provider_is_refused(self):
        device = self.make_device(None)
        with self.assertRaises(SubmissionError):
            channel_for_device(device)


class DescriptionTests(SubmissionBase):
    def test_body_contains_required_fields(self):
        device = self.make_device(self.email_provider)
        request = ServiceRequest.objects.create(
            device=device,
            description="Не печатает, мигает индикатор",
            initiator=self.user,
            initiator_contacts="Петров, +7 999 111-22-33",
            registered_at=datetime(2026, 3, 2, 14, tzinfo=ZoneInfo("Asia/Irkutsk")),
        )
        html, text = build_description(request, self.context())

        # Состав по п.6.6.2 ТЗ
        for expected in ("ул. Ленина, 1", "M404", "SN001", "Не печатает", "Иванов Иван"):
            self.assertIn(expected, html)
            self.assertIn(expected, text)
        self.assertIn(request.number, html)
        self.assertIn("Петров, +7 999 111-22-33", text)
        self.assertIn("Срочность: Обычная — печать остановлена, норматив 8 раб. ч", text)

    def test_body_contains_urgency_for_critical(self):
        device = self.make_device(self.email_provider)
        request = ServiceRequest.objects.create(
            device=device,
            description="Не печатает",
            initiator=self.user,
            is_critical=True,
            registered_at=datetime(2026, 3, 2, 14, tzinfo=ZoneInfo("Asia/Irkutsk")),
        )
        html, text = build_description(request, self.context())
        self.assertIn("КРИТИЧНАЯ — печать остановлена, норматив 4 раб. ч", html)
        self.assertIn("Срочность: КРИТИЧНАЯ", text)

    def test_html_is_escaped(self):
        device = self.make_device(self.email_provider)
        request = ServiceRequest.objects.create(
            device=device,
            description="<script>alert(1)</script>",
            initiator=self.user,
            registered_at=datetime(2026, 3, 2, 14, tzinfo=ZoneInfo("Asia/Irkutsk")),
        )
        html, _ = build_description(request, self.context())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class EmailSubmissionTests(SubmissionBase):
    # Без общего ящика: проверяем fallback-ветку reply_to (иначе тест зависел бы от .env)
    @override_settings(SERVICE_DESK_EMAIL="")
    def test_request_is_journaled_and_sent(self):
        device = self.make_device(self.email_provider)
        request = submit_service_request(device.id, "Не печатает", self.context())

        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertIsNotNone(request.deadline_at)
        self.assertEqual(request.service_provider, self.email_provider)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["sd@contractor.ru"])
        self.assertEqual(message.reply_to, ["ivanov@abi.ru"])
        self.assertIn(request.number, message.subject)
        self.assertIn("SN001", message.body)

    def test_provider_without_email_is_refused_and_nothing_journaled(self):
        provider = ServiceProvider.objects.create(name="Без почты", code="noemail", issue_tracker=ServiceProvider.EMAIL)
        device = self.make_device(provider)

        with self.assertRaises(SubmissionError):
            submit_service_request(device.id, "Не печатает", self.context())

        self.assertEqual(ServiceRequest.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_journal_flags_are_stored(self):
        device = self.make_device(self.email_provider)
        request = submit_service_request(
            device.id, "Посторонний шум", self.context(), stops_printing=False, is_critical=True
        )
        self.assertFalse(request.stops_printing)
        self.assertTrue(request.counts_in_sla)
        self.assertEqual(request.sla_hours, 4)

    def test_unknown_device_is_refused(self):
        with self.assertRaises(SubmissionError):
            submit_service_request(999999, "Не печатает", self.context())


class JournalOnlySubmissionTests(SubmissionBase):
    """Режим «только журнал»: заявка регистрируется, подрядчику ничего не уходит."""

    def setUp(self):
        self.provider = ServiceProvider.objects.create(
            name="Подрядчик без интеграции", code="journalonly", issue_tracker=ServiceProvider.JOURNAL
        )

    def test_request_is_journaled_without_sending(self):
        device = self.make_device(self.provider)
        with patch("contracts.services_requests.requests.post") as post:
            request = submit_service_request(device.id, "Не печатает", self.context())

        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(request.external_number, "")
        self.assertIsNotNone(request.deadline_at)
        self.assertEqual(len(mail.outbox), 0)
        post.assert_not_called()

    def test_urgency_from_client_is_ignored(self):
        # Форму срочности в этом режиме не показывают, поэтому присланные флаги не в счёт
        device = self.make_device(self.provider)
        request = submit_service_request(
            device.id, "Не печатает", self.context(), stops_printing=False, counts_in_sla=False, is_critical=True
        )

        self.assertTrue(request.stops_printing)
        self.assertTrue(request.counts_in_sla)
        self.assertFalse(request.is_critical)
        self.assertEqual(request.sla_hours, 8)


class ProviderUrgencyFlagTests(SubmissionBase):
    """Флаг подрядчика в админке: спрашиваем ли срочность и передаём ли её."""

    def test_flag_on_by_default(self):
        self.assertTrue(collects_urgency(self.make_device(self.email_provider)))

    def test_flag_off_hides_urgency(self):
        self.email_provider.collects_urgency = False
        self.email_provider.save(update_fields=["collects_urgency"])
        self.assertFalse(collects_urgency(self.make_device(self.email_provider)))

    def test_body_has_no_urgency_when_flag_off(self):
        self.email_provider.collects_urgency = False
        self.email_provider.save(update_fields=["collects_urgency"])
        device = self.make_device(self.email_provider)
        request = ServiceRequest.objects.create(
            device=device,
            description="Не печатает",
            initiator=self.user,
            is_critical=True,
            registered_at=datetime(2026, 3, 2, 14, tzinfo=ZoneInfo("Asia/Irkutsk")),
        )
        html, text = build_description(request, self.context())

        self.assertNotIn("Срочность:", text)
        self.assertNotIn("КРИТИЧНАЯ", html)

    def test_urgency_from_client_is_ignored_when_flag_off(self):
        self.email_provider.collects_urgency = False
        self.email_provider.save(update_fields=["collects_urgency"])
        device = self.make_device(self.email_provider)
        request = submit_service_request(
            device.id, "Не печатает", self.context(), stops_printing=False, counts_in_sla=False, is_critical=True
        )

        self.assertTrue(request.stops_printing)
        self.assertTrue(request.counts_in_sla)
        self.assertFalse(request.is_critical)
        self.assertEqual(request.sla_hours, 8)


class OkdeskSubmissionTests(SubmissionBase):
    def setUp(self):
        from access.models import UserOkdeskToken

        UserOkdeskToken.objects.create(user=self.user, encrypted_token="stub")

    @patch("contracts.services_requests.requests.post")
    @patch("access.models.UserOkdeskToken.get_token", return_value="secret")
    def test_external_number_is_saved(self, _token, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"id": 4242}
        post.return_value.raise_for_status.return_value = None

        device = self.make_device(self.okdesk_provider)
        request = submit_service_request(device.id, "Не печатает", self.context())

        self.assertEqual(request.external_number, "4242")
        self.assertEqual(len(mail.outbox), 0)

        from integrations.models import OkdeskIssue

        self.assertTrue(OkdeskIssue.objects.filter(issue_id=4242, contract_device=device).exists())

    @patch("contracts.services_requests.requests.post")
    @patch("access.models.UserOkdeskToken.get_token", return_value="secret")
    def test_api_failure_rolls_back_journal(self, _token, post):
        post.return_value.status_code = 401

        device = self.make_device(self.okdesk_provider)
        with self.assertRaises(SubmissionError):
            submit_service_request(device.id, "Не печатает", self.context())

        self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_missing_token_is_reported(self):
        from access.models import UserOkdeskToken

        UserOkdeskToken.objects.all().delete()
        device = self.make_device(self.okdesk_provider)
        with self.assertRaises(SubmissionError):
            submit_service_request(device.id, "Не печатает", self.context())


class OkdeskReplyTests(SubmissionBase):
    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.utils import timezone

        self.user.user_permissions.add(
            Permission.objects.get(codename="post_okdesk_comment", content_type__app_label="integrations")
        )
        self.user = User.objects.get(pk=self.user.pk)  # сброс кэша прав

        self.device = self.make_device(self.okdesk_provider)
        self.request_obj = ServiceRequest.objects.create(
            device=self.device,
            service_provider=self.okdesk_provider,
            description="Не печатает",
            initiator=self.user,
            external_number="4242",
            registered_at=timezone.now(),
        )

    @patch("integrations.services_okdesk_send.post_comment_to_okdesk", return_value={"id": 777})
    def test_reply_posts_comment_and_logs_message(self, post_comment):
        record = OkdeskChannel().reply(self.request_obj, "Когда приедет мастер?", user=self.user)

        post_comment.assert_called_once_with(self.user, 4242, "Когда приедет мастер?")
        self.assertEqual(record.channel, ServiceProvider.OKDESK)
        self.assertEqual(record.direction, record.OUTGOING)
        self.assertEqual(record.external_id, "777")
        self.assertEqual(record.service_request, self.request_obj)
        self.assertEqual(record.from_email, "Иванов Иван")

    @patch("integrations.services_okdesk_send.post_comment_to_okdesk")
    def test_reply_without_permission_is_refused(self, post_comment):
        self.user.user_permissions.clear()
        user = User.objects.get(pk=self.user.pk)

        with self.assertRaises(SubmissionError) as ctx:
            OkdeskChannel().reply(self.request_obj, "Текст", user=user)

        self.assertEqual(ctx.exception.status, 403)
        post_comment.assert_not_called()

    @patch("integrations.services_okdesk_send.post_comment_to_okdesk")
    def test_reply_with_attachments_is_refused(self, post_comment):
        with self.assertRaises(SubmissionError) as ctx:
            OkdeskChannel().reply(self.request_obj, "Текст", attachments=[object()], user=self.user)

        self.assertEqual(ctx.exception.status, 400)
        post_comment.assert_not_called()

    @patch("integrations.services_okdesk_send.post_comment_to_okdesk")
    def test_reply_without_external_number_is_refused(self, post_comment):
        self.request_obj.external_number = ""

        with self.assertRaises(SubmissionError) as ctx:
            OkdeskChannel().reply(self.request_obj, "Текст", user=self.user)

        self.assertEqual(ctx.exception.status, 409)
        post_comment.assert_not_called()

    @patch("integrations.services_okdesk_send.post_comment_to_okdesk")
    def test_api_error_maps_to_submission_error(self, post_comment):
        from integrations.services_okdesk_send import OkdeskSendError

        post_comment.side_effect = OkdeskSendError("Заявка #4242 не найдена в Okdesk.", status_code=404)

        with self.assertRaises(SubmissionError) as ctx:
            OkdeskChannel().reply(self.request_obj, "Текст", user=self.user)

        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(self.request_obj.messages.count(), 0)
