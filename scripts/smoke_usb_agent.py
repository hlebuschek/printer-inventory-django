"""Smoke-тест USB-агента через Django test client (без runserver/Redis).

Проверяет:
  1. /api/v1/inventory/usb-agents/register/ — выдача токена
  2. /api/v1/inventory/usb-readings/ — auth + автосоздание Printer + сохранение reading'a
  3. дедупликацию (тот же reading повторно)
  4. отказ при отсутствии ContractDevice
"""

import json
import os
import sys
from datetime import datetime, timezone

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "printer_inventory.settings")
django.setup()

# Подменяем дедупликационный cache в services_usb на простой dict,
# чтобы тест не зависел от Redis.
import inventory.services_usb as _svc  # noqa: E402


class _DictCache:
    def __init__(self):
        self._d = {}

    def get(self, key):
        return self._d.get(key)

    def set(self, key, value, timeout=None):
        self._d[key] = value


_svc.cache = _DictCache()

from django.test import RequestFactory  # noqa: E402

from inventory.views_usb import register_agent, submit_readings  # noqa: E402

from contracts.models import (  # noqa: E402
    City,
    ContractDevice,
    ContractStatus,
    DeviceModel,
    Manufacturer,
)
from inventory.models import (  # noqa: E402
    InventoryTask,
    Organization,
    PageCounter,
    Printer,
    USBAgent,
)

SERIAL = "USB-SMOKE-12345"
AGENT_ID = "smoke-agent-001"
MASTER_KEY = "test-key"


def step(title):
    print(f"\n=== {title} ===")


def seed():
    step("seed: Organization + ContractDevice")
    org, _ = Organization.objects.get_or_create(name="USB Smoke Org")
    mfr, _ = Manufacturer.objects.get_or_create(name="Smoke Mfr")
    city, _ = City.objects.get_or_create(name="Smoke City")
    status, _ = ContractStatus.objects.get_or_create(name="Активен")
    model, _ = DeviceModel.objects.get_or_create(
        manufacturer=mfr,
        name="HP LaserJet USB-Smoke",
    )
    cd, created = ContractDevice.objects.get_or_create(
        organization=org,
        serial_number=SERIAL,
        defaults={"city": city, "address": "Smoke Address", "model": model, "status": status},
    )
    print(f"  ContractDevice id={cd.id} (new={created}) org={org.name}")
    return cd


def cleanup():
    step("cleanup: prev test data")
    Printer.objects.filter(serial_number=SERIAL).delete()
    USBAgent.objects.filter(agent_id=AGENT_ID).delete()
    print("  cleared")


RF = RequestFactory()


def _post(view, path, body, token=None):
    """Вызывает view напрямую через RequestFactory, минуя session middleware."""
    headers = {}
    if token:
        headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    request = RF.post(path, data=json.dumps(body), content_type="application/json", **headers)
    resp = view(request)
    try:
        resp_json = json.loads(resp.content.decode("utf-8"))
    except Exception:
        resp_json = None
    return resp.status_code, resp_json


def register():
    step("register agent")
    status, body = _post(
        register_agent,
        "/api/v1/inventory/usb-agents/register/",
        {
            "registration_key": MASTER_KEY,
            "agent_id": AGENT_ID,
            "hostname": "SMOKE-PC",
            "agent_version": "0.1.0-smoke",
        },
    )
    print(f"  HTTP {status} → {body}")
    assert status == 201, body
    return body["token"]


def reading_payload(timestamp_iso, total=12345):
    return {
        "agent_id": AGENT_ID,
        "agent_version": "0.1.0-smoke",
        "readings": [
            {
                "timestamp": timestamp_iso,
                "printer_name": "HP LaserJet 1020 USB",
                "model": "HP LaserJet 1020",
                "serial_number": {"source": "registry", "value": SERIAL},
                "counters": {"total_pages": total, "bw_a4": total},
                "connection_verified": True,
                "device_instance_id": "USB\\VID_03F0&PID_2B17\\SMOKE",
            }
        ],
    }


def submit(token, payload):
    return _post(submit_readings, "/api/v1/inventory/usb-readings/", payload, token=token)


def test_no_contract_device(token):
    step("submit reading WITHOUT ContractDevice → expect error")
    payload = reading_payload(datetime.now(timezone.utc).isoformat())
    payload["readings"][0]["serial_number"]["value"] = "NO-SUCH-SERIAL-XYZ"
    status, body = submit(token, payload)
    print(f"  HTTP {status} → {body}")
    assert status == 200
    assert body["results"][0]["status"] == "error"


def test_happy_path(token):
    step("submit reading WITH ContractDevice → expect success + Printer auto-create")
    ts = datetime.now(timezone.utc).isoformat()
    status, body = submit(token, reading_payload(ts))
    print(f"  HTTP {status} → {body}")
    assert status == 200
    result = body["results"][0]
    assert result["status"] == "success", result
    task_id = result["task_id"]

    p = Printer.objects.get(serial_number=SERIAL)
    print(
        f"  Printer auto-created: id={p.id} polling={p.polling_method} "
        f"connection={p.connection_type} usb_id={p.usb_identifier!r}"
    )
    assert p.polling_method == "USB_API"
    assert p.connection_type == "USB"

    task = InventoryTask.objects.get(id=task_id)
    pc = PageCounter.objects.get(task=task)
    print(
        f"  InventoryTask status={task.status} data_source={task.data_source} "
        f"agent_id={task.agent_id}; counter total={pc.total_pages}"
    )
    assert task.data_source == "USB_AGENT"
    assert pc.total_pages == 12345
    return ts


def test_dedup(token, ts):
    step("submit SAME reading again → expect duplicate")
    status, body = submit(token, reading_payload(ts))
    print(f"  HTTP {status} → {body}")
    assert status == 200
    assert body["results"][0]["status"] == "duplicate", body


def test_bad_token():
    step("submit with bad token → expect 401")
    payload = reading_payload(datetime.now(timezone.utc).isoformat())
    status, body = submit("BOGUS-TOKEN", payload)
    print(f"  HTTP {status} → {body}")
    assert status == 401


def main():
    cleanup()
    seed()
    token = register()
    test_bad_token()
    test_no_contract_device(token)
    ts = test_happy_path(token)
    test_dedup(token, ts)
    print("\n*** ALL SMOKE TESTS PASSED ***")


if __name__ == "__main__":
    main()
