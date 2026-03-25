"""
API endpoints для интеграций.
"""

import json
import logging

import requests
import urllib3
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from contracts.models import ContractDevice

from .glpi.services import (
    check_device_in_glpi,
    check_multiple_devices_in_glpi,
    get_devices_not_in_glpi,
    get_devices_with_conflicts,
    get_last_sync_for_device,
)
from .models import OkdeskIssue

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@login_required
@permission_required("contracts.view_contractdevice", raise_exception=True)
@ensure_csrf_cookie
def check_device_glpi(request, device_id):
    """
    Проверяет одно устройство в GLPI.

    POST /integrations/glpi/check-device/<device_id>/
    """
    try:
        device = ContractDevice.objects.get(id=device_id)
    except ContractDevice.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Устройство не найдено"}, status=404)

    # Принудительная проверка или использовать кэш?
    force_check = False
    try:
        body = json.loads(request.body.decode("utf-8"))
        force_check = body.get("force", False)
    except (json.JSONDecodeError, UnicodeDecodeError):
        force_check = request.POST.get("force", "false").lower() == "true"

    try:
        logger.info(f"GLPI check: device_id={device_id}, serial={device.serial_number}, user={request.user.username}")
        sync = check_device_in_glpi(device, user=request.user, force_check=force_check)

        return JsonResponse(
            {
                "ok": True,
                "sync": {
                    "id": sync.id,
                    "status": sync.status,
                    "status_display": sync.get_status_display(),
                    "glpi_ids": sync.glpi_ids,
                    "glpi_count": sync.glpi_count,
                    "is_synced": sync.is_synced,
                    "has_conflict": sync.has_conflict,
                    "glpi_state_id": sync.glpi_state_id,
                    "glpi_state_name": sync.glpi_state_name,
                    "error_message": sync.error_message,
                    "checked_at": sync.checked_at.isoformat(),
                    "checked_by": sync.checked_by.username if sync.checked_by else None,
                },
            }
        )

    except Exception as e:
        logger.exception(f"Ошибка при проверке устройства {device_id} в GLPI: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_http_methods(["POST"])
@login_required
@permission_required("contracts.view_contractdevice", raise_exception=True)
@ensure_csrf_cookie
def check_multiple_devices_glpi(request):
    """
    Проверяет несколько устройств в GLPI.

    POST /integrations/glpi/check-multiple/
    Body: {"device_ids": [1, 2, 3]}
    """
    import json

    try:
        data = json.loads(request.body)
        device_ids = data.get("device_ids", [])

        if not device_ids:
            return JsonResponse({"ok": False, "error": "Не указаны ID устройств"}, status=400)

        # Ограничение на количество
        if len(device_ids) > 100:
            return JsonResponse({"ok": False, "error": "Максимум 100 устройств за один запрос"}, status=400)

        stats = check_multiple_devices_in_glpi(device_ids, user=request.user)

        return JsonResponse({"ok": True, "stats": stats})

    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)
    except Exception as e:
        logger.exception(f"Ошибка при массовой проверке устройств в GLPI: {e}")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_http_methods(["GET"])
@login_required
@permission_required("contracts.view_contractdevice", raise_exception=True)
def get_device_sync_status(request, device_id):
    """
    Получает статус последней синхронизации для устройства.

    GET /integrations/glpi/sync-status/<device_id>/
    """
    try:
        device = ContractDevice.objects.get(id=device_id)
    except ContractDevice.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Устройство не найдено"}, status=404)

    sync = get_last_sync_for_device(device)

    if not sync:
        return JsonResponse({"ok": True, "sync": None, "message": "Устройство ещё не проверялось в GLPI"})

    return JsonResponse(
        {
            "ok": True,
            "sync": {
                "id": sync.id,
                "status": sync.status,
                "status_display": sync.get_status_display(),
                "glpi_ids": sync.glpi_ids,
                "glpi_count": sync.glpi_count,
                "is_synced": sync.is_synced,
                "has_conflict": sync.has_conflict,
                "glpi_state_id": sync.glpi_state_id,
                "glpi_state_name": sync.glpi_state_name,
                "error_message": sync.error_message,
                "checked_at": sync.checked_at.isoformat(),
                "checked_by": sync.checked_by.username if sync.checked_by else None,
            },
        }
    )


