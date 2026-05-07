"""HTTP endpoints для USB-агентов: регистрация и приём readings."""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .authentication import usb_agent_required
from .services_usb import (
    USBReadingError,
    process_usb_reading,
    register_or_get_agent,
)

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 МБ — кап на flush большой очереди
MAX_READINGS_PER_BATCH = 500


@csrf_exempt
@require_GET
def health(request):
    """Лёгкий health-check для USB-агентов.

    Возвращает 200 без аутентификации. Агент дёргает это при «Тест соединения»
    чтобы убедиться что сервер достижим и слушает на правильном префиксе.
    """
    return JsonResponse({"ok": True, "service": "printer-inventory", "api_version": "v1"})


def _read_json(request):
    if request.content_type and not request.content_type.startswith("application/json"):
        return None, JsonResponse({"error": "Content-Type must be application/json"}, status=400)
    if len(request.body) > MAX_BODY_BYTES:
        return None, JsonResponse({"error": "request body too large"}, status=413)
    try:
        return json.loads(request.body.decode("utf-8")), None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, JsonResponse({"error": f"invalid json: {e}"}, status=400)


@csrf_exempt
@require_POST
def register_agent(request):
    data, err = _read_json(request)
    if err:
        return err

    try:
        agent, plaintext_token = register_or_get_agent(
            registration_key=str(data.get("registration_key") or ""),
            expected_key=getattr(settings, "USB_AGENT_REGISTRATION_KEY", ""),
            agent_id=str(data.get("agent_id") or "").strip(),
            hostname=str(data.get("hostname") or "").strip(),
            agent_version=str(data.get("agent_version") or "").strip(),
        )
    except USBReadingError as e:
        msg = str(e)
        status = 403 if "registration key" in msg or "deactivated" in msg else 400
        return JsonResponse({"error": msg}, status=status)

    return JsonResponse(
        {"agent_id": agent.agent_id, "token": plaintext_token, "message": "Agent registered"},
        status=201,
    )


@csrf_exempt
@require_POST
@usb_agent_required
def submit_readings(request):
    data, err = _read_json(request)
    if err:
        return err

    readings = data.get("readings")
    if not isinstance(readings, list):
        return JsonResponse({"error": "'readings' must be a list"}, status=400)
    if not readings:
        return JsonResponse({"error": "'readings' is empty"}, status=400)
    if len(readings) > MAX_READINGS_PER_BATCH:
        return JsonResponse({"error": f"too many readings (>{MAX_READINGS_PER_BATCH})"}, status=400)

    # обновляем agent_version, если пришёл
    incoming_version = str(data.get("agent_version") or "").strip()
    if incoming_version and request.usb_agent.agent_version != incoming_version:
        request.usb_agent.agent_version = incoming_version
        request.usb_agent.save(update_fields=["agent_version"])

    results = []
    for reading in readings:
        if not isinstance(reading, dict):
            results.append({"status": "error", "error": "reading must be an object"})
            continue
        try:
            results.append(process_usb_reading(request.usb_agent, reading))
        except Exception as e:  # pragma: no cover — финальный safety net
            logger.exception("USB: unexpected error processing reading from %s", request.usb_agent.agent_id)
            results.append({"status": "error", "error": f"internal: {e.__class__.__name__}"})

    return JsonResponse({"processed": len(results), "results": results}, status=200)
