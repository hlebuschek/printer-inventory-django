"""
Постановка на опрос в GLPI — интеграционные тесты на настоящем GLPI 10 + glpiinventory.

Проверено на GLPI 10.0.20 + glpiinventory 1.3.4 и GLPI 12.0.1 + glpiinventory 1.7.0.
Запуск со стендом (~/PycharmProjects/glpi-test/glpi10 — порт 8082, glpi12 — 8085; docker compose up -d):
    GLPI_TEST_URL=http://127.0.0.1:8082/apirest.php GLPI_TEST_TOKEN=<user_token> \
        .venv/bin/python manage.py test inventory.tests.test_netscan_glpi_push
Без GLPI_TEST_URL интеграционные тесты пропускаются (в CI GLPI нет).
Каждый прогон заводит свои организации/задачи/карточки с уникальным суффиксом.
"""

import json
import os
import random
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase, modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone

from integrations.glpi.client import GLPIAPIError, GLPIClient
from inventory.models import DiscoveredDevice, ScanNetwork
from inventory.services_netscan_glpi_push import build_plan, execute

GLPI_URL = os.getenv("GLPI_TEST_URL", "")
GLPI_TOKEN = os.getenv("GLPI_TEST_TOKEN", "testtoken1234567890testtoken1234567890ab")

NO_OIDC = modify_settings(
    MIDDLEWARE={
        "remove": [
            "mozilla_django_oidc.middleware.SessionRefresh",
            "printer_inventory.middleware.AjaxSessionRefreshMiddleware",
        ]
    }
)
GLPI_SETTINGS = override_settings(
    GLPI_API_URL=GLPI_URL or "http://glpi.invalid/apirest.php",
    GLPI_USER_TOKEN=GLPI_TOKEN,
    GLPI_APP_TOKEN="",
    GLPI_USERNAME="",
    GLPI_PASSWORD="",
    GLPI_ENTITIES_ID="0",
    GLPI_RECURSIVE=True,
    GLPI_VERIFY_SSL=False,
    GLPI_NETSCAN_SNMP_CREDENTIALS="1,2",
)