@require_http_methods(["GET"])
@login_required
@permission_required("contracts.view_contractdevice", raise_exception=True)
def get_glpi_conflicts(request):
    """
    Получает список устройств с конфликтами в GLPI (найдено несколько карточек).

    GET /integrations/glpi/conflicts/
    """
    devices = get_devices_with_conflicts()

    results = []
    for device in devices:
        sync = get_last_sync_for_device(device)
        results.append(
            {
                "device_id": device.id,
                "serial_number": device.serial_number,
                "model": str(device.model),
                "organization": device.organization.name,
                "glpi_count": sync.glpi_count if sync else 0,
                "glpi_ids": sync.glpi_ids if sync else [],
                "checked_at": sync.checked_at.isoformat() if sync else None,
            }
        )

    return JsonResponse({"ok": True, "count": len(results), "devices": results})


@require_http_methods(["GET"])
@login_required
@permission_required("contracts.view_contractdevice", raise_exception=True)
def get_devices_not_in_glpi_view(request):
    """
    Получает список устройств, не найденных в GLPI.

    GET /integrations/glpi/not-found/
    """
    devices = get_devices_not_in_glpi()

    results = []
    for device in devices:
        sync = get_last_sync_for_device(device)
        results.append(
            {
                "device_id": device.id,
                "serial_number": device.serial_number,
                "model": str(device.model),
                "organization": device.organization.name,
                "checked_at": sync.checked_at.isoformat() if sync else None,
            }
        )

    return JsonResponse({"ok": True, "count": len(results), "devices": results})


@require_http_methods(["GET"])
@login_required
@permission_required("integrations.view_okdesk_issues")
def get_okdesk_issues(request, device_id):
    """
    Получает заявки Okdesk по серийному номеру устройства.
    Также возвращает device_info с картриджами и has_okdesk_token.

    GET /integrations/okdesk/issues/<device_id>/
    """
    from access.models import UserOkdeskToken

    try:
        device = (
            ContractDevice.objects.select_related(
                "organization",
                "city",
                "model__manufacturer",
            )
            .prefetch_related("model__model_cartridges__cartridge")
            .get(id=device_id)
        )
    except ContractDevice.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Устройство не найдено"}, status=404)

    # Проверяем наличие токена у пользователя
    has_token = UserOkdeskToken.objects.filter(user=request.user).exists()

    # Собираем информацию об устройстве для формы создания заявки
    cartridge_text = ""
    if device.model:
        cartridges = device.model.model_cartridges.select_related("cartridge").all()
        primary = [mc.cartridge for mc in cartridges if mc.is_primary]
        other = [mc.cartridge for mc in cartridges if not mc.is_primary]
        parts = []
        for c in primary + other:
            name_parts = [c.name]
            if c.part_number:
                name_parts.append(f"({c.part_number})")
            parts.append(" ".join(name_parts))
        cartridge_text = ", ".join(parts)

    device_info = {
        "organization": device.organization.name if device.organization else "",
        "city": device.city.name if device.city else "",
        "address": device.address or "",
        "room_number": device.room_number or "",
        "manufacturer": device.model.manufacturer.name if device.model and device.model.manufacturer else "",
        "model": device.model.name if device.model else "",
        "serial_number": device.serial_number or "",
        "cartridge": cartridge_text,
        "comment": device.comment or "",
    }

    # Ищем заявки
    serial = device.serial_number
    results = []
    if serial:
        issues = OkdeskIssue.objects.filter(
            Q(serial_numbers=serial)
            | Q(serial_numbers__startswith=serial + ",")
            | Q(serial_numbers__endswith=", " + serial)
            | Q(serial_numbers__contains=", " + serial + ",")
        ).order_by("-created_at")

        for issue in issues:
            results.append(
                {
                    "id": issue.issue_id,
                    "title": issue.title,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "completed_at": issue.completed_at.isoformat() if issue.completed_at else None,
                    "status_name": issue.status_name,
                    "priority_name": issue.priority_name,
                    "assignee_name": issue.assignee_name,
                    "is_overdue": issue.is_overdue,
                }
            )

    return JsonResponse(
        {
            "ok": True,
            "issues": results,
            "count": len(results),
            "has_okdesk_token": has_token,
            "device_info": device_info,
        }
    )


OKDESK_API_URL = getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")


