import io
from datetime import date, timedelta

from openpyxl import Workbook

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from inventory.models import Organization

from .models import MonthControl, MonthlyReport

MONTH = date(2026, 3, 1)


def excel_file(serial="SN-1", org="Орг"):
    wb = Workbook()
    ws = wb.active
    ws.append(["Организация", "Модель", "Серийный номер", "A4 ч/б начало", "A4 ч/б конец"])
    ws.append([org, "HP M404", serial, 100, 200])
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        "report.xlsx",
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class UploadAccessBase(TestCase):
    extra_perms: list[str] = []

    def setUp(self):
        Organization.objects.create(name="Орг")
        user = get_user_model().objects.create_user(username="uploader", password="p")
        for codename in ["upload_monthly_report", *self.extra_perms]:
            user.user_permissions.add(Permission.objects.get(codename=codename))

        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(user)
        session = self.client.session
        session["oidc_id_token_expiration"] = 9999999999
        session.save()

    def upload(self, **extra):
        return self.client.post(
            "/monthly-report/upload/",
            data={"excel_file": excel_file(), "month": MONTH.isoformat(), **extra},
        )

    def existing_month(self, *, editable: bool):
        MonthlyReport.objects.create(month=MONTH, serial_number="SN-1", organization="Орг", equipment_model="HP M404")
        return MonthControl.objects.create(
            month=MONTH,
            edit_until=timezone.now() + timedelta(days=1) if editable else None,
            is_published=True,
        )


class PublicationTests(UploadAccessBase):
    def test_upload_without_visibility_permission_keeps_publication(self):
        # Поля is_published в форме нет, и обычная загрузка не снимает месяц с публикации
        control = self.existing_month(editable=True)

        self.assertEqual(self.upload().status_code, 200)
        control.refresh_from_db()
        self.assertTrue(control.is_published)

    def test_is_published_from_handcrafted_post_is_ignored(self):
        control = self.existing_month(editable=True)

        self.assertEqual(self.upload(is_published="").status_code, 200)
        control.refresh_from_db()
        self.assertTrue(control.is_published)


class PublicationWithPermissionTests(UploadAccessBase):
    extra_perms = ["can_manage_month_visibility"]

    def test_permission_holder_still_controls_publication(self):
        control = self.existing_month(editable=True)

        self.assertEqual(self.upload().status_code, 200)
        control.refresh_from_db()
        self.assertFalse(control.is_published)


class MonthLockTests(UploadAccessBase):
    def test_first_upload_of_a_month_is_allowed(self):
        # Месяца ещё нет — заводить новый отчёт можно без права обхода блокировки
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(MonthlyReport.objects.filter(month=MONTH).count(), 1)

    def test_reupload_into_closed_month_is_forbidden(self):
        self.existing_month(editable=False)

        response = self.upload(replace_month="on")

        self.assertEqual(response.status_code, 403)
        # Данные закрытого месяца остались на месте
        self.assertEqual(MonthlyReport.objects.filter(month=MONTH).count(), 1)

    def test_reupload_into_open_month_is_allowed(self):
        self.existing_month(editable=True)

        self.assertEqual(self.upload(replace_month="on").status_code, 200)


class MonthLockOverrideTests(UploadAccessBase):
    extra_perms = ["override_auto_lock"]

    def test_override_permission_reopens_closed_month_for_upload(self):
        self.existing_month(editable=False)

        self.assertEqual(self.upload().status_code, 200)


class ReplaceMonthAtomicityTests(UploadAccessBase):
    def test_broken_file_does_not_wipe_the_month(self):
        # Очистка месяца идёт после разбора файла, иначе битая выгрузка стирает данные
        self.existing_month(editable=True)

        response = self.client.post(
            "/monthly-report/upload/",
            data={
                "excel_file": SimpleUploadedFile("report.xlsx", b"not an excel file at all"),
                "month": MONTH.isoformat(),
                "replace_month": "on",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(MonthlyReport.objects.filter(month=MONTH).count(), 1)

    def test_unknown_organization_does_not_wipe_the_month(self):
        self.existing_month(editable=True)

        response = self.client.post(
            "/monthly-report/upload/",
            data={
                "excel_file": excel_file(org="Неизвестная контора"),
                "month": MONTH.isoformat(),
                "replace_month": "on",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(MonthlyReport.objects.filter(month=MONTH).count(), 1)
