"""Тесты admin-action клонирования шаблонов веб-парсинга на другие модели."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from contracts.models import DeviceModel, Manufacturer
from inventory.models import WebParsingTemplate

User = get_user_model()


class CloneTemplateAdminActionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin", password="pass", email="a@a.ru")
        self.client.force_login(self.admin)

        manufacturer = Manufacturer.objects.create(name="Pantum")
        self.model_adw = DeviceModel.objects.create(manufacturer=manufacturer, name="BM5100ADW")
        self.model_fdw = DeviceModel.objects.create(manufacturer=manufacturer, name="BM5100FDW")
        self.model_fdn = DeviceModel.objects.create(manufacturer=manufacturer, name="BM5100FDN")

        self.template = WebParsingTemplate.objects.create(
            name="Pantum BM5100 стандарт",
            device_model=self.model_adw,
            description="Тестовый шаблон",
            rules_config=[{"protocol": "http", "url_path": "/status", "field_name": "bw_a4", "xpath": "//td"}],
            created_by=self.admin,
            is_public=True,
        )
        self.changelist_url = reverse("admin:inventory_webparsingtemplate_changelist")

    def test_action_shows_intermediate_form(self):
        response = self.client.post(
            self.changelist_url,
            data={"action": "clone_to_models", "_selected_action": [self.template.pk]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Клонирование шаблонов")
        self.assertContains(response, self.template.name)

    def test_clone_creates_copies_for_target_models(self):
        response = self.client.post(
            self.changelist_url,
            data={
                "action": "clone_to_models",
                "_selected_action": [self.template.pk],
                "target_models": [self.model_fdw.pk, self.model_fdn.pk],
                "apply": "1",
            },
        )
        self.assertEqual(response.status_code, 302)

        clones = WebParsingTemplate.objects.filter(name=self.template.name).exclude(pk=self.template.pk)
        self.assertEqual(clones.count(), 2)
        self.assertSetEqual(
            {c.device_model_id for c in clones}, {self.model_fdw.pk, self.model_fdn.pk}
        )
        for clone in clones:
            self.assertEqual(clone.rules_config, self.template.rules_config)
            self.assertEqual(clone.is_public, self.template.is_public)
            self.assertEqual(clone.created_by, self.admin)

    def test_clone_skips_same_model_and_duplicates(self):
        # Уже существующий клон на FDW
        WebParsingTemplate.objects.create(
            name=self.template.name,
            device_model=self.model_fdw,
            rules_config=self.template.rules_config,
        )

        self.client.post(
            self.changelist_url,
            data={
                "action": "clone_to_models",
                "_selected_action": [self.template.pk],
                "target_models": [self.model_adw.pk, self.model_fdw.pk],
                "apply": "1",
            },
        )

        # Ничего нового не создано: та же модель + дубликат имени
        self.assertEqual(WebParsingTemplate.objects.filter(name=self.template.name).count(), 2)
