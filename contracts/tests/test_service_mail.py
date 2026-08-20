"""Приём ответных писем подрядчика: узнавание заявки, дубли, вложения."""

import shutil
import tempfile
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from django.test import override_settings

from contracts.models import ServiceRequestMessage
from contracts.services_mail import ingest_email

from .test_service_requests import ServiceRequestBase, dt

MEDIA_ROOT = tempfile.mkdtemp(prefix="service-mail-test-")


def build_email(subject="", body="Приняли в работу", *, in_reply_to="", attachments=(), message_id=None):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "service@provider.example"
    message["To"] = "servicedesk@company.example"
    message["Message-ID"] = message_id or make_msgid(domain="provider.example")
    message["Date"] = format_datetime(dt("2026-03-02", 16))
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
    message.set_content(body)

    for filename, payload in attachments:
        message.add_attachment(payload, maintype="application", subtype="pdf", filename=filename)
    return message.as_bytes()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class IngestTests(ServiceRequestBase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.request = self.make_request()

    def test_matches_request_by_number_in_subject(self):
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}. Ремонт. Иркутск. SN001"))

        message = ServiceRequestMessage.objects.get()
        self.assertEqual(message.service_request, self.request)
        self.assertEqual(message.direction, ServiceRequestMessage.INCOMING)
        self.assertEqual(message.from_email, "service@provider.example")
        self.assertIn("Приняли в работу", message.body_text)

    def test_matches_request_by_thread_headers_when_subject_changed(self):
        outgoing = ServiceRequestMessage.objects.create(
            service_request=self.request,
            direction=ServiceRequestMessage.OUTGOING,
            external_id="<our-letter@company.example>",
            subject=f"Заявка № {self.request.number}",
            sent_at=dt("2026-03-02", 14),
        )

        ingest_email(build_email(subject="По вашему обращению", in_reply_to=outgoing.external_id))

        message = ServiceRequestMessage.objects.filter(direction=ServiceRequestMessage.INCOMING).get()
        self.assertEqual(message.service_request, self.request)

    def test_unknown_number_leaves_message_unmatched(self):
        ingest_email(build_email(subject="Re: Заявка № 2026-99999. Ремонт"))

        message = ServiceRequestMessage.objects.get()
        self.assertIsNone(message.service_request_id)

    def test_wrong_year_in_number_does_not_match(self):
        # Номер выводится из года регистрации: та же заявка, но год чужой
        _, _, pk_part = self.request.number.partition("-")
        ingest_email(build_email(subject=f"Re: Заявка № 2019-{pk_part}"))

        self.assertIsNone(ServiceRequestMessage.objects.get().service_request_id)

    def test_same_letter_is_not_stored_twice(self):
        raw = build_email(subject=f"Re: Заявка № {self.request.number}")

        self.assertIsNotNone(ingest_email(raw))
        self.assertIsNone(ingest_email(raw))
        self.assertEqual(ServiceRequestMessage.objects.count(), 1)

    def test_attachment_is_saved_with_original_name(self):
        ingest_email(
            build_email(
                subject=f"Re: Заявка № {self.request.number}",
                attachments=[("Технический акт №77.pdf", b"%PDF-1.4 fake")],
            )
        )

        attachment = ServiceRequestMessage.objects.get().attachments.get()
        self.assertEqual(attachment.filename, "Технический акт №77.pdf")
        self.assertEqual(attachment.size, len(b"%PDF-1.4 fake"))
        # Имя из письма в путь не попадает — только расширение
        self.assertTrue(attachment.file.name.startswith("service-mail/"))
        self.assertTrue(attachment.file.name.endswith(".pdf"))
        self.assertNotIn("Технический", attachment.file.name)

    def test_html_only_letter_is_stored_as_text(self):
        message = EmailMessage()
        message["Subject"] = f"Re: Заявка № {self.request.number}"
        message["From"] = "service@provider.example"
        message["Message-ID"] = make_msgid(domain="provider.example")
        message["Date"] = format_datetime(dt("2026-03-02", 16))
        message.set_content("<p>Мастер выехал</p>", subtype="html")

        ingest_email(message.as_bytes())

        self.assertIn("Мастер выехал", ServiceRequestMessage.objects.get().body_text)

    def test_letter_without_date_header_still_accepted(self):
        message = EmailMessage()
        message["Subject"] = f"Re: Заявка № {self.request.number}"
        message["From"] = "service@provider.example"
        message["Message-ID"] = make_msgid(domain="provider.example")
        message.set_content("Без даты")

        ingest_email(message.as_bytes())

        self.assertIsNotNone(ServiceRequestMessage.objects.get().sent_at)


