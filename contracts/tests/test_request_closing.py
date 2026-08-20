import shutil
import tempfile

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from contracts.models import ServiceProvider, ServiceRequest, ServiceRequestAttachment, ServiceRequestMessage
from contracts.services_request_closing import close_by_act, close_by_message, mark_restored

from .test_service_requests import ServiceRequestBase, dt

MEDIA_ROOT = tempfile.mkdtemp(prefix="acts-test-")


def act_file(name="act.pdf", content=b"%PDF-1.4 fake"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RestorationTests(ServiceRequestBase):
    def test_restoration_sets_status_and_stops_downtime(self):
        request = self.make_request()
        mark_restored(request, dt("2026-03-02", 16))

        self.assertEqual(request.status, ServiceRequest.RESTORED)
        # С 14:00 до 16:00 понедельника — два рабочих часа, дальше простой не растёт
        self.assertEqual(request.downtime_hours(), 2.0)

    def test_restoration_before_registration_is_rejected(self):
        request = self.make_request()
        with self.assertRaises(ValidationError) as ctx:
            mark_restored(request, dt("2026-03-02", 10))

        # Время регистрации в сообщении — местное, а не UTC: иначе не сойдётся с журналом
        self.assertIn("02.03.2026 14:00", str(ctx.exception))

    def test_restoration_in_future_is_rejected(self):
        request = self.make_request()
        with self.assertRaises(ValidationError):
            mark_restored(request, timezone.now() + timezone.timedelta(hours=1))

    def test_provider_figures_are_kept_alongside_ours(self):
        request = self.make_request()
        mark_restored(
            request,
            dt("2026-03-02", 16),
            provider_restored_at=dt("2026-03-02", 15),
            provider_downtime_hours="1.00",
        )

        self.assertEqual(request.provider_restored_at, dt("2026-03-02", 15))
        self.assertEqual(request.restoration_discrepancy_hours, 1.0)
        # Наш простой считается по нашей отметке, чужие цифры на него не влияют
        self.assertEqual(request.downtime_hours(), 2.0)

    def test_rejected_request_cannot_be_restored(self):
        request = self.make_request(status=ServiceRequest.REJECTED)
        with self.assertRaises(ValidationError):
            mark_restored(request, dt("2026-03-02", 16))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ActTests(ServiceRequestBase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def restored_request(self):
        request = self.make_request()
        mark_restored(request, dt("2026-03-02", 16))
        return request

    def test_act_closes_request(self):
        request = self.restored_request()
        close_by_act(request, act_file=act_file(), act_number="ТА-17", closed_at=dt("2026-03-03", 10))

        self.assertEqual(request.status, ServiceRequest.CLOSED)
        self.assertEqual(request.act_number, "ТА-17")
        self.assertEqual(request.act_scan.name, f"service-acts/2026/{request.number}.pdf")

    def test_closing_without_scan_is_rejected(self):
        request = self.restored_request()
        with self.assertRaises(ValidationError):
            close_by_act(request, act_number="ТА-17")

    def test_closing_without_restoration_is_rejected(self):
        request = self.make_request()
        with self.assertRaises(ValidationError):
            close_by_act(request, act_file=act_file())

    def test_act_earlier_than_restoration_is_rejected(self):
        request = self.restored_request()
        with self.assertRaises(ValidationError):
            close_by_act(request, act_file=act_file(), closed_at=dt("2026-03-02", 15))

    def test_foreign_extension_is_rejected(self):
        request = self.restored_request()
        with self.assertRaises(ValidationError):
            close_by_act(request, act_file=act_file(name="act.exe"))

    def test_oversized_scan_is_rejected(self):
        request = self.restored_request()
        with self.assertRaises(ValidationError):
            close_by_act(request, act_file=act_file(content=b"x" * (10 * 1024 * 1024 + 1)))

    def test_repeated_upload_replaces_scan(self):
        request = self.restored_request()
        close_by_act(request, act_file=act_file(), act_number="ТА-17", closed_at=dt("2026-03-03", 10))
        close_by_act(request, act_number="ТА-18", closed_at=dt("2026-03-03", 10))

        self.assertEqual(request.act_number, "ТА-18")
        self.assertEqual(request.status, ServiceRequest.CLOSED)


def incoming_message(service_request, *, filename="Акт №77.pdf", subject="Re: по вашей заявке", direction=None):
    message = ServiceRequestMessage.objects.create(
        service_request=service_request,
        direction=direction or ServiceRequestMessage.INCOMING,
        subject=subject,
        sent_at=dt("2026-03-02", 16),
    )
    if filename:
        ServiceRequestAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile(filename, b"%PDF-1.4 fake"),
            filename=filename,
            size=13,
        )
    return message


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CloseByMessageTests(ServiceRequestBase):
    """Ручное закрытие письмом: акт пришёл, но тема не формальная и автозакрытие молчит."""

    def setUp(self):
        self.request = self.make_request()

    def test_informal_letter_with_act_closes_request(self):
        message = incoming_message(self.request)
        close_by_message(self.request, message)

        self.assertEqual(self.request.status, ServiceRequest.CLOSED)
        self.assertEqual(self.request.restored_at, dt("2026-03-02", 16))
        self.assertEqual(self.request.closing_message, message)
        self.assertTrue(self.request.act_scan)

    def test_iphone_photo_counts_as_act(self):
        message = incoming_message(self.request, filename="IMG_0042.HEIC")
        close_by_message(self.request, message)

        self.assertEqual(self.request.status, ServiceRequest.CLOSED)

    def test_letter_without_act_attachment_is_rejected(self):
        message = incoming_message(self.request, filename="")
        with self.assertRaises(ValidationError):
            close_by_message(self.request, message)

    def test_own_outgoing_letter_is_rejected(self):
        message = incoming_message(self.request, direction=ServiceRequestMessage.OUTGOING)
        with self.assertRaises(ValidationError):
            close_by_message(self.request, message)

    def test_closed_request_is_rejected(self):
        message = incoming_message(self.request)
        close_by_message(self.request, message)
        with self.assertRaises(ValidationError):
            close_by_message(self.request, message)

    def test_manual_restoration_time_is_kept(self):
        self.request.restored_at = dt("2026-03-02", 15)
        self.request.save()

        close_by_message(self.request, incoming_message(self.request))

        self.assertEqual(self.request.restored_at, dt("2026-03-02", 15))
        self.assertEqual(self.request.closed_at, dt("2026-03-02", 16))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class JournalApiTests(ServiceRequestBase):
    def setUp(self):
        # Доступ к приложению требует AppAccessMiddleware для всего namespace contracts
        self.viewer = self.make_user("viewer", "view_servicerequest")
        self.initiator = self.make_user("initiator", "create_service_request")

    def make_user(self, username, *codenames):
        user = User.objects.create_user(username, password="x")
        user.user_permissions.add(Permission.objects.get(codename="access_contracts_app"))
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        return user

    def login(self, user):
        # Явный backend обязателен: с OIDC-бэкендом SessionRefresh заворачивает
        # запросы на Keycloak, которого в тестах нет
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_initiator_sees_only_own_requests(self):
        mine = self.make_request(initiator=self.initiator)
        self.make_request(description="Чужая")

        self.login(self.initiator)
        response = self.client.get(reverse("contracts:api_requests"), {"status": ""})

        numbers = [item["number"] for item in response.json()["requests"]]
        self.assertEqual(numbers, [mine.number])

    def test_search_finds_request_by_initiator(self):
        self.initiator.first_name, self.initiator.last_name = "Пётр", "Кузнецов"
        self.initiator.save(update_fields=["first_name", "last_name"])
        mine = self.make_request(initiator=self.initiator)
        self.make_request(description="Чужая")

        self.login(self.viewer)
        response = self.client.get(reverse("contracts:api_requests"), {"status": "", "q": "Пётр Кузнецов"})

        numbers = [item["number"] for item in response.json()["requests"]]
        self.assertEqual(numbers, [mine.number])

    def test_search_finds_request_by_initiator_contacts(self):
        mine = self.make_request(initiator=self.initiator, initiator_contacts="Сидорова, доб. 245")

        self.login(self.viewer)
        response = self.client.get(reverse("contracts:api_requests"), {"status": "", "q": "Сидорова"})

        numbers = [item["number"] for item in response.json()["requests"]]
        self.assertEqual(numbers, [mine.number])

    def test_restoration_requires_permission(self):
        request = self.make_request()
        self.login(self.viewer)

        response = self.client.post(reverse("contracts:api_request_restore", args=[request.pk]), {})

        self.assertEqual(response.status_code, 403)
        request.refresh_from_db()
        self.assertIsNone(request.restored_at)

    def test_restoration_via_api(self):
        request = self.make_request()
        self.viewer.user_permissions.add(Permission.objects.get(codename="close_service_request"))
        self.login(self.viewer)

        response = self.client.post(
            reverse("contracts:api_request_restore", args=[request.pk]),
            {"restored_at": "2026-03-02T16:00"},
        )

        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.restored_at, dt("2026-03-02", 16))

    def test_validation_error_returns_message(self):
        request = self.make_request()
        self.viewer.user_permissions.add(Permission.objects.get(codename="close_service_request"))
        self.login(self.viewer)

        response = self.client.post(
            reverse("contracts:api_request_restore", args=[request.pk]),
            {"restored_at": "2026-03-02T10:00"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("раньше регистрации", response.json()["error"])

    def test_closing_candidate_is_flagged_in_journal(self):
        candidate = self.make_request()
        incoming_message(candidate)
        self.make_request(description="Без писем")

        self.login(self.viewer)
        response = self.client.get(reverse("contracts:api_requests"), {"status": ""})

        flags = {item["number"]: item["closing_candidate"] for item in response.json()["requests"]}
        self.assertTrue(flags[candidate.number])
        self.assertEqual(sum(flags.values()), 1)

    def test_thread_marks_letters_with_act_attachment(self):
        request = self.make_request()
        incoming_message(request)

        self.login(self.viewer)
        response = self.client.get(reverse("contracts:api_request_messages", args=[request.pk]))

        message = response.json()["messages"][0]
        self.assertTrue(message["has_act_attachment"])

    def test_close_by_message_via_api(self):
        request = self.make_request()
        message = incoming_message(request)
        self.viewer.user_permissions.add(Permission.objects.get(codename="close_service_request"))
        self.login(self.viewer)

        response = self.client.post(reverse("contracts:api_request_close_by_message", args=[request.pk, message.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()["request"]
        self.assertEqual(payload["status"], ServiceRequest.CLOSED)
        self.assertFalse(payload["closing_candidate"])
        self.assertEqual(payload["closing_channel"], ServiceProvider.EMAIL)

    def test_close_by_message_requires_permission(self):
        request = self.make_request()
        message = incoming_message(request)
        self.login(self.viewer)

        response = self.client.post(reverse("contracts:api_request_close_by_message", args=[request.pk, message.pk]))

        self.assertEqual(response.status_code, 403)
        request.refresh_from_db()
        self.assertNotEqual(request.status, ServiceRequest.CLOSED)

    def test_act_scan_is_not_served_to_strangers(self):
        request = self.make_request(initiator=self.initiator)
        mark_restored(request, dt("2026-03-02", 16))
        close_by_act(request, act_file=act_file(), closed_at=dt("2026-03-03", 10))
        stranger = self.make_user("stranger")

        self.login(stranger)
        self.assertEqual(self.client.get(request.act_scan.url).status_code, 403)

        self.login(self.initiator)
        self.assertEqual(self.client.get(request.act_scan.url).status_code, 200)

        self.login(self.viewer)
        self.assertEqual(self.client.get(request.act_scan.url).status_code, 200)
