from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse

from contracts.models import ContractDevice, ServiceProvider, ServiceRequest
from contracts.services_request_analytics import build_analytics

from .test_service_requests import ServiceRequestBase, dt


class AnalyticsServiceTests(ServiceRequestBase):
    def test_summary_counts_active_and_overdue(self):
        self.make_request()
        self.make_request(restored_at=dt("2026-03-03", 11), closed_at=dt("2026-03-03", 12))
        self.make_request(registered_at=dt("2026-03-02", 14), status=ServiceRequest.REJECTED)

        summary = build_analytics(ServiceRequest.objects.all())["summary"]
        self.assertEqual(summary["total"], 3)
        # Отклонённая не активна и не просрочена, закрытая уложилась в норматив
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["overdue_share"], 33.3)

    def test_downtime_counted_in_working_hours(self):
        # Понедельник 14:00 → 16:00 при графике 8:00-17:00
        self.make_request(restored_at=dt("2026-03-02", 16), closed_at=dt("2026-03-02", 16))
        self.assertEqual(build_analytics(ServiceRequest.objects.all())["summary"]["downtime_hours"], 2.0)

    def test_request_without_printing_stop_adds_no_downtime(self):
        self.make_request(stops_printing=False, restored_at=dt("2026-03-04", 16))
        self.assertEqual(build_analytics(ServiceRequest.objects.all())["summary"]["downtime_hours"], 0.0)

    def test_provider_breakdown_compares_contractors(self):
        other_provider = ServiceProvider.objects.create(name="Второй", code="second")
        other_device = ContractDevice.objects.create(
            organization=self.device.organization,
            city=self.city,
            address="ул. Мира, 2",
            model=self.device.model,
            serial_number="SN002",
            status=self.device.status,
            service_provider=other_provider,
        )
        self.make_request(service_provider=self.provider)
        self.make_request(service_provider=self.provider)
        self.make_request(
            device=other_device,
            service_provider=other_provider,
            restored_at=dt("2026-03-02", 16),
            closed_at=dt("2026-03-02", 16),
        )

        rows = build_analytics(ServiceRequest.objects.all())["by_provider"]
        self.assertEqual([row["label"] for row in rows], ["Подрядчик", "Второй"])
        self.assertEqual(rows[0]["overdue"], 2)
        self.assertEqual(rows[0]["overdue_share"], 100.0)
        self.assertEqual(rows[1]["overdue"], 0)
        self.assertEqual(rows[1]["downtime_hours"], 2.0)

    def test_requests_without_provider_are_grouped_apart(self):
        self.make_request()
        self.assertEqual(build_analytics(ServiceRequest.objects.all())["by_provider"][0]["label"], "—")

    def test_daily_series_shows_created_and_restored(self):
        self.make_request(registered_at=dt("2026-03-02", 14), restored_at=dt("2026-03-03", 10))
        self.make_request(registered_at=dt("2026-03-03", 9))

        daily = build_analytics(ServiceRequest.objects.all())["daily"]
        self.assertEqual(
            daily,
            [
                {"date": "2026-03-02", "created": 1, "restored": 0},
                {"date": "2026-03-03", "created": 1, "restored": 1},
            ],
        )

    def test_empty_selection_gives_zeroes(self):
        analytics = build_analytics(ServiceRequest.objects.none())
        self.assertEqual(analytics["summary"]["total"], 0)
        self.assertEqual(analytics["summary"]["overdue_share"], 0.0)
        self.assertEqual(analytics["by_provider"], [])
        self.assertEqual(analytics["daily"], [])


class AnalyticsApiTests(ServiceRequestBase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass12345")
        for codename in ("access_contracts_app", "view_servicerequest"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def test_analytics_follows_journal_filters(self):
        self.make_request(description="Открытая")
        self.make_request(description="Закрытая", restored_at=dt("2026-03-03", 11), closed_at=dt("2026-03-03", 12))

        url = reverse("contracts:api_requests_analytics")
        self.assertEqual(self.client.get(url, {"status": ""}).json()["summary"]["total"], 2)
        self.assertEqual(self.client.get(url, {"status": "active"}).json()["summary"]["total"], 1)
        self.assertEqual(self.client.get(url, {"q": "Закрытая", "status": ""}).json()["summary"]["total"], 1)

    def test_user_without_view_all_sees_only_own_requests(self):
        restricted = get_user_model().objects.create_user(username="own", password="pass12345")
        for codename in ("access_contracts_app", "create_service_request"):
            restricted.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(restricted, backend="django.contrib.auth.backends.ModelBackend")

        self.make_request(initiator=restricted)
        self.make_request(initiator=self.user)

        response = self.client.get(reverse("contracts:api_requests_analytics"), {"status": ""})
        self.assertEqual(response.json()["summary"]["total"], 1)