@skipUnless(GLPI_URL, "нужен тестовый GLPI: GLPI_TEST_URL")
@GLPI_SETTINGS
class PushOnRealGLPITests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.suffix = f"{random.randint(0, 0xFFFFFF):06x}"
        cls.net = f"10.{random.randint(100, 250)}.{random.randint(0, 250)}"
        with GLPI_SETTINGS:
            cls.glpi = GLPIClient()
            cls.glpi.init_session()
            g = cls.glpi
            cls.entity = g.add_item("Entity", {"name": f"IT Больница {cls.suffix}", "entities_id": 0})
            g.change_active_entities()  # GLPI 11+: новая организация видна сессии только после обновления
            cls.child = g.add_item("Entity", {"name": f"Филиал {cls.suffix}", "entities_id": cls.entity})
            g.change_active_entities()
            cls.jobs = {}
            for method, title in (("networkdiscovery", "Discovery"), ("networkinventory", "Inventory")):
                task = g.add_item(
                    "PluginGlpiinventoryTask",
                    {"name": f"{title} {cls.suffix}", "entities_id": cls.entity, "is_active": 1},
                )
                cls.jobs[method] = g.add_item(
                    "PluginGlpiinventoryTaskjob",
                    {
                        "name": f"{title} {cls.suffix}",
                        "plugin_glpiinventory_tasks_id": task,
                        "entities_id": cls.entity,
                        "method": method,
                        "targets": "[]",
                        "actors": json.dumps([{"Agent": "1"}]),
                    },
                )

    @classmethod
    def tearDownClass(cls):
        cls.glpi.kill_session()
        super().tearDownClass()

    def card(self, ip, mac, credential=2, entity=None):
        g = self.glpi
        serial = f"IT{self.suffix}{random.randint(0, 99999):05d}"
        entity = entity or self.entity
        pid = g.add_item(
            "Printer",
            {"name": f"PRN {serial}", "serial": serial, "entities_id": entity, "snmpcredentials_id": credential},
        )
        port = g.add_item(
            "NetworkPort",
            {
                "itemtype": "Printer",
                "items_id": pid,
                "instantiation_type": "NetworkPortEthernet",
                "mac": mac,
                "name": "eth0",
                "entities_id": entity,
            },
        )
        name = g.add_item("NetworkName", {"itemtype": "NetworkPort", "items_id": port, "name": serial.lower()})
        if ip:
            g.add_item("IPAddress", {"itemtype": "NetworkName", "items_id": name, "name": ip, "entities_id": entity})
        return pid, serial, name

    def device(self, ip, serial="", mac="", card=None, glpi_status=DiscoveredDevice.GLPI_STALE, entity=None):
        network, _ = ScanNetwork.objects.get_or_create(cidr=f"{self.net}.0/24", defaults={"name": "IT"})
        return DiscoveredDevice.objects.create(
            network=network,
            identity=f"sn:{serial or ip}",
            ip_address=ip,
            serial_number=serial,
            mac_address=mac,
            status=DiscoveredDevice.NOT_IN_CONTRACT,
            last_seen=timezone.now(),
            glpi_status=glpi_status,
            glpi_printer_id=card,
            glpi_entity_id=entity,
        )

    def job_targets(self, method):
        return json.loads(self.glpi.get_item("PluginGlpiinventoryTaskjob", self.jobs[method])["targets"] or "[]")

    def ranges_for(self, ip):
        return [r for r in self.glpi.list_items("PluginGlpiinventoryIPRange") if r["ip_start"] == ip]

    def test_known_card_ip_fixed_and_range_added_to_both_tasks(self):
        pid, serial, name = self.card(f"{self.net}.10", "aa:bb:cc:dd:00:10")
        ip = f"{self.net}.20"
        dev = self.device(ip, serial, "AA:BB:CC:DD:00:10", card=pid)

        plan = build_plan(self.glpi, dev)
        self.assertEqual(plan.problems, [])
        texts = [s.text for s in plan.steps if s.action]
        self.assertEqual(len(texts), 5, texts)  # IP, диапазон, учётки, поиск, опрос
        self.assertTrue(texts[0].startswith("Исправить IP"))
        execute(plan)

        ips = [a["name"] for a in self.glpi.get_sub_items("NetworkName", name, "IPAddress")]
        self.assertEqual(ips, [ip])
        rng = self.ranges_for(ip)
        self.assertEqual(len(rng), 1)
        for method in ("networkdiscovery", "networkinventory"):
            targets = self.job_targets(method)
            self.assertIn({"PluginGlpiinventoryIPRange": str(rng[0]["id"])}, targets)
            self.assertNotIn({"Printer": str(pid)}, targets)  # саму карточку в задачи не кладём
        dev.refresh_from_db()
        self.assertIn("Исправить IP", dev.glpi_push_message)

        again = build_plan(self.glpi, dev)  # повторно — делать нечего
        self.assertFalse([s for s in again.steps if s.action])
        self.assertFalse(again.can_run)

    def test_not_in_glpi_single_ip_range_with_credentials_in_both_tasks(self):
        ip = f"{self.net}.30"
        dev = self.device(ip, glpi_status=DiscoveredDevice.GLPI_NOT_FOUND)
        self.assertIn("Выберите организацию GLPI", build_plan(self.glpi, dev).problems)

        plan = build_plan(self.glpi, dev, entity_id=self.entity)
        self.assertEqual(plan.problems, [])
        execute(plan)

        rng = [r for r in self.glpi.list_items("PluginGlpiinventoryIPRange") if r["ip_start"] == ip]
        self.assertEqual(len(rng), 1)
        self.assertEqual((rng[0]["ip_end"], int(rng[0]["entities_id"])), (ip, self.entity))
        links = sorted(
            (int(x["rank"]), int(x["snmpcredentials_id"]))
            for x in self.glpi.list_items("PluginGlpiinventoryIPRange_SNMPCredential")
            if int(x["plugin_glpiinventory_ipranges_id"]) == int(rng[0]["id"])
        )
        self.assertEqual(links, [(1, 1), (2, 2)])
        for method in ("networkdiscovery", "networkinventory"):
            self.assertIn({"PluginGlpiinventoryIPRange": str(rng[0]["id"])}, self.job_targets(method))
        raw = self.glpi.get_item("PluginGlpiinventoryTaskjob", self.jobs["networkdiscovery"])["targets"]
        self.assertIn(f'{{"PluginGlpiinventoryIPRange":"{rng[0]["id"]}"}}', raw)  # формат как у плагина

        self.assertFalse(build_plan(self.glpi, dev, entity_id=self.entity).can_run)  # идемпотентно

    def test_card_without_credential_goes_to_discovery_and_child_entity_uses_parent_tasks(self):
        pid, serial, _ = self.card(f"{self.net}.40", "aa:bb:cc:dd:00:40", credential=0, entity=self.child)
        dev = self.device(f"{self.net}.41", serial, card=pid)
        plan = build_plan(self.glpi, dev, entity_id=self.entity)  # выбор игнорируется: берётся из карточки
        self.assertEqual((plan.entity_id, plan.problems), (self.child, []))
        self.assertIn(f"Discovery {self.suffix}", plan.jobs["networkdiscovery"][0]["task_name"])
        self.assertFalse(any(s.text.startswith("Исправить IP") for s in plan.steps))
        self.assertTrue(any("нет SNMP-учётки" in n for n in plan.notes))

    def test_several_tasks_of_one_method_all_get_the_range(self):
        g = self.glpi
        other = g.add_item("Entity", {"name": f"Две задачи {self.suffix}", "entities_id": 0})
        g.change_active_entities()
        jobs = []
        for method, count in (("networkdiscovery", 2), ("networkinventory", 3)):
            for i in range(count):
                task = g.add_item(
                    "PluginGlpiinventoryTask", {"name": f"{method} {i} {self.suffix}", "entities_id": other}
                )
                jobs.append(
                    g.add_item(
                        "PluginGlpiinventoryTaskjob",
                        {
                            "name": f"{method} {i}",
                            "plugin_glpiinventory_tasks_id": task,
                            "entities_id": other,
                            "method": method,
                            "targets": "[]",
                        },
                    )
                )
        ip = f"{self.net}.60"
        plan = build_plan(g, self.device(ip, glpi_status=DiscoveredDevice.GLPI_NOT_FOUND), entity_id=other)
        self.assertEqual(plan.problems, [])
        self.assertEqual({m: len(j) for m, j in plan.jobs.items()}, {"networkdiscovery": 2, "networkinventory": 3})
        execute(plan)
        rng = self.ranges_for(ip)
        self.assertEqual(len(rng), 1)
        for job in jobs:
            targets = json.loads(g.get_item("PluginGlpiinventoryTaskjob", job)["targets"] or "[]")
            self.assertEqual(targets, [{"PluginGlpiinventoryIPRange": str(rng[0]["id"])}])

    @NO_OIDC
    def test_page_plan_and_confirm(self):
        user = User.objects.create_user("pusher")
        for code in ("access_inventory_app", "manage_network_scan", "push_netscan_to_glpi"):
            user.user_permissions.add(Permission.objects.get(codename=code))
        self.client.force_login(user)
        pid, serial, name = self.card(f"{self.net}.70", "aa:bb:cc:dd:00:70")
        dev = self.device(f"{self.net}.71", serial, card=pid)
        url = reverse("inventory:netscan_device_glpi_push", args=[dev.pk])

        page = self.client.get(url)
        self.assertContains(page, f"Исправить IP карточки {pid}: {self.net}.70 → {self.net}.71")
        self.assertContains(page, "Добавить диапазон в задачу опроса")
        self.client.post(url, {"confirm": "1"})
        self.assertEqual(
            [a["name"] for a in self.glpi.get_sub_items("NetworkName", name, "IPAddress")], [f"{self.net}.71"]
        )
        dev.refresh_from_db()
        self.assertEqual(dev.glpi_push_by, user)