@override_settings(
    SERVICE_DESK_EMAIL="servicedesk@company.example",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OutgoingLetterTests(ServiceRequestBase):
    """Письмо-заявка должно быть началом треда, иначе ответ не с чем связать."""

    def test_reply_goes_to_shared_mailbox_and_letter_is_logged(self):
        from django.contrib.auth import get_user_model
        from django.core import mail

        from contracts.services_requests import SubmissionContext, submit_service_request

        self.provider.issue_tracker = self.provider.EMAIL
        self.provider.support_email = "help@provider.example"
        self.provider.save(update_fields=["issue_tracker", "support_email"])

        user = get_user_model().objects.create_user("ivanov", email="ivanov@company.example", password="x")
        service_request = submit_service_request(self.device.pk, "Не печатает", SubmissionContext(user=user))

        letter = mail.outbox[0]
        self.assertEqual(letter.from_email, "servicedesk@company.example")
        self.assertEqual(letter.reply_to, ["servicedesk@company.example"])
        self.assertEqual(letter.cc, ["ivanov@company.example"])

        logged = service_request.messages.get()
        self.assertEqual(logged.direction, ServiceRequestMessage.OUTGOING)
        self.assertEqual(logged.external_id, letter.extra_headers["Message-ID"])

    def test_answer_to_our_letter_lands_in_the_same_thread(self):
        from django.contrib.auth import get_user_model

        from contracts.services_requests import SubmissionContext, submit_service_request

        self.provider.issue_tracker = self.provider.EMAIL
        self.provider.support_email = "help@provider.example"
        self.provider.save(update_fields=["issue_tracker", "support_email"])

        user = get_user_model().objects.create_user("petrov", email="petrov@company.example", password="x")
        service_request = submit_service_request(self.device.pk, "Не печатает", SubmissionContext(user=user))
        outgoing = service_request.messages.get()

        ingest_email(build_email(subject="Ответ без номера", in_reply_to=outgoing.external_id))

        self.assertEqual(service_request.messages.count(), 2)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AutoCloseTests(ServiceRequestBase):
    """Заявку закрывает только связка «тема по п. 6.6.4 ТЗ + скан акта»."""

    CLOSING_SUBJECT = "Работоспособность Оборудования восстановлена"

    def setUp(self):
        self.request = self.make_request()

    def closing_letter(self, *, subject=None, attachments=(("Акт №77.pdf", b"%PDF-1.4 fake"),)):
        return build_email(
            subject=subject if subject is not None else f"Re: Заявка № {self.request.number}. {self.CLOSING_SUBJECT}",
            attachments=attachments,
        )

    def test_formal_letter_with_act_closes_request(self):
        ingest_email(self.closing_letter())

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.CLOSED)
        self.assertEqual(self.request.restored_at, dt("2026-03-02", 16))
        self.assertEqual(self.request.closed_at, dt("2026-03-02", 16))
        self.assertTrue(self.request.act_scan)
        self.assertEqual(self.request.closing_message, ServiceRequestMessage.objects.get())

    def test_letter_without_attachment_does_not_close(self):
        ingest_email(self.closing_letter(attachments=()))

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.OPEN)

    def test_act_in_ordinary_letter_does_not_close(self):
        ingest_email(self.closing_letter(subject=f"Re: Заявка № {self.request.number}. Отчёт мастера"))

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.OPEN)

    def test_manual_restoration_time_is_kept(self):
        # Подрядчик пишет позже, чем чинит: наша отметка ближе к правде и остаётся
        self.request.restored_at = dt("2026-03-02", 15)
        self.request.save()

        ingest_email(self.closing_letter())

        self.request.refresh_from_db()
        self.assertEqual(self.request.restored_at, dt("2026-03-02", 15))
        self.assertEqual(self.request.closed_at, dt("2026-03-02", 16))

    def test_closed_request_is_not_reclosed_by_next_letter(self):
        ingest_email(self.closing_letter())
        self.request.refresh_from_db()
        first_scan = self.request.act_scan.name

        ingest_email(self.closing_letter(attachments=(("Акт №78.pdf", b"%PDF-1.4 other"),)))

        self.request.refresh_from_db()
        self.assertEqual(self.request.act_scan.name, first_scan)

    def test_rejected_request_is_not_closed(self):
        self.request.status = self.request.REJECTED
        self.request.save()

        ingest_email(self.closing_letter())

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.REJECTED)

    def test_letter_dated_before_registration_is_left_to_human(self):
        message = EmailMessage()
        message["Subject"] = f"Re: Заявка № {self.request.number}. {self.CLOSING_SUBJECT}"
        message["From"] = "service@provider.example"
        message["Message-ID"] = make_msgid(domain="provider.example")
        message["Date"] = format_datetime(dt("2026-03-01", 9))
        message.set_content("Акт во вложении")
        message.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="Акт.pdf")

        ingest_email(message.as_bytes())

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.OPEN)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MessagesApiTests(ServiceRequestBase):
    """Лента и разбор непривязанных писем в журнале."""

    def setUp(self):
        from django.contrib.auth.models import Permission, User

        self.request = self.make_request()
        self.user = User.objects.create_user("operator", password="x")
        for codename in ("access_contracts_app", "view_servicerequest", "close_service_request"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        # Явный backend: с OIDC-бэкендом SessionRefresh уводит запрос на Keycloak
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def test_thread_returns_messages_with_attachments(self):
        from django.urls import reverse

        ingest_email(
            build_email(
                subject=f"Re: Заявка № {self.request.number}",
                attachments=[("act.pdf", b"%PDF-1.4 fake")],
            )
        )

        response = self.client.get(reverse("contracts:api_request_messages", args=[self.request.pk]))

        message = response.json()["messages"][0]
        self.assertEqual(message["direction"], "in")
        self.assertEqual(message["attachments"][0]["filename"], "act.pdf")

    def test_unmatched_letter_can_be_attached_by_number(self):
        from django.urls import reverse

        ingest_email(build_email(subject="Ваша заявка принята"))
        message = ServiceRequestMessage.objects.get()

        listed = self.client.get(reverse("contracts:api_unmatched_messages")).json()["messages"]
        self.assertEqual(len(listed), 1)

        response = self.client.post(
            reverse("contracts:api_message_attach", args=[message.pk]), {"number": self.request.number}
        )

        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertEqual(message.service_request, self.request)
        self.assertEqual(self.client.get(reverse("contracts:api_unmatched_messages")).json()["messages"], [])

    def test_attach_rejects_unknown_number(self):
        from django.urls import reverse

        ingest_email(build_email(subject="Ваша заявка принята"))
        message = ServiceRequestMessage.objects.get()

        response = self.client.post(
            reverse("contracts:api_message_attach", args=[message.pk]), {"number": "2026-99999"}
        )

        self.assertEqual(response.status_code, 404)
        message.refresh_from_db()
        self.assertIsNone(message.service_request_id)

    def test_attaching_formal_letter_closes_request(self):
        from django.urls import reverse

        # Тема без нашего номера: к какой заявке письмо, становится ясно только при привязке
        ingest_email(
            build_email(
                subject="Работоспособность Оборудования восстановлена",
                attachments=[("Акт №77.pdf", b"%PDF-1.4 fake")],
            )
        )
        message = ServiceRequestMessage.objects.get()

        response = self.client.post(
            reverse("contracts:api_message_attach", args=[message.pk]), {"number": self.request.number}
        )

        self.assertTrue(response.json()["closed_by_letter"])
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, self.request.CLOSED)

    def test_journal_keeps_newest_first_with_message_counter(self):
        from django.urls import reverse

        older = self.make_request(registered_at=dt("2026-03-01", 10), description="Старая")
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        listed = self.client.get(reverse("contracts:api_requests"), {"status": ""}).json()["requests"]

        self.assertEqual([item["number"] for item in listed], [self.request.number, older.number])
        self.assertEqual([item["messages_count"] for item in listed], [1, 0])


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ReplyApiTests(ServiceRequestBase):
    """Ответ подрядчику из ленты: адресат, тред и запись в переписке."""

    def setUp(self):
        from django.contrib.auth.models import Permission, User

        self.provider.issue_tracker = self.provider.EMAIL
        self.provider.support_email = "help@provider.example"
        self.provider.save(update_fields=["issue_tracker", "support_email"])

        self.request = self.make_request()
        self.user = User.objects.create_user("operator", password="x")
        for codename in ("access_contracts_app", "view_servicerequest"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def post_reply(self, **payload):
        from django.urls import reverse

        return self.client.post(reverse("contracts:api_request_reply", args=[self.request.pk]), payload)

    def test_reply_goes_to_the_last_answering_person(self):
        from django.core import mail

        # Заявку принял сервис-деск, ведёт её мастер со своего адреса — отвечаем мастеру
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))
        ServiceRequestMessage.objects.update(from_email="Мастер <master@provider.example>")

        response = self.post_reply(text="Когда приедете?")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].to, ["master@provider.example"])

    def test_reply_falls_back_to_provider_mailbox(self):
        from django.core import mail

        self.post_reply(text="Напоминаем о заявке")

        self.assertEqual(mail.outbox[0].to, ["help@provider.example"])

    def test_reply_is_signed_with_author_name_and_phone(self):
        from django.core import mail

        from access.models import UserProfile

        # Письмо уходит с общего адреса сервис-деска — без подписи подрядчик не видит собеседника
        self.user.first_name, self.user.last_name = "Иван", "Петров"
        self.user.save(update_fields=["first_name", "last_name"])
        UserProfile.objects.create(user=self.user, phone="+7 999 000-00-01")

        self.post_reply(text="Когда приедете?")

        self.assertIn("С уважением, Петров Иван\n+7 999 000-00-01", mail.outbox[0].body)
        self.assertIn("С уважением, Петров Иван", self.request.messages.latest("pk").body_text)

    def test_reply_keeps_thread_headers_and_our_number(self):
        from django.core import mail

        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}", message_id="<theirs@provider.example>"))

        self.post_reply(text="Уточните срок")

        letter = mail.outbox[0]
        self.assertEqual(letter.extra_headers["In-Reply-To"], "<theirs@provider.example>")
        self.assertIn(self.request.number, letter.subject)

    def test_reply_with_attachment_lands_in_the_feed(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.post_reply(
            text="Фото ошибки", attachments=SimpleUploadedFile("error.png", b"png-bytes", "image/png")
        )

        message = self.request.messages.get()
        self.assertEqual(message.direction, ServiceRequestMessage.OUTGOING)
        self.assertEqual(response.json()["message"]["attachments"][0]["filename"], "error.png")
        self.assertEqual(message.attachments.get().size, len(b"png-bytes"))

    def test_empty_reply_is_rejected(self):
        response = self.post_reply(text="   ")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.request.messages.exists())

    def test_reply_without_provider_mailbox_is_refused(self):
        self.provider.support_email = ""
        self.provider.save(update_fields=["support_email"])

        response = self.post_reply(text="Напоминаем о заявке")

        self.assertEqual(response.status_code, 409)

    def test_reply_goes_to_chosen_address_from_thread(self):
        from django.core import mail

        # В переписке два адреса: сервис-деск принял, мастер ведёт — отвечаем сервис-деску
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}", body="Выехал"))
        ServiceRequestMessage.objects.filter(body_text__contains="Выехал").update(from_email="master@provider.example")

        response = self.post_reply(text="Вопрос по заявке", to="service@provider.example")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].to, ["service@provider.example"])

    def test_reply_to_foreign_address_is_refused(self):
        response = self.post_reply(text="Вопрос", to="stranger@evil.example")

        self.assertEqual(response.status_code, 400)
        self.assertIn("не из переписки", response.json()["error"])

    def test_reply_options_include_thread_addresses_and_provider_mailbox(self):
        from django.urls import reverse

        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        response = self.client.get(reverse("contracts:api_request_messages", args=[self.request.pk]))

        self.assertEqual(response.json()["reply_options"], ["service@provider.example", "help@provider.example"])

    def test_colleague_from_system_can_be_cc_ed(self):
        from django.contrib.auth.models import User
        from django.core import mail

        User.objects.create_user("kollega", email="kollega@company.example", password="x")

        response = self.post_reply(text="Держу в курсе", cc="kollega@company.example")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].cc, ["kollega@company.example"])
        self.assertIn("kollega@company.example", self.request.messages.get().to_emails)

    def test_cc_to_stranger_is_refused(self):
        response = self.post_reply(text="Держу в курсе", cc="stranger@evil.example")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Не сотрудники системы", response.json()["error"])

    def test_reply_notifies_subscribed_colleague_but_not_author(self):
        from django.contrib.auth.models import User

        from contracts.models import ServiceRequestSubscription

        colleague = User.objects.create_user("kollega", email="kollega@company.example", password="x")
        ServiceRequestSubscription.objects.create(user=colleague, service_request=self.request)

        self.post_reply(text="Уточнил у мастера")

        self.assertEqual(colleague.notifications.count(), 1)
        self.assertIn("operator", colleague.notifications.get().subtitle)
        self.assertFalse(self.user.notifications.exists())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SubscriptionTests(ServiceRequestBase):
    """Подписка на заявку и уведомления в колокольчике."""

    def setUp(self):
        from django.contrib.auth.models import Permission, User

        from contracts.models import ServiceRequestSubscription

        self.request = self.make_request()
        self.user = User.objects.create_user("operator", password="x")
        for codename in ("access_contracts_app", "view_servicerequest"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.subscription = ServiceRequestSubscription.objects.create(user=self.user, service_request=self.request)

    def bell(self, history=False):
        from django.urls import reverse

        return self.client.get(reverse("access:notifications_api"), {"history": "1"} if history else {}).json()

    def open_thread(self):
        from django.urls import reverse

        return self.client.get(reverse("contracts:api_request_messages", args=[self.request.pk]))

    def test_initiator_is_subscribed_when_submitting(self):
        from django.contrib.auth import get_user_model

        from contracts.models import ServiceRequestSubscription
        from contracts.services_requests import SubmissionContext, submit_service_request

        self.provider.issue_tracker = self.provider.EMAIL
        self.provider.support_email = "help@provider.example"
        self.provider.save(update_fields=["issue_tracker", "support_email"])

        author = get_user_model().objects.create_user("sidorov", email="sidorov@company.example", password="x")
        submitted = submit_service_request(self.device.pk, "Не печатает", SubmissionContext(user=author))

        self.assertTrue(ServiceRequestSubscription.objects.filter(user=author, service_request=submitted).exists())

    def test_incoming_letter_shows_up_in_the_bell(self):
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        payload = self.bell()

        self.assertEqual(payload["unread_count"], 1)
        self.assertIn(self.request.number, payload["items"][0]["title"])
        self.assertIn(f"request={self.request.pk}", payload["items"][0]["url"])

    def test_opening_the_thread_marks_notifications_read(self):
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        self.open_thread()

        self.assertEqual(self.bell()["unread_count"], 0)

    def test_marking_one_notification_leaves_the_other_unread(self):
        from django.urls import reverse

        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}", body="Мастер выехал"))

        first, second = self.bell()["items"]
        self.client.post(reverse("access:notification_read_api", args=[first["id"]]))

        payload = self.bell()
        self.assertEqual(payload["unread_count"], 1)
        self.assertEqual([item["id"] for item in payload["items"]], [second["id"]])

    def test_read_all_empties_the_bell_but_history_remains(self):
        from django.urls import reverse

        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        self.client.post(reverse("access:notifications_read_all_api"))

        self.assertEqual(self.bell()["items"], [])
        history = self.bell(history=True)["items"]
        self.assertEqual(len(history), 1)
        self.assertTrue(history[0]["read"])

    def test_repeated_notification_for_the_same_letter_is_not_duplicated(self):
        from contracts.services_request_notifications import notify_subscribers

        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))
        notify_subscribers(ServiceRequestMessage.objects.get(direction=ServiceRequestMessage.INCOMING))

        self.assertEqual(self.bell()["unread_count"], 1)

    def test_colleague_comment_notifies_subscribers_but_not_author(self):
        from django.contrib.auth.models import User

        from contracts.services_request_notifications import notify_subscribers

        author = User.objects.create_user("colleague", password="x", first_name="Иван", last_name="Петров")
        outgoing = ServiceRequestMessage.objects.create(
            service_request=self.request,
            direction=ServiceRequestMessage.OUTGOING,
            subject=f"Заявка № {self.request.number}",
            body_text="Уточнил у мастера, приедет завтра",
            sent_at=dt("2026-03-02", 15),
        )
        notify_subscribers(outgoing, author=author)

        payload = self.bell()
        self.assertEqual(payload["unread_count"], 1)
        self.assertIn("Иван Петров", payload["items"][0]["subtitle"])
        self.assertFalse(author.notifications.exists())

    def test_request_without_subscription_stays_silent(self):
        self.subscription.delete()
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        self.assertEqual(self.bell()["unread_count"], 0)

    def test_subscription_can_be_toggled_from_the_thread(self):
        from django.urls import reverse

        from contracts.models import ServiceRequestSubscription

        url = reverse("contracts:api_request_subscribe", args=[self.request.pk])

        self.assertFalse(self.client.post(url, {"on": "0"}).json()["subscribed"])
        self.assertFalse(ServiceRequestSubscription.objects.filter(user=self.user).exists())

        self.assertTrue(self.client.post(url, {"on": "1"}).json()["subscribed"])
        self.assertTrue(ServiceRequestSubscription.objects.filter(user=self.user).exists())

    def test_fresh_subscription_does_not_resurrect_old_letters(self):
        from django.urls import reverse

        self.subscription.delete()
        ingest_email(build_email(subject=f"Re: Заявка № {self.request.number}"))

        self.client.post(reverse("contracts:api_request_subscribe", args=[self.request.pk]), {"on": "1"})

        self.assertEqual(self.bell()["unread_count"], 0)


