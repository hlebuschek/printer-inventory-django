"""Тесты приёмки устройств: initial_counter, право manage_device_acceptance, PDF-документы."""

import json
import shutil
import tempfile
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from contracts.models import AcceptanceDocument, City, ContractDevice, ContractStatus, DeviceModel, Manufacturer
from inventory.models import Organization

User = get_user_model()

PDF_BYTES = b"%PDF-1.4\n%fake pdf for tests\n%%EOF"

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="test_acceptance_media_")


def _perm(codename, model):
    ct = ContentType.objects.get(app_label="contracts", model=model)
    return Permission.objects.get(content_type=ct, codename=codename)


class AcceptanceTestBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="ООО Ромашка")
        self.city = City.objects.create(name="Иркутск")
        self.mfr = Manufacturer.objects.create(name="Kyocera")
        self.model = DeviceModel.objects.create(manufacturer=self.mfr, name="ECOSYS M2040")
        self.status = ContractStatus.objects.create(name="Активен")
        self.status2 = ContractStatus.objects.create(name="На складе")
        self.device = ContractDevice.objects.create(
            organization=self.org,
            city=self.city,
            address="ул. Ленина 1",
            model=self.model,
            status=self.status,
            serial_number="SN-ACC-1",
        )

        access = _perm("access_contracts_app", "contractsaccess")
        acceptance = _perm("manage_device_acceptance", "contractsaccess")
        view = _perm("view_contractdevice", "contractdevice")
        change = _perm("change_contractdevice", "contractdevice")

        # только просмотр
        self.viewer = User.objects.create_user(username="viewer", password="x")
        self.viewer.user_permissions.add(access, view)

        # только приёмка (счётчик, PDF, статус, месяц)
        self.acceptor = User.objects.create_user(username="acceptor", password="x")
        self.acceptor.user_permissions.add(access, view, acceptance)

        # полный редактор
        self.editor = User.objects.create_user(username="editor", password="x")
        self.editor.user_permissions.add(access, view, change)

    def _login(self, user):
        """force_login + свежий oidc_id_token_expiration, иначе SessionRefresh редиректит GET на Keycloak."""
        self.client.force_login(user)
        session = self.client.session
        session["oidc_id_token_expiration"] = time.time() + 3600
        session.save()

    def _update(self, payload):
        return self.client.post(
            f"/contracts/api/{self.device.id}/update/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _upload(self, *files):
        return self.client.post(f"/contracts/api/{self.device.id}/acceptance-docs/upload/", data={"files": files})


class UpdateApiPermissionTests(AcceptanceTestBase):
    def test_viewer_cannot_update(self):
        self._login(self.viewer)
        response = self._update({"initial_counter": 100})
        self.assertEqual(response.status_code, 403)

    def test_acceptor_updates_acceptance_fields(self):
        self._login(self.acceptor)
        response = self._update(
            {"initial_counter": 12345, "service_start_month": "2026-08", "status_id": self.status2.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.device.refresh_from_db()
        self.assertEqual(self.device.initial_counter, 12345)
        self.assertEqual(self.device.status_id, self.status2.id)
        self.assertEqual(self.device.service_start_month.strftime("%Y-%m"), "2026-08")

    def test_acceptor_cannot_touch_other_fields(self):
        self._login(self.acceptor)
        response = self._update({"address": "взломанный адрес", "serial_number": "HACKED", "initial_counter": 1})
        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.address, "ул. Ленина 1")
        self.assertEqual(self.device.serial_number, "SN-ACC-1")
        self.assertEqual(self.device.initial_counter, 1)

    def test_editor_updates_counter(self):
        self._login(self.editor)
        response = self._update({"initial_counter": 777})
        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertEqual(self.device.initial_counter, 777)

    def test_invalid_counter_rejected(self):
        self._login(self.acceptor)
        for bad in ("abc", -5):
            response = self._update({"initial_counter": bad})
            self.assertEqual(response.status_code, 400, f"counter={bad!r}")
        self.device.refresh_from_db()
        self.assertIsNone(self.device.initial_counter)

    def test_empty_counter_clears_value(self):
        self.device.initial_counter = 500
        self.device.save(update_fields=["initial_counter"])
        self._login(self.acceptor)
        response = self._update({"initial_counter": ""})
        self.assertEqual(response.status_code, 200)
        self.device.refresh_from_db()
        self.assertIsNone(self.device.initial_counter)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AcceptanceDocsApiTests(AcceptanceTestBase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def _pdf(self, name="акт.pdf", content=PDF_BYTES):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_upload_requires_acceptance_perm(self):
        self._login(self.viewer)
        response = self._upload(self._pdf())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AcceptanceDocument.objects.count(), 0)

    def test_upload_valid_pdfs(self):
        self._login(self.acceptor)
        response = self._upload(self._pdf("акт.pdf"), self._pdf("конфигурация.pdf"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["documents"]), 2)
        self.assertEqual(self.device.acceptance_documents.count(), 2)
        doc = self.device.acceptance_documents.first()
        self.assertEqual(doc.original_name, "акт.pdf")
        self.assertEqual(doc.uploaded_by, self.acceptor)
        with doc.file.open("rb") as fh:
            self.assertEqual(fh.read(), PDF_BYTES)

    def test_upload_rejects_wrong_extension(self):
        self._login(self.acceptor)
        response = self._upload(SimpleUploadedFile("акт.txt", PDF_BYTES))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AcceptanceDocument.objects.count(), 0)

    def test_upload_rejects_renamed_non_pdf(self):
        self._login(self.acceptor)
        response = self._upload(self._pdf(content=b"MZ not a pdf at all"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AcceptanceDocument.objects.count(), 0)

    def test_upload_rejects_batch_with_one_bad_file(self):
        self._login(self.acceptor)
        response = self._upload(self._pdf(), self._pdf(content=b"not a pdf"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AcceptanceDocument.objects.count(), 0)

    def test_upload_without_files(self):
        self._login(self.acceptor)
        response = self.client.post(f"/contracts/api/{self.device.id}/acceptance-docs/upload/")
        self.assertEqual(response.status_code, 400)

    def _create_doc(self):
        return AcceptanceDocument.objects.create(device=self.device, file=self._pdf(), uploaded_by=self.editor)

    def test_download_returns_pdf(self):
        doc = self._create_doc()
        self._login(self.viewer)
        response = self.client.get(f"/contracts/api/acceptance-docs/{doc.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)

    def test_download_requires_login(self):
        doc = self._create_doc()
        response = self.client.get(f"/contracts/api/acceptance-docs/{doc.id}/")
        self.assertEqual(response.status_code, 302)

    def test_download_missing_doc_404(self):
        self._login(self.viewer)
        response = self.client.get("/contracts/api/acceptance-docs/999999/")
        self.assertEqual(response.status_code, 404)

    def test_delete_requires_acceptance_perm(self):
        doc = self._create_doc()
        self._login(self.viewer)
        response = self.client.post(f"/contracts/api/acceptance-docs/{doc.id}/delete/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AcceptanceDocument.objects.filter(pk=doc.pk).exists())

    def test_delete_removes_doc_and_file(self):
        doc = self._create_doc()
        storage, path = doc.file.storage, doc.file.name
        self.assertTrue(storage.exists(path))
        self._login(self.acceptor)
        response = self.client.post(f"/contracts/api/acceptance-docs/{doc.id}/delete/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AcceptanceDocument.objects.filter(pk=doc.pk).exists())
        self.assertFalse(storage.exists(path))

    def test_docs_in_devices_api(self):
        self._create_doc()
        self._login(self.viewer)
        response = self.client.get("/contracts/api/devices/")
        self.assertEqual(response.status_code, 200)
        devices = response.json()["devices"]
        target = next(d for d in devices if d["id"] == self.device.id)
        self.assertEqual(target["initial_counter"], None)
        self.assertEqual(len(target["acceptance_docs"]), 1)
        self.assertEqual(target["acceptance_docs"][0]["name"], "акт.pdf")
