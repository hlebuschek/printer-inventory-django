"""Тесты логирования изменений правил веб-парсинга в историю принтера (EntityChangeLog)."""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from access.models import EntityChangeLog
from contracts.models import DeviceModel, Manufacturer
from inventory.models import Organization, Printer, WebParsingRule, WebParsingTemplate

User = get_user_model()


class WebParsingRuleLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="parseruser", password="pass")
        ct = ContentType.objects.get(app_label="inventory", model="inventoryaccess")
        for codename in ("access_inventory_app", "manage_web_parsing"):
            self.user.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
        self.client.force_login(self.user)

        org = Organization.objects.create(name="Org")
        manufacturer = Manufacturer.objects.create(name="Pantum")
        self.device_model = DeviceModel.objects.create(manufacturer=manufacturer, name="BM5100ADW")
        self.printer = Printer.objects.create(
            ip_address="10.1.1.1",
            serial_number="SN1",
            organization=org,
            snmp_community="public",
            device_model=self.device_model,
        )
        self.printer_ct = ContentType.objects.get_for_model(Printer)

    def _printer_logs(self):
        return EntityChangeLog.objects.filter(content_type=self.printer_ct, object_id=self.printer.id)

    def _post_rule(self, payload):
        return self.client.post(
            "/inventory/api/web-parser/save-rule/", data=json.dumps(payload), content_type="application/json"
        )

    def test_create_rule_logged(self):
        response = self._post_rule(
            {"printer_id": self.printer.id, "field_name": "counter", "url_path": "/status", "xpath": "//td"}
        )
        self.assertEqual(response.status_code, 200)

        log = self._printer_logs().first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)
        self.assertIn("web_parsing_rule", log.changes)
        self.assertIsNone(log.changes["web_parsing_rule"]["old"])
        self.assertEqual(log.changes["web_parsing_rule"]["new"], "Общий счетчик")

    def test_update_rule_logged_with_diff(self):
        rule = WebParsingRule.objects.create(
            printer=self.printer, field_name="counter", url_path="/status", xpath="//td"
        )
        response = self._post_rule(
            {
                "edit_id": rule.id,
                "printer_id": self.printer.id,
                "field_name": "counter",
                "url_path": "/status",
                "xpath": "//td[2]",
            }
        )
        self.assertEqual(response.status_code, 200)

        log = self._printer_logs().first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)
        self.assertIn("xpath", log.changes)
        self.assertEqual(log.changes["xpath"]["old"], "//td")
        self.assertEqual(log.changes["xpath"]["new"], "//td[2]")
        self.assertIn("Правило «Общий счетчик»", log.changes["xpath"]["label"])

    def test_update_without_changes_not_logged(self):
        rule = WebParsingRule.objects.create(
            printer=self.printer, field_name="counter", url_path="/status", xpath="//td"
        )
        self._post_rule(
            {
                "edit_id": rule.id,
                "printer_id": self.printer.id,
                "field_name": "counter",
                "url_path": "/status",
                "xpath": "//td",
            }
        )
        self.assertFalse(self._printer_logs().exists())

    def test_delete_rule_logged(self):
        rule = WebParsingRule.objects.create(
            printer=self.printer, field_name="counter", url_path="/status", xpath="//td"
        )
        response = self._post_rule({"delete": True, "edit_id": rule.id})
        self.assertEqual(response.status_code, 200)

        log = self._printer_logs().first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changes["web_parsing_rule"]["old"], "Общий счетчик")
        self.assertIsNone(log.changes["web_parsing_rule"]["new"])

    def test_apply_template_logged(self):
        template = WebParsingTemplate.objects.create(
            name="BM5100 стандарт",
            device_model=self.device_model,
            rules_config=[
                {"protocol": "http", "url_path": "/status", "field_name": "counter", "xpath": "//td"},
            ],
            created_by=self.user,
        )
        WebParsingRule.objects.create(printer=self.printer, field_name="counter", url_path="/old", xpath="//old")

        response = self.client.post(
            "/inventory/api/web-parser/apply-template/",
            data=json.dumps({"printer_id": self.printer.id, "template_id": template.id, "overwrite": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        log = self._printer_logs().first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.user)
        change = log.changes["web_parsing_template"]
        self.assertIn("BM5100 стандарт", change["new"])
        self.assertIn("удалено прежних правил: 1", change["old"])