class StubImap:
    """Соединение для проверки квоты: отдаёт заготовленный ответ GETQUOTAROOT."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def getquotaroot(self, folder):
        if self.error:
            raise self.error
        return self.response


@override_settings(SERVICE_DESK_IMAP_USER="servicedesk@company.example")
class MailboxQuotaTests(ServiceRequestBase):
    """Тревога администраторам, когда общий ящик подходит к квоте."""

    def setUp(self):
        from django.contrib.auth.models import User

        self.admin = User.objects.create_superuser("admin", "admin@company.example", "x")

    def alerts(self):
        from access.models import Notification

        return Notification.objects.filter(user=self.admin, kind=Notification.MAILBOX_QUOTA)

    def quota_response(self, used_kb, limit_kb):
        return ("OK", [[b'"INBOX" ""'], [f'"" (STORAGE {used_kb} {limit_kb})'.encode()]])

    def test_nearly_full_mailbox_alerts_superusers(self):
        from contracts.services_mail import check_mailbox_quota

        ratio = check_mailbox_quota(StubImap(self.quota_response(900 * 1024, 1000 * 1024)))

        self.assertEqual(ratio, 0.9)
        alert = self.alerts().get()
        self.assertIn("90%", alert.title)
        self.assertIn("900 из 1000 МБ", alert.subtitle)

    def test_half_empty_mailbox_stays_silent(self):
        from contracts.services_mail import check_mailbox_quota

        ratio = check_mailbox_quota(StubImap(self.quota_response(400 * 1024, 1000 * 1024)))

        self.assertEqual(ratio, 0.4)
        self.assertFalse(self.alerts().exists())

    def test_same_day_alert_is_not_duplicated(self):
        from contracts.services_mail import check_mailbox_quota

        connection = StubImap(self.quota_response(900 * 1024, 1000 * 1024))
        check_mailbox_quota(connection)
        check_mailbox_quota(connection)

        self.assertEqual(self.alerts().count(), 1)

    def test_server_without_quota_support_is_ignored(self):
        import imaplib

        from contracts.services_mail import check_mailbox_quota

        self.assertIsNone(check_mailbox_quota(StubImap(error=imaplib.IMAP4.error("GETQUOTAROOT unknown"))))
        self.assertIsNone(check_mailbox_quota(StubImap(("NO", [None]))))
        self.assertFalse(self.alerts().exists())
