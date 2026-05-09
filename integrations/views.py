"""
API endpoints для интеграций.
"""

import json
import logging
from html import escape

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from contracts.models import ContractDevice

from .glpi.services import (
    check_device_in_glpi,
    check_multiple_devices_in_glpi,
    get_devices_not_in_glpi,
    get_devices_with_conflicts,
    get_last_sync_for_device,
)
from .models import OkdeskIssue

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

    # Телефон и ФИО пользователя для подписи
    from access.models import UserProfile

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    user_phone = profile.phone
    user_full_name = f"{request.user.last_name} {request.user.first_name}".strip() or request.user.username

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

    # Ищем заявки — связь идёт через FK contract_device
    results = []
    issues = OkdeskIssue.objects.filter(contract_device=device).order_by("-created_at")

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
            "user_full_name": user_full_name,
            "user_phone": user_phone,
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
    phone = data.get("phone", "").strip()

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
    # escape() защищает от HTML-инъекций в сторонней системе Okdesk
    org = escape(device.organization.name) if device.organization else ""
    city = escape(device.city.name) if device.city else ""
    address = escape(device.address or "")
    room = escape(device.room_number or "")
    manufacturer = escape(device.model.manufacturer.name) if device.model and device.model.manufacturer else ""
    model = escape(device.model.name) if device.model else ""
    serial = escape(device.serial_number or "")
    cartridge = escape(cartridge)
    service_type = escape(service_type)
    comment = escape(comment)
    phone = escape(phone)

    # Сохраняем телефон в профиль пользователя для будущих заявок
    if phone:
        from access.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.phone != phone:
            profile.phone = phone
            profile.save(update_fields=["phone", "updated_at"])

    # ФИО (Фамилия Имя Отчество) для подписи в письме
    full_fio = f"{request.user.last_name} {request.user.first_name}".strip() or request.user.username
    user_full_name = escape(full_fio)
    # Формат Okdesk — "Фамилия Имя" (без отчества): last_name + первое слово first_name
    first_name_only = (request.user.first_name or "").split()[0] if request.user.first_name else ""
    okdesk_author_name = f"{request.user.last_name} {first_name_only}".strip() or request.user.username
    signature_parts = [f"С уважением, {user_full_name}"]
    if phone:
        signature_parts.append(phone)
    signature = "<br>".join(signature_parts)

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
<br>
<p>{signature}</p>
"""

    title = f"Заявка на {service_type.lower()}. {city}. {serial}"

    # Отправляем в Okdesk
    try:
        resp = requests.post(
            f"{OKDESK_API_URL}/issues/",
            params={"api_token": token_obj.get_token()},
            json={"issue": {"title": title, "description": description}},
            verify=settings.OKDESK_VERIFY_SSL,
            timeout=15,
        )

        if resp.status_code == 401:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Неверный API-токен Okdesk. Обновите токен в меню пользователя.",
                },
                status=403,
            )

        resp.raise_for_status()
        result = resp.json()
        issue_id = result.get("id")

        # Сохраняем заявку локально, чтобы она сразу отображалась в списке
        if issue_id:
            from django.utils import timezone

            OkdeskIssue.objects.update_or_create(
                issue_id=issue_id,
                contract_device=device,
                defaults={
                    "title": title,
                    "created_at": timezone.now(),
                    "status_name": "Открыта",
                    "author_name": okdesk_author_name,
                    "serial_numbers": device.serial_number or "",
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


# ──────────────────────────────────────────────────────────────────────────────
# Service Desk dashboard (Okdesk)
# Все view запрашивают view_okdesk_issues — невидимы пользователям без права.
# Бизнес-логика — в integrations.services_okdesk_dashboard
# ──────────────────────────────────────────────────────────────────────────────


@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def okdesk_dashboard_view(request):
    """Страница Service Desk — рендерит шаблон с Vue mount-point."""
    from access.models import UserOkdeskToken

    from .services_okdesk_dashboard import get_user_okdesk_name

    has_token = UserOkdeskToken.objects.filter(user=request.user).exists()
    context = {
        "permissions_json": json.dumps(
            {
                "view_okdesk_issues": request.user.has_perm("integrations.view_okdesk_issues"),
                "create_okdesk_issue": request.user.has_perm("integrations.create_okdesk_issue"),
                "post_okdesk_comment": request.user.has_perm("integrations.post_okdesk_comment"),
            }
        ),
        "user_context_json": json.dumps(
            {
                "okdesk_name": get_user_okdesk_name(request.user) or "",
                "has_okdesk_token": has_token,
            }
        ),
    }
    return render(request, "integrations/okdesk_dashboard.html", context)


def _mine_param(request):
    return (request.GET.get("mine", "") or "").lower() in ("1", "true", "yes")


def _filter_params(request):
    """Общие фильтры для всех okdesk-эндпоинтов: поиск (по серийнику/
    организации/теме/компании) и инициатор. Инициаторов может быть несколько —
    передаются повторяющимися параметрами `?author=A&author=B`."""
    authors = [a.strip() for a in request.GET.getlist("author") if a and a.strip()]
    return {
        "search": (request.GET.get("q", "") or "").strip(),
        "author": authors,
    }


def _date_range_params(request):
    """Диапазон дат YYYY-MM-DD для табов Active/Closed."""
    return {
        "date_from": (request.GET.get("date_from") or "").strip() or None,
        "date_to": (request.GET.get("date_to") or "").strip() or None,
    }


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_daily_stats(request):
    from .services_okdesk_dashboard import get_daily_stats

    target_date = request.GET.get("date") or None
    return JsonResponse(
        get_daily_stats(target_date, user=request.user, mine=_mine_param(request), **_filter_params(request))
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_daily_comments(request):
    from .services_okdesk_dashboard import get_daily_comments

    target_date = request.GET.get("date") or None
    page = int(request.GET.get("page", 1) or 1)
    per_page = min(int(request.GET.get("per_page", 50) or 50), 200)
    return JsonResponse(
        get_daily_comments(
            target_date,
            page=page,
            per_page=per_page,
            user=request.user,
            mine=_mine_param(request),
            **_filter_params(request),
        )
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_active_grouped(request):
    from .services_okdesk_dashboard import get_active_grouped_by_status

    return JsonResponse(
        {
            "groups": get_active_grouped_by_status(
                user=request.user,
                mine=_mine_param(request),
                **_filter_params(request),
                **_date_range_params(request),
            )
        }
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_by_status(request, status_name):
    from urllib.parse import unquote

    from .services_okdesk_dashboard import get_issues_by_status

    page = int(request.GET.get("page", 1) or 1)
    return JsonResponse(
        get_issues_by_status(
            unquote(status_name),
            page=page,
            user=request.user,
            mine=_mine_param(request),
            **_filter_params(request),
            **_date_range_params(request),
        )
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_analytics(request):
    """Сводная аналитика за период (по умолчанию — последние 30 дней)."""
    from .services_okdesk_analytics import get_okdesk_analytics

    only_created = (request.GET.get("only_period_created", "") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    return JsonResponse(
        get_okdesk_analytics(
            user=request.user,
            mine=_mine_param(request),
            only_period_created=only_created,
            **_filter_params(request),
            **_date_range_params(request),
        )
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_authors(request):
    """Список уникальных инициаторов заявок для автодополнения фильтра."""
    from .services_okdesk_dashboard import get_distinct_authors

    q = (request.GET.get("q", "") or "").strip()
    return JsonResponse({"authors": get_distinct_authors(q, limit=200)})


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_closed(request):
    from .services_okdesk_dashboard import get_closed_issues

    page = int(request.GET.get("page", 1) or 1)
    filters = _filter_params(request)
    return JsonResponse(
        get_closed_issues(
            page=page,
            search=filters["search"],
            author=filters["author"],
            user=request.user,
            mine=_mine_param(request),
            **_date_range_params(request),
        )
    )


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def api_okdesk_issue_detail(request, issue_id):
    from .services_okdesk_dashboard import get_issue_detail

    detail = get_issue_detail(int(issue_id))
    if not detail:
        return JsonResponse({"error": "issue not found"}, status=404)
    return JsonResponse(detail)


def _xlsx_response(content, filename):
    resp = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_created(request, date_str):
    from .services_okdesk_dashboard import export_created_excel

    content, filename = export_created_excel(date_str)
    return _xlsx_response(content, filename)


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_closed(request, date_str):
    from .services_okdesk_dashboard import export_closed_excel

    content, filename = export_closed_excel(date_str)
    return _xlsx_response(content, filename)


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_by_status(request, status_name):
    from urllib.parse import unquote

    from .services_okdesk_dashboard import export_by_status_excel

    content, filename = export_by_status_excel(unquote(status_name))
    return _xlsx_response(content, filename)


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_active_all(request):
    from .services_okdesk_dashboard import export_all_active_excel

    content, filename = export_all_active_excel()
    return _xlsx_response(content, filename)


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_active_filtered(request):
    """Активные заявки с применением текущих фильтров (q/author/mine/date_from/date_to).
    Без параметров — выгружает всё (тогда совпадает по смыслу с active-all,
    но плоским листом)."""
    from .services_okdesk_dashboard import export_active_filtered_excel

    content, filename = export_active_filtered_excel(
        user=request.user,
        mine=_mine_param(request),
        **_filter_params(request),
        **_date_range_params(request),
    )
    return _xlsx_response(content, filename)


@require_GET
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def export_okdesk_closed_filtered(request):
    """Закрытые заявки с применением текущих фильтров."""
    from .services_okdesk_dashboard import export_closed_filtered_excel

    content, filename = export_closed_filtered_excel(
        user=request.user,
        mine=_mine_param(request),
        **_filter_params(request),
        **_date_range_params(request),
    )
    return _xlsx_response(content, filename)


@require_http_methods(["POST"])
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def okdesk_refresh_issue_comments(request, issue_id):
    """Точечная синхронизация комментариев одной заявки.

    Дёргается из модалки при открытии заявки — чтобы пользователь видел
    свежие комментарии без ожидания периодического background-sync'а.
    """
    from .services_okdesk_send import OkdeskSendError, refresh_issue_comments

    try:
        result = refresh_issue_comments(int(issue_id))
    except OkdeskSendError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=e.status_code)
    except Exception:
        logger.exception("refresh comments failed for issue %s", issue_id)
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка сервера"}, status=500)
    return JsonResponse({"ok": True, **result})


@require_http_methods(["POST"])
@login_required
@permission_required("integrations.post_okdesk_comment", raise_exception=True)
@ensure_csrf_cookie
def okdesk_post_comment(request, issue_id):
    """Отправка комментария в Okdesk от имени пользователя.

    Требует личный API-токен (UserOkdeskToken). Возвращает созданный комментарий.
    """
    from .services_okdesk_send import OkdeskSendError, post_comment_to_okdesk

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)

    content = (body.get("content") or "").strip()
    is_public = bool(body.get("is_public", True))

    try:
        comment = post_comment_to_okdesk(request.user, int(issue_id), content, is_public=is_public)
    except OkdeskSendError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=e.status_code)
    except Exception:
        logger.exception("post comment failed for issue %s by %s", issue_id, request.user.username)
        return JsonResponse({"ok": False, "error": "Внутренняя ошибка сервера"}, status=500)

    logger.info("Okdesk comment posted: issue=%s user=%s", issue_id, request.user.username)
    return JsonResponse({"ok": True, "comment": comment})


@require_http_methods(["POST"])
@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def okdesk_sync_now(request):
    """Ручной запуск синхронизации заявок и/или комментариев из Okdesk API.

    Вызывается с UI-кнопки. Запуск синхронный (.apply()) — таск выполняется
    в потоке запроса, чтобы пользователь сразу увидел результат. Для штатного
    периодического sync используется Celery beat (см. CELERY_BEAT_SCHEDULE).
    """
    from .tasks import sync_okdesk_comments, sync_okdesk_issues

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {}

    sync_issues = bool(body.get("issues", True))
    sync_comments = bool(body.get("comments", True))

    issues_result = None
    comments_result = None

    try:
        if sync_issues:
            issues_result = sync_okdesk_issues.apply().get()
        if sync_comments:
            comments_result = sync_okdesk_comments.apply().get()
    except Exception as e:
        logger.exception("Okdesk sync (manual) failed")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    return JsonResponse({"ok": True, "issues": issues_result, "comments": comments_result})