@require_http_methods(["POST"])
@login_required
@permission_required("integrations.create_okdesk_issue")
@ensure_csrf_cookie
def create_okdesk_issue(request):
    """
    Создаёт заявку в Okdesk через API с токеном пользователя.

    POST /integrations/okdesk/create-issue/
    Body: {"device_id": 123, "cartridge": "...", "service_type": "Обслуживание", "comment": "..."}
    """
    from access.models import UserOkdeskToken

    # Проверяем токен
    try:
        token_obj = UserOkdeskToken.objects.get(user=request.user)
    except UserOkdeskToken.DoesNotExist:
        return JsonResponse(
            {
                "ok": False,
                "error": "API-токен Okdesk не настроен. Добавьте его в меню пользователя → Токен Okdesk.",
            },
            status=403,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)

    device_id = data.get("device_id")
    cartridge = data.get("cartridge", "")
    service_type = data.get("service_type", "Обслуживание")
    comment = data.get("comment", "")

    if not device_id:
        return JsonResponse({"ok": False, "error": "Не указан device_id"}, status=400)

    try:
        device = ContractDevice.objects.select_related(
            "organization",
            "city",
            "model__manufacturer",
        ).get(id=device_id)
    except ContractDevice.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Устройство не найдено"}, status=404)

    # Формируем HTML-описание по паттерну email
    org = device.organization.name if device.organization else ""
    city = device.city.name if device.city else ""
    address = device.address or ""
    room = device.room_number or ""
    manufacturer = device.model.manufacturer.name if device.model and device.model.manufacturer else ""
    model = device.model.name if device.model else ""
    serial = device.serial_number or ""

    description = f"""
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
  <thead>
    <tr>
      <th>№</th>
      <th>Организация</th>
      <th>Город</th>
      <th>Адрес</th>
      <th>Кабинет</th>
      <th>Производитель</th>
      <th>Модель</th>
      <th>Серийный номер</th>
      <th>Картридж</th>
      <th>Ремонт/обслуживание</th>
      <th>Комментарии</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>{org}</td>
      <td>{city}</td>
      <td>{address}</td>
      <td>{room}</td>
      <td>{manufacturer}</td>
      <td>{model}</td>
      <td>{serial}</td>
      <td>{cartridge}</td>
      <td>{service_type}</td>
      <td>{comment}</td>
    </tr>
  </tbody>
</table>
"""

    title = f"Заявка на {service_type.lower()}. {city}. {serial}"

    # Отправляем в Okdesk
    try:
        resp = requests.post(
            f"{OKDESK_API_URL}/issues/",
            params={"api_token": token_obj.get_token()},
            json={"issue": {"title": title, "description": description}},
            verify=False,
            timeout=15,
        )

        if resp.status_code == 401:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Неверный API-токен Okdesk. Обновите токен в меню пользователя.",
                },
                status=401,
            )

        resp.raise_for_status()
        result = resp.json()
        issue_id = result.get("id")

        # Сохраняем заявку локально, чтобы она сразу отображалась в списке
        if issue_id:
            from django.utils import timezone

            OkdeskIssue.objects.update_or_create(
                issue_id=issue_id,
                defaults={
                    "title": title,
                    "created_at": timezone.now(),
                    "status_name": "Открыта",
                    "serial_numbers": serial,
                    "company_name": org,
                    "source": OkdeskIssue.SOURCE_CREATED,
                    "created_by": request.user,
                    "synced_at": timezone.now(),
                },
            )

        logger.info(f"Okdesk issue #{issue_id} created by {request.user.username} for device {device_id}")

        return JsonResponse({"ok": True, "issue_id": issue_id})

    except requests.Timeout:
        return JsonResponse(
            {
                "ok": False,
                "error": "Сервер Okdesk не отвечает. Попробуйте повторить через несколько минут.",
                "retry": True,
            },
            status=504,
        )
    except requests.ConnectionError:
        return JsonResponse(
            {
                "ok": False,
                "error": "Нет соединения с сервером Okdesk. Проверьте сеть и попробуйте позже.",
                "retry": True,
            },
            status=502,
        )
    except requests.RequestException as e:
        logger.exception(f"Ошибка при создании заявки в Okdesk: {e}")
        return JsonResponse(
            {
                "ok": False,
                "error": f"Ошибка API Okdesk: {e}. Попробуйте повторить позже.",
                "retry": True,
            },
            status=502,
        )
