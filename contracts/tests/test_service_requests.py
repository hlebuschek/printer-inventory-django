from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
from inventory.models import Organization

IRKUTSK = ZoneInfo("Asia/Irkutsk")


def dt(day, hour, minute=0):
    return datetime.fromisoformat(f"{day} {hour:02d}:{minute:02d}").replace(tzinfo=IRKUTSK)


class ServiceRequestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schedule = WorkSchedule.objects.create(
            name="Тестовый 5/2", work_start=time(8, 0), work_end=time(17, 0), weekdays="12345", is_default=True
        )
        cls.city = City.objects.create(name="Иркутск", timezone="Asia/Irkutsk", sla_standard_hours=8)
        cls.provider = ServiceProvider.objects.create(name="Подрядчик", code="test")
        org = Organization.objects.create(name="Тест")
        manufacturer = Manufacturer.objects.create(name="HP")
        model = DeviceModel.objects.create(manufacturer=manufacturer, name="M404")
        status = ContractStatus.objects.create(name="В работе")
        cls.device = ContractDevice.objects.create(
            organization=org,
            city=cls.city,
            address="ул. Ленина, 1",
            model=model,
            serial_number="SN001",
            status=status,
            service_provider=cls.provider,
        )

    def make_request(self, **kwargs):
        kwargs.setdefault("device", self.device)
        kwargs.setdefault("description", "Не печатает")
        kwargs.setdefault("registered_at", dt("2026-03-02", 14))
        return ServiceRequest.objects.create(**kwargs)


class DeadlineTests(ServiceRequestBase):
    def test_deadline_uses_city_norm_and_working_hours(self):
        # 8 рабочих часов от понедельника 14:00: 3 часа до закрытия и 5 часов во вторник
        request = self.make_request()
        self.assertEqual(request.sla_hours, 8)
        self.assertEqual(request.deadline_at, dt("2026-03-03", 13))

    def test_critical_incident_gets_four_hours(self):
        request = self.make_request(is_critical=True)
        self.assertEqual(request.sla_hours, 4)
        self.assertEqual(request.deadline_at, dt("2026-03-03", 9))

    def test_schedule_is_snapshotted(self):
        request = self.make_request()
        self.assertEqual(request.schedule_snapshot, self.schedule)

    def test_deadline_is_not_recalculated_after_norm_changes(self):
        # Норматив города меняется, но по уже поданной заявке срок пересчитывать нельзя
        request = self.make_request()
        original = request.deadline_at

        self.city.sla_standard_hours = 16
        self.city.save(update_fields=["sla_standard_hours"])
        request.description = "Уточнение"
        request.save()

        request.refresh_from_db()
        self.assertEqual(request.deadline_at, original)
        self.assertEqual(request.sla_hours, 8)

    def test_reopen_inherits_deadline_of_first_request(self):
        # По п.6.6.1 ТЗ повторное обращение по тем же основаниям не даёт нового срока
        origin = self.make_request()
        reopen = self.make_request(registered_at=dt("2026-03-05", 10), reopened_from=origin)

        self.assertEqual(reopen.deadline_at, origin.deadline_at)
        self.assertEqual(reopen.sla_hours, origin.sla_hours)


class StatusTests(ServiceRequestBase):
    def test_new_request_is_open(self):
        self.assertEqual(self.make_request().status, ServiceRequest.OPEN)

    def test_restored_at_moves_to_restored(self):
        request = self.make_request(restored_at=dt("2026-03-03", 10))
        self.assertEqual(request.status, ServiceRequest.RESTORED)

    def test_closed_at_moves_to_closed(self):
        request = self.make_request(restored_at=dt("2026-03-03", 10), closed_at=dt("2026-03-04", 10))
        self.assertEqual(request.status, ServiceRequest.CLOSED)

    def test_rejected_status_is_kept(self):
        request = self.make_request(status=ServiceRequest.REJECTED)
        self.assertEqual(request.status, ServiceRequest.REJECTED)

    def test_number_is_built_from_year_and_id(self):
        request = self.make_request()
        self.assertEqual(request.number, f"2026-{request.pk:05d}")


class OverdueTests(ServiceRequestBase):
    def test_closed_before_deadline_is_not_overdue(self):
        request = self.make_request(restored_at=dt("2026-03-03", 11), closed_at=dt("2026-03-03", 12))
        self.assertFalse(request.is_overdue)

    def test_closed_after_deadline_is_overdue(self):
        request = self.make_request(restored_at=dt("2026-03-03", 14), closed_at=dt("2026-03-03", 14))
        self.assertTrue(request.is_overdue)

    def test_restored_in_time_but_act_late_is_overdue(self):
        # По ТЗ заявка не выполнена, пока не прислан скан технического акта
        request = self.make_request(restored_at=dt("2026-03-03", 11), closed_at=dt("2026-03-06", 12))
        self.assertTrue(request.is_overdue)

    def test_rejected_request_is_never_overdue(self):
        request = self.make_request(status=ServiceRequest.REJECTED)
        self.assertFalse(request.is_overdue)


class DowntimeTests(ServiceRequestBase):
    def test_downtime_counted_in_working_hours(self):
        # Пн 14:00 → Вт 10:00: 3 часа понедельника и 2 часа вторника
        request = self.make_request(restored_at=dt("2026-03-03", 10))
        self.assertEqual(request.downtime_hours(), 5.0)

    def test_request_without_print_stop_gives_no_downtime(self):
        request = self.make_request(stops_printing=False, restored_at=dt("2026-03-03", 10))
        self.assertEqual(request.downtime_hours(), 0.0)

    def test_open_request_counted_until_given_moment(self):
        request = self.make_request()
        self.assertEqual(request.downtime_hours(until=dt("2026-03-02", 16)), 2.0)


class DeviceTableColumnsTests(ServiceRequestBase):
    """Колонки заявок в таблице договоров питаются и журналом, а не только зеркалом Okdesk:
    заявки почтовому подрядчику в Okdesk не попадают вовсе."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester", password="pass12345", first_name="Иван", last_name="Петров"
        )
        for codename in ("access_contracts_app", "view_contractdevice"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def _row(self):
        response = self.client.get(reverse("contracts:api_devices"))
        self.assertEqual(response.status_code, 200)
        return response.json()["devices"][0]

    def test_device_without_requests_has_empty_columns(self):
        row = self._row()
        self.assertFalse(row["has_active_issues"])
        self.assertFalse(row["has_overdue_issues"])
        self.assertEqual(row["okdesk_author_name"], "")

    def test_active_request_fills_author_and_active_flag(self):
        self.make_request(initiator=self.user, registered_at=timezone.now())
        row = self._row()
        self.assertTrue(row["has_active_issues"])
        self.assertFalse(row["has_overdue_issues"])
        self.assertEqual(row["okdesk_author_name"], "Иван Петров")

    def test_expired_deadline_marks_row_overdue(self):
        self.make_request(initiator=self.user, registered_at=dt("2026-03-02", 14))
        self.assertTrue(self._row()["has_overdue_issues"])

    def test_closed_request_leaves_columns_empty(self):
        self.make_request(initiator=self.user, restored_at=dt("2026-03-03", 11), closed_at=dt("2026-03-03", 12))
        row = self._row()
        self.assertFalse(row["has_active_issues"])
        self.assertEqual(row["okdesk_author_name"], "")