@NO_OIDC
@GLPI_SETTINGS
class PushPermissionTests(TestCase):
    def setUp(self):
        self.network = ScanNetwork.objects.create(name="N", cidr="10.7.7.0/24")
        self.device = DiscoveredDevice.objects.create(
            network=self.network,
            identity="sn:x",
            ip_address="10.7.7.5",
            serial_number="X",
            status=DiscoveredDevice.NOT_IN_CONTRACT,
            last_seen=timezone.now(),
            glpi_status=DiscoveredDevice.GLPI_STALE,
        )
        self.user = User.objects.create_user("u")
        for code in ("access_inventory_app", "manage_network_scan"):
            self.user.user_permissions.add(Permission.objects.get(codename=code))
        self.client.force_login(self.user)

    def test_without_push_permission_no_button_and_403(self):
        page = self.client.get(reverse("inventory:netscan_detail", args=[self.network.pk]) + "?tab=all")
        self.assertNotContains(page, "Поставить на опрос в GLPI")
        url = reverse("inventory:netscan_device_glpi_push", args=[self.device.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch("integrations.glpi.client.GLPIClient.init_session", side_effect=GLPIAPIError("нет связи"))
    def test_with_permission_button_shown_and_glpi_down_handled(self, _init):
        self.user.user_permissions.add(Permission.objects.get(codename="push_netscan_to_glpi"))
        page = self.client.get(reverse("inventory:netscan_detail", args=[self.network.pk]) + "?tab=all")
        self.assertContains(page, "Поставить на опрос в GLPI")
        resp = self.client.get(reverse("inventory:netscan_device_glpi_push", args=[self.device.pk]), follow=True)
        self.assertContains(resp, "GLPI недоступен")

    def test_group_from_migration(self):
        from django.contrib.auth.models import Group

        codes = set(
            Group.objects.get(name="Сканирование сетей — постановка в GLPI").permissions.values_list(
                "codename", flat=True
            )
        )
        self.assertTrue({"push_netscan_to_glpi", "manage_network_scan", "access_inventory_app"} <= codes)
