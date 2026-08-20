"""
API endpoints для интеграций.
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from contracts.models import ContractDevice

from .api_docs_decorators import (
    api_okdesk_active_grouped_schema,
    api_okdesk_authors_schema,
    api_okdesk_by_status_schema,
    api_okdesk_closed_schema,
    api_okdesk_daily_comments_schema,
    api_okdesk_daily_stats_schema,
    api_okdesk_issue_detail_schema,
    check_device_glpi_schema,
    check_multiple_devices_glpi_schema,
    create_service_request_schema,
    get_device_sync_status_schema,
    get_devices_not_in_glpi_schema,
    get_glpi_conflicts_schema,
    get_okdesk_issues_schema,
    okdesk_post_comment_schema,
    okdesk_refresh_issue_comments_schema,
    okdesk_sync_now_schema,
    okdesk_sync_status_schema,
)
from .glpi.services import (
    check_device_in_glpi,
    check_multiple_devices_in_glpi,
    get_devices_not_in_glpi,
    get_devices_with_conflicts,
    get_last_sync_for_device,
)
from .models import OkdeskIssue
from .okdesk_secrets import mask_api_token

logger = logging.getLogger(__name__)


@login_required
@check_device_glpi_schema
@permission_required("contracts.view_contractdevice", raise_exception=True)
@require_http_methods(["POST"])
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


@login_required
@check_multiple_devices_glpi_schema
@permission_required("contracts.view_contractdevice", raise_exception=True)
@require_http_methods(["POST"])
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


@login_required
@get_device_sync_status_schema
@permission_required("contracts.view_contractdevice", raise_exception=True)
@require_GET
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


@login_required
@get_glpi_conflicts_schema
@permission_required("contracts.view_contractdevice", raise_exception=True)
@require_GET
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


@login_required
@get_devices_not_in_glpi_schema
@permission_required("contracts.view_contractdevice", raise_exception=True)
@require_GET
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


def _journal_requests_for_device(device, user, okdesk_results):
    """Заявки из нашего журнала по устройству — почтовые в Okdesk не попадают.

    Заявки, ушедшие в Okdesk, уже есть в списке зеркала (там богаче статус),
    поэтому по номеру у подрядчика их отсеиваем, чтобы не задвоить.
    """
    from django.db.models import OuterRef, Subquery

    from contracts.models import ServiceRequest, ServiceRequestMessage

    # Описание — это необязательный комментарий из формы, а тип обслуживания есть
    # только в теме исходящего письма, поэтому она и служит заголовком строки
    first_subject = (
        ServiceRequestMessage.objects.filter(service_request=OuterRef("pk"), direction=ServiceRequestMessage.OUTGOING)
        .order_by("pk")
        .values("subject")[:1]
    )
    requests = (
        ServiceRequest.objects.filter(device=device)
        .select_related("service_provider")
        .annotate(outgoing_subject=Subquery(first_subject))
    )
    if not user.has_perm("contracts.view_servicerequest"):
        if not user.has_perm("contracts.create_service_request"):
            return []
        requests = requests.filter(initiator=user)

    mirrored = {str(item["id"]) for item in okdesk_results}

    def urgency(service_request):
        if not service_request.stops_printing and not service_request.counts_in_sla:
            return "Плановая"
        if service_request.is_critical:
            return "Критичная"
        return "Обычная" if service_request.stops_printing else "Печать работает"

    def title(service_request):
        if service_request.description.strip():
            return service_request.description.strip()
        subject = (service_request.outgoing_subject or "").strip()
        # Номер заявки уже есть в отдельной колонке — из темы письма его убираем
        prefix = f"Заявка № {service_request.number}."
        if subject.startswith(prefix):
            subject = subject[len(prefix) :].strip()
        return subject or "Без описания"

    payload = []
    for service_request in requests:
        if service_request.external_number and service_request.external_number in mirrored:
            continue
        payload.append(
            {
                "id": service_request.number,
                "source": "journal",
                "title": title(service_request),
                "created_at": service_request.registered_at.isoformat(),
                "completed_at": service_request.closed_at.isoformat() if service_request.closed_at else None,
                "status_name": service_request.get_status_display(),
                "priority_name": urgency(service_request),
                "assignee_name": service_request.service_provider.name if service_request.service_provider_id else "",
                "is_overdue": service_request.is_overdue,
            }
        )
    return payload


@login_required
@get_okdesk_issues_schema
@permission_required("integrations.view_okdesk_issues")
@require_GET
def get_okdesk_issues(request, device_id):
    """
    Получает заявки Okdesk по серийному номеру устройства.
    Также возвращает device_info с картриджами и has_okdesk_token.

    GET /integrations/okdesk/issues/<device_id>/
    """
    from access.models import UserOkdeskToken
    from contracts.services_requests import collects_urgency

    try:
        device = (
            ContractDevice.objects.select_related(
                "organization",
                "city",
                "model__manufacturer",
                "service_provider",
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
                "source": "okdesk",
                "title": issue.title,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "completed_at": issue.completed_at.isoformat() if issue.completed_at else None,
                "status_name": issue.status_name,
                "priority_name": issue.priority_name,
                "assignee_name": issue.assignee_name,
                "is_overdue": issue.is_overdue,
            }
        )

    results.extend(_journal_requests_for_device(device, request.user, results))
    results.sort(key=lambda item: item["created_at"] or "", reverse=True)

    return JsonResponse(
        {
            "ok": True,
            "issues": results,
            "count": len(results),
            "has_okdesk_token": has_token,
            # Личный токен нужен только каналу Okdesk; почтовый канал подаёт заявку без него
            "request_channel": device.service_provider.issue_tracker if device.service_provider_id else None,
            "collects_urgency": collects_urgency(device),
            "device_info": device_info,
            "user_full_name": user_full_name,
            "user_phone": user_phone,
        }
    )


OKDESK_API_URL = getattr(settings, "OKDESK_API_URL", "https://abikom.okdesk.ru/api/v1")


@login_required
@create_service_request_schema
@permission_required("contracts.create_service_request", raise_exception=True)
@require_http_methods(["POST"])
@ensure_csrf_cookie
def create_service_request(request):
    """
    Регистрирует заявку в журнале и передаёт её подрядчику устройства.

    Канал выбирается по подрядчику: Okdesk API или письмо на почту сервис-деска,
    вся логика — в contracts.services_requests.

    POST /integrations/requests/create/
    Body: {"device_id": 123, "cartridge": "...", "service_type": "Обслуживание", "comment": "..."}
    """
    from contracts.services_requests import SubmissionContext, SubmissionError, submit_service_request

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Неверный формат JSON"}, status=400)

    device_id = data.get("device_id")
    if not device_id:
        return JsonResponse({"ok": False, "error": "Не указан device_id"}, status=400)

    phone = data.get("phone", "").strip()
    if phone:
        from access.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.phone != phone:
            profile.phone = phone
            profile.save(update_fields=["phone", "updated_at"])

    context = SubmissionContext(
        user=request.user,
        phone=phone,
        cartridge=data.get("cartridge", ""),
        service_type=data.get("service_type", "Обслуживание"),
    )

    try:
        service_request = submit_service_request(
            device_id=device_id,
            description=data.get("comment", ""),
            context=context,
            stops_printing=bool(data.get("stops_printing", True)),
            counts_in_sla=bool(data.get("counts_in_sla", True)),
            is_critical=bool(data.get("is_critical", False)),
        )
    except SubmissionError as exc:
        return JsonResponse({"ok": False, "error": str(exc), "retry": exc.retry}, status=exc.status)

    logger.info(
        "Заявка %s создана пользователем %s по устройству %s",
        service_request.number,
        request.user.username,
        device_id,
    )
    return JsonResponse(
        {
            "ok": True,
            "issue_id": service_request.external_number or None,
            "request_number": service_request.number,
            "deadline_at": service_request.deadline_at.isoformat() if service_request.deadline_at else None,
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Архив заявок Okdesk
# Все view запрашивают view_okdesk_issues — невидимы пользователям без права.
# Бизнес-логика — в integrations.services_okdesk_dashboard
# ──────────────────────────────────────────────────────────────────────────────


@login_required
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
def okdesk_dashboard_view(request):
    """Страница архива Okdesk — рендерит шаблон с Vue mount-point."""
    from access.models import UserOkdeskToken

    from .services_okdesk_dashboard import get_user_okdesk_name

    has_token = UserOkdeskToken.objects.filter(user=request.user).exists()
    context = {
        "permissions_json": json.dumps(
            {
                "view_okdesk_issues": request.user.has_perm("integrations.view_okdesk_issues"),
                "post_okdesk_comment": request.user.has_perm("integrations.post_okdesk_comment"),
                "view_journal": request.user.has_perm("contracts.view_servicerequest"),
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


@login_required
@api_okdesk_daily_stats_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
def api_okdesk_daily_stats(request):
    from .services_okdesk_dashboard import get_daily_stats

    target_date = request.GET.get("date") or None
    return JsonResponse(
        get_daily_stats(target_date, user=request.user, mine=_mine_param(request), **_filter_params(request))
    )


@login_required
@api_okdesk_daily_comments_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
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


@login_required
@api_okdesk_active_grouped_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
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


@login_required
@api_okdesk_by_status_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
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


@login_required
@api_okdesk_authors_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
def api_okdesk_authors(request):
    """Список уникальных инициаторов заявок для автодополнения фильтра."""
    from .services_okdesk_dashboard import get_distinct_authors

    q = (request.GET.get("q", "") or "").strip()
    return JsonResponse({"authors": get_distinct_authors(q, limit=200)})


@login_required
@api_okdesk_closed_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
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


@login_required
@api_okdesk_issue_detail_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
def api_okdesk_issue_detail(request, issue_id):
    from .services_okdesk_dashboard import get_issue_detail

    detail = get_issue_detail(int(issue_id))
    if not detail:
        return JsonResponse({"error": "issue not found"}, status=404)
    return JsonResponse(detail)


@login_required
@okdesk_refresh_issue_comments_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_http_methods(["POST"])
def okdesk_refresh_issue_comments(request, issue_id):
    """Запускает фоновую точечную синхронизацию комментариев заявки.

    Возвращает task_id; фронт опрашивает /sync-status/ и после ready=true
    перезагружает заявку из БД. Раньше делался синхронный requests.get
    к Okdesk прямо во view — блокировал ASGI-worker на время сетевого
    ответа Okdesk.
    """
    from .tasks import refresh_okdesk_issue_comments_task

    try:
        task_id = refresh_okdesk_issue_comments_task.delay(int(issue_id)).id
    except Exception:
        logger.exception("enqueue refresh comments failed for issue %s", issue_id)
        return JsonResponse({"ok": False, "error": "Не удалось поставить задачу"}, status=500)
    return JsonResponse({"ok": True, "task_id": task_id}, status=202)


@login_required
@okdesk_post_comment_schema
@permission_required("integrations.post_okdesk_comment", raise_exception=True)
@require_http_methods(["POST"])
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


# Anti-spam lock для ручного sync (одновременно может бежать только один)
_SYNC_LOCK_KEY = "okdesk:manual_sync:running"
_SYNC_LOCK_TTL = 60 * 60 * 4  # 4 часа — соответствует time_limit у sync_okdesk_issues


@login_required
@okdesk_sync_now_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_http_methods(["POST"])
def okdesk_sync_now(request):
    """Ручной запуск синхронизации заявок/комментариев из Okdesk API.

    Запуск асинхронный (.delay()): возвращает task_id, фронт опрашивает
    /sync-status/. Раньше использовался .apply().get() в потоке запроса —
    при таймауте Okdesk API это блокировало ASGI-worker и зависало приложение
    для всех пользователей.
    """
    from django.core.cache import cache

    from .tasks import sync_okdesk_comments, sync_okdesk_issues

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        body = {}

    sync_issues = bool(body.get("issues", True))
    sync_comments = bool(body.get("comments", True))

    if not (sync_issues or sync_comments):
        return JsonResponse({"ok": False, "error": "Нечего синхронизировать"}, status=400)

    # Anti-spam: один ручной sync на инстанс. cache.add — атомарно.
    if not cache.add(_SYNC_LOCK_KEY, "1", timeout=_SYNC_LOCK_TTL):
        return JsonResponse(
            {"ok": False, "error": "Синхронизация уже запущена. Подождите её завершения."},
            status=409,
        )

    try:
        task_ids = {}
        if sync_issues:
            task_ids["issues"] = sync_okdesk_issues.delay().id
        if sync_comments:
            task_ids["comments"] = sync_okdesk_comments.delay().id
    except Exception as e:
        cache.delete(_SYNC_LOCK_KEY)
        logger.exception("Okdesk sync (manual): enqueue failed")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)

    return JsonResponse({"ok": True, "tasks": task_ids})


@login_required
@okdesk_sync_status_schema
@permission_required("integrations.view_okdesk_issues", raise_exception=True)
@require_GET
def okdesk_sync_status(request):
    """Статус задач из последнего sync-now: { tasks: {issues|comments: state} }.

    Параметр ?ids=<id1>,<id2> — task_id'ы, полученные от sync-now.
    Когда все задачи терминальные — снимает anti-spam lock.
    """
    from celery.result import AsyncResult
    from django.core.cache import cache

    raw_ids = (request.GET.get("ids") or "").strip()
    if not raw_ids:
        return JsonResponse({"ok": False, "error": "ids required"}, status=400)
    # release_lock=1 — снять lock ручного sync. Передаётся только из UI sync-now,
    # чтобы refresh-comments / экспорты не сбрасывали lock чужой задачи.
    release_lock = (request.GET.get("release_lock") or "").lower() in ("1", "true", "yes")

    task_ids = [tid for tid in (s.strip() for s in raw_ids.split(",")) if tid]
    results = {}
    all_done = True
    for tid in task_ids:
        res = AsyncResult(tid)
        info = {"state": res.state, "ready": res.ready()}
        if res.ready():
            if res.successful():
                info["result"] = (
                    res.result
                    if isinstance(res.result, (dict, list, str, int, float, bool, type(None)))
                    else str(res.result)
                )
            else:
                # Сообщение исключения requests несёт полный URL запроса вместе с
                # api_token, а этот эндпоинт доступен по одному лишь праву на чтение.
                info["error"] = mask_api_token(res.result)
        else:
            all_done = False
        results[tid] = info

    if all_done and release_lock:
        cache.delete(_SYNC_LOCK_KEY)

    return JsonResponse({"ok": True, "all_done": all_done, "tasks": results})
