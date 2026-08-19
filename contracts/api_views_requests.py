"""API журнала заявок подрядчику: список, отметка восстановления, приём акта.

Инициатор без права `view_servicerequest` видит только собственные заявки —
подавать их может почти любой сотрудник, а чужой журнал ему не нужен.
"""

import logging
from base64 import b64decode
from email.utils import parseaddr

import requests
from celery.result import AsyncResult

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Concat
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from access.services.notifications import mark_target_read
from integrations.okdesk_secrets import mask_api_token

from .models import ServiceRequest, ServiceRequestAttachment, ServiceRequestMessage, ServiceRequestSubscription
from .services_okdesk_import import download_attachment_file
from .services_request_analytics import build_analytics
from .services_request_closing import (
    ALLOWED_ACT_EXTENSIONS,
    act_attachment,
    close_by_act,
    close_by_letter,
    close_by_message,
    mark_restored,
)
from .services_request_notifications import notify_subscribers, target_key
from .services_requests import SubmissionError, channel_for_device
from .tasks import REQUEST_EXPORT_CACHE_PREFIX, build_request_export_task

logger = logging.getLogger(__name__)

PER_PAGE_CHOICES = (25, 50, 100, 200)
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _has_act_letter(pk_ref):
    """Есть ли входящее письмо с вложением, годным как скан акта.

    Расширения — те же ALLOWED_ACT_EXTENSIONS, что и у автозакрытия: незакрытая
    заявка с таким письмом подсвечивается как кандидат на закрытие.
    """
    act_name = Q()
    for ext in ALLOWED_ACT_EXTENSIONS:
        # Вложение без скачанного файла актом стать не может — по имени заявку не закрыть
        act_name |= Q(attachments__filename__iendswith=f".{ext}", attachments__file__gt="")
    return Exists(
        ServiceRequestMessage.objects.filter(
            service_request=OuterRef(pk_ref), direction=ServiceRequestMessage.INCOMING
        ).filter(act_name)
    )


def visible_requests(user):
    """Журнал целиком — по view_servicerequest, иначе только свои заявки."""
    # order_by явный: с annotate() Django не применяет Meta.ordering, и журнал
    # приезжает в произвольном порядке вместо «новые сверху».
    qs = (
        ServiceRequest.objects.select_related(
            "device__organization",
            "device__city",
            "device__model__manufacturer",
            "device__service_provider",
            "service_provider",
            "initiator",
            "closing_message",
        )
        .annotate(
            messages_total=Count("messages"),
            subscribed=Exists(ServiceRequestSubscription.objects.filter(service_request=OuterRef("pk"), user=user)),
            has_act_letter=_has_act_letter("pk"),
        )
        .order_by("-registered_at")
    )
    if user.has_perm("contracts.view_servicerequest"):
        return qs
    if user.has_perm("contracts.create_service_request"):
        return qs.filter(initiator=user)
    raise PermissionDenied("Нет доступа к журналу заявок")


def _initiator_name(service_request):
    if not service_request.initiator_id:
        return ""
    return service_request.initiator.get_full_name() or service_request.initiator.username


def _serialize(service_request):
    device = service_request.device
    provider_downtime = service_request.provider_downtime_hours
    return {
        "id": service_request.pk,
        "number": service_request.number,
        "external_number": service_request.external_number,
        "status": service_request.status,
        "status_display": service_request.get_status_display(),
        "device": {
            "id": device.pk,
            "organization": device.organization.name if device.organization_id else "",
            "city": device.city.name if device.city_id else "",
            "address": device.address,
            "room": device.room_number,
            "model": str(device.model) if device.model_id else "",
            "serial_number": device.serial_number,
        },
        "service_provider": service_request.service_provider.name if service_request.service_provider_id else "",
        # Канал ответа — по текущему подрядчику устройства (как в channel_for_device):
        # лента по нему решает, показывать почтовую форму или комментарий Okdesk
        "channel": device.service_provider.issue_tracker if device.service_provider_id else "",
        "description": service_request.description,
        "initiator": _initiator_name(service_request),
        "initiator_contacts": service_request.initiator_contacts,
        "stops_printing": service_request.stops_printing,
        "counts_in_sla": service_request.counts_in_sla,
        "is_critical": service_request.is_critical,
        "sla_hours": service_request.sla_hours,
        "registered_at": service_request.registered_at.isoformat(),
        "deadline_at": service_request.deadline_at.isoformat() if service_request.deadline_at else None,
        "restored_at": service_request.restored_at.isoformat() if service_request.restored_at else None,
        "closed_at": service_request.closed_at.isoformat() if service_request.closed_at else None,
        "is_overdue": service_request.is_overdue,
        "downtime_hours": round(service_request.downtime_hours(), 2),
        "act_number": service_request.act_number,
        "act_url": service_request.act_scan.url if service_request.act_scan else None,
        "closing_channel": service_request.closing_message.channel if service_request.closing_message_id else None,
        "provider_restored_at": (
            service_request.provider_restored_at.isoformat() if service_request.provider_restored_at else None
        ),
        "provider_downtime_hours": float(provider_downtime) if provider_downtime is not None else None,
        "restoration_discrepancy_hours": service_request.restoration_discrepancy_hours,
        "messages_count": service_request.messages_total,
        "subscribed": service_request.subscribed,
        # Подрядчик прислал похожее на акт вложение, а заявка не закрылась —
        # скорее всего, тема письма не формальная; закрывается кнопкой из ленты
        "closing_candidate": (
            service_request.status not in (ServiceRequest.CLOSED, ServiceRequest.REJECTED)
            and bool(getattr(service_request, "has_act_letter", False))
        ),
    }


def _serialize_message(message):
    return {
        "id": message.pk,
        "direction": message.direction,
        "channel": message.channel,
        "subject": message.subject,
        "from_email": message.from_email,
        "to_emails": message.to_emails,
        "body_text": message.body_text,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "request_number": message.service_request.number if message.service_request_id else "",
        "attachments": [
            {
                "id": attachment.pk,
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size": attachment.size,
                # url пуст, когда из Okdesk приехали только метаданные вложения
                "url": attachment.file.url if attachment.file else None,
                "can_fetch": bool(
                    not attachment.file and attachment.okdesk_issue_id and attachment.okdesk_attachment_id
                ),
            }
            for attachment in message.attachments.all()
        ],
        "has_act_attachment": (
            message.direction == ServiceRequestMessage.INCOMING and act_attachment(message) is not None
        ),
    }


def _filter_moment(raw):
    """Граница периода из фильтра. Нераспознанное значение фильтр просто не применяет."""
    moment = parse_datetime(raw or "")
    if moment is None:
        return None
    # Фронт шлёт локальную дату без пояса, а сравнение идёт с aware-полем
    return timezone.make_aware(moment) if timezone.is_naive(moment) else moment


def filter_requests(qs, params, user):
    """Фильтры журнала: статус, свои, просрочка, период регистрации, поиск.

    Общие для списка и выгрузки — иначе «экспортировать то, что на экране»
    однажды начнёт выгружать не то, что на экране.
    """
    status = params.get("status", "")
    if status == "active":
        qs = qs.exclude(status__in=[ServiceRequest.CLOSED, ServiceRequest.REJECTED])
    elif status in dict(ServiceRequest.STATUSES):
        qs = qs.filter(status=status)

    if params.get("provider"):
        qs = qs.filter(service_provider_id=params["provider"])

    if params.get("mine") in ("1", "true"):
        qs = qs.filter(initiator=user)

    if params.get("overdue") in ("1", "true"):
        # Незакрытая заявка просрочена, как только срок прошёл; закрытая — если акт позже срока
        qs = (
            qs.exclude(status=ServiceRequest.REJECTED)
            .filter(deadline_at__isnull=False)
            .filter(Q(closed_at__isnull=True, deadline_at__lt=timezone.now()) | Q(closed_at__gt=F("deadline_at")))
        )

    date_from = _filter_moment(params.get("date_from", ""))
    if date_from:
        qs = qs.filter(registered_at__gte=date_from)
    date_to = _filter_moment(params.get("date_to", ""))
    if date_to:
        qs = qs.filter(registered_at__lte=date_to)

    search = (params.get("q", "") or "").strip()
    if search:
        # Инициатор ищется и по склеенному ФИО: в журнале он показан именно так
        qs = qs.annotate(initiator_name=Concat("initiator__first_name", Value(" "), "initiator__last_name")).filter(
            Q(device__serial_number__icontains=search)
            | Q(device__address__icontains=search)
            | Q(device__organization__name__icontains=search)
            | Q(description__icontains=search)
            | Q(external_number__icontains=search)
            | Q(act_number__icontains=search)
            | Q(initiator_name__icontains=search)
            | Q(initiator__username__icontains=search)
            | Q(initiator_contacts__icontains=search)
        )

    return qs


@login_required
@require_GET
def api_service_requests(request):
    """Список заявок с фильтрами по статусу, просрочке, периоду и поиском."""
    qs = filter_requests(visible_requests(request.user), request.GET, request.user)

    per_page = int(request.GET.get("per_page", 50) or 50)
    if per_page not in PER_PAGE_CHOICES:
        per_page = 50

    paginator = Paginator(qs, per_page)
    page = paginator.get_page(request.GET.get("page", 1))

    return JsonResponse(
        {
            "requests": [_serialize(item) for item in page],
            "pagination": {
                "total_count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page.number,
                "per_page": per_page,
                "has_next": page.has_next(),
                "has_previous": page.has_previous(),
            },
        }
    )


@login_required
@require_GET
def api_service_requests_export(request):
    """Ставит в очередь выгрузку тех же заявок, что показывает журнал с текущими фильтрами.

    Годовой журнал собирается заметно дольше, чем живёт HTTP-запрос, поэтому
    файл делает воркер очереди exports, а фронт забирает его по task_id.
    """
    if not request.user.has_perm("contracts.export_service_requests"):
        raise PermissionDenied("Нет права выгружать журнал заявок")

    # QueryDict не переживёт сериализацию в брокер
    task = build_request_export_task.delay(request.user.pk, request.GET.dict())
    return JsonResponse(
        {"task_id": task.id, "download_url": reverse("contracts:api_requests_export_download", args=[task.id])},
        status=202,
    )


@login_required
@require_GET
def api_service_requests_export_download(request, task_id):
    """Отдаёт готовую выгрузку; пока воркер считает — 202, чтобы фронт опросил ещё раз."""
    from django.core.cache import cache

    payload = cache.get(f"{REQUEST_EXPORT_CACHE_PREFIX}{task_id}")
    if payload is None:
        if AsyncResult(task_id).failed():
            return JsonResponse({"error": "Не удалось сформировать выгрузку"}, status=500)
        return JsonResponse({"ready": False}, status=202)

    # Выборка зависит от прав заказчика, поэтому по чужому task_id файл не отдаём
    if payload["user_id"] != request.user.pk:
        raise PermissionDenied("Выгрузку заказывал другой пользователь")

    response = HttpResponse(b64decode(payload["content_b64"]), content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{payload["filename"]}"'
    return response


@login_required
@require_GET
def api_service_requests_analytics(request):
    """Сводка по тем же заявкам, что показывает журнал с текущими фильтрами."""
    qs = filter_requests(visible_requests(request.user), request.GET, request.user)
    return JsonResponse(build_analytics(qs))


def _get_for_update(request, pk):
    if not request.user.has_perm("contracts.close_service_request"):
        raise PermissionDenied("Нет права отмечать выполнение заявок")
    qs = ServiceRequest.objects.select_related("device__city").annotate(
        messages_total=Count("messages"),
        subscribed=Exists(ServiceRequestSubscription.objects.filter(service_request=OuterRef("pk"), user=request.user)),
        has_act_letter=_has_act_letter("pk"),
    )
    return get_object_or_404(qs, pk=pk)


def _parse_moment(raw, label):
    if not raw:
        return None
    moment = parse_datetime(raw)
    if moment is None:
        raise ValidationError(f"{label}: не разобрать дату «{raw}».")
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


@login_required
@require_POST
def api_service_request_restore(request, pk):
    """Отметка восстановления работоспособности — останавливает простой в K1."""
    service_request = _get_for_update(request, pk)

    try:
        restored_at = _parse_moment(request.POST.get("restored_at"), "Время восстановления") or timezone.now()
        provider_restored_at = _parse_moment(
            request.POST.get("provider_restored_at"), "Время восстановления по данным подрядчика"
        )
        provider_downtime = request.POST.get("provider_downtime_hours") or None

        mark_restored(
            service_request,
            restored_at,
            user=request.user,
            request=request,
            provider_restored_at=provider_restored_at,
            provider_downtime_hours=provider_downtime,
        )
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": "; ".join(exc.messages)}, status=400)

    return JsonResponse({"ok": True, "request": _serialize(service_request)})


@login_required
@require_POST
def api_service_request_act(request, pk):
    """Приём технического акта: закрывает заявку (п. 6.6.4 ТЗ)."""
    service_request = _get_for_update(request, pk)

    try:
        close_by_act(
            service_request,
            act_file=request.FILES.get("act_scan"),
            act_number=(request.POST.get("act_number", "") or "").strip(),
            closed_at=_parse_moment(request.POST.get("closed_at"), "Дата акта"),
            user=request.user,
            request=request,
        )
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": "; ".join(exc.messages)}, status=400)

    return JsonResponse({"ok": True, "request": _serialize(service_request)})


@login_required
@require_POST
def api_service_request_close_by_message(request, pk, message_id):
    """Закрытие заявки выбранным письмом: акт пришёл, но тема письма не формальная."""
    service_request = _get_for_update(request, pk)
    message = get_object_or_404(service_request.messages, pk=message_id)

    try:
        close_by_message(service_request, message, user=request.user, request=request)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": "; ".join(exc.messages)}, status=400)

    return JsonResponse({"ok": True, "request": _serialize(service_request)})


def _reply_addresses(service_request):
    """Белый список «Кому»: адреса из входящих писем плюс общий ящик подрядчика.

    Произвольный адрес не принимаем — авторизованный пользователь иначе получил бы
    отправку писем от имени сервис-деска кому угодно.
    """
    addresses = []
    for message in service_request.messages.all():
        if message.direction != ServiceRequestMessage.INCOMING:
            continue
        email = parseaddr(message.from_email)[1]
        if email and email not in addresses:
            addresses.append(email)
    addresses.reverse()  # последний ответивший — первым, он же адресат по умолчанию
    support = service_request.device.support_email
    if support and support not in addresses:
        addresses.append(support)
    return addresses


@login_required
@require_GET
def api_service_request_messages(request, pk):
    """Лента переписки по заявке."""
    service_request = get_object_or_404(visible_requests(request.user), pk=pk)
    messages = service_request.messages.prefetch_related("attachments")

    # Лента открыта — уведомления по этой заявке больше не новость
    mark_target_read(request.user, target_key(service_request))

    # Саму заявку отдаём вместе с лентой: по ссылке из уведомления её может не быть
    # на текущей странице журнала, а шапке ленты нужны номер и состояние подписки.
    return JsonResponse(
        {
            "request": _serialize(service_request),
            "messages": [_serialize_message(message) for message in messages],
            "reply_options": _reply_addresses(service_request),
        }
    )


@login_required
@require_GET
def api_reply_colleagues(request):
    """Коллеги с почтой — кандидаты в копию письма подрядчику."""
    if not (
        request.user.has_perm("contracts.view_servicerequest")
        or request.user.has_perm("contracts.create_service_request")
    ):
        raise PermissionDenied("Нет доступа к журналу заявок")

    users = (
        get_user_model()
        .objects.filter(is_active=True)
        .exclude(email="")
        .exclude(pk=request.user.pk)
        .order_by("last_name", "first_name", "username")
    )
    return JsonResponse(
        {"colleagues": [{"name": user.get_full_name() or user.username, "email": user.email} for user in users]}
    )


@login_required
@require_POST
def api_service_request_subscribe(request, pk):
    """Подписка на заявку: следить за ответами подрядчика в колокольчике."""
    service_request = get_object_or_404(visible_requests(request.user), pk=pk)

    if request.POST.get("on") in ("1", "true"):
        ServiceRequestSubscription.objects.get_or_create(user=request.user, service_request=service_request)
        subscribed = True
    else:
        ServiceRequestSubscription.objects.filter(user=request.user, service_request=service_request).delete()
        subscribed = False

    return JsonResponse({"ok": True, "subscribed": subscribed})


MAX_REPLY_ATTACHMENT_SIZE = 20 * 1024 * 1024


@login_required
@require_POST
def api_service_request_reply(request, pk):
    """Ответ подрядчику из ленты — уходит в ту же переписку, что и заявка."""
    service_request = get_object_or_404(visible_requests(request.user), pk=pk)

    text = (request.POST.get("text", "") or "").strip()
    attachments = request.FILES.getlist("attachments")
    if not text and not attachments:
        return JsonResponse({"ok": False, "error": "Письмо без текста и вложений отправлять нечего."}, status=400)

    oversized = [upload.name for upload in attachments if upload.size > MAX_REPLY_ATTACHMENT_SIZE]
    if oversized:
        limit = MAX_REPLY_ATTACHMENT_SIZE // 1024 // 1024
        return JsonResponse({"ok": False, "error": f"Файл больше {limit} МБ: {', '.join(oversized)}."}, status=400)

    to_email = (request.POST.get("to", "") or "").strip()
    if to_email and to_email not in _reply_addresses(service_request):
        return JsonResponse({"ok": False, "error": "Адрес не из переписки по этой заявке."}, status=400)

    # В копию — только почта коллег из системы: произвольные адреса превратили бы
    # форму в отправку писем от имени сервис-деска кому угодно
    cc_emails = [value.strip() for value in request.POST.getlist("cc") if value.strip()]
    if cc_emails:
        known = set(
            get_user_model().objects.filter(is_active=True, email__in=cc_emails).values_list("email", flat=True)
        )
        strangers = [email for email in cc_emails if email not in known]
        if strangers:
            return JsonResponse({"ok": False, "error": f"Не сотрудники системы: {', '.join(strangers)}."}, status=400)

    try:
        channel = channel_for_device(service_request.device)
        message = channel.reply(service_request, text, attachments, user=request.user, to_email=to_email, cc=cc_emails)
    except SubmissionError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=exc.status)

    # Коллеги-подписчики видят комментарий в колокольчике; автору он не новость
    notify_subscribers(message, author=request.user)
    return JsonResponse({"ok": True, "message": _serialize_message(message)})


@login_required
@require_GET
def api_unmatched_messages(request):
    """Письма, в которых не нашлось номера заявки — их привязывают руками."""
    if not request.user.has_perm("contracts.view_servicerequest"):
        raise PermissionDenied("Нет доступа к непривязанным письмам")

    messages = ServiceRequestMessage.objects.filter(service_request__isnull=True).prefetch_related("attachments")
    return JsonResponse({"messages": [_serialize_message(message) for message in messages]})


@login_required
@require_GET
def api_unmatched_okdesk_issues(request):
    """Открытые заявки Okdesk без устройства в договоре — они выпадают из журнала.

    Устройство привязывается по серийнику (auto_link + синк Okdesk), поэтому лечится
    исправлением серийника в договоре или в самой заявке Okdesk.
    """
    if not request.user.has_perm("contracts.view_servicerequest"):
        raise PermissionDenied("Нет доступа к заявкам Okdesk")

    from django.conf import settings

    from integrations.models import OkdeskIssue

    from .services_okdesk_import import CLOSED_STATUS_NAMES

    web_root = settings.OKDESK_API_URL.split("/api/")[0]
    # Заведённые в журнал вручную не показываем: их номер уже в ServiceRequest,
    # хотя строка зеркала так и осталась без устройства
    in_journal = ServiceRequest.objects.exclude(external_number="").values_list("external_number", flat=True)
    issues = (
        OkdeskIssue.objects.filter(contract_device__isnull=True)
        .exclude(status_name__in=CLOSED_STATUS_NAMES)
        .exclude(issue_id__in=[int(number) for number in in_journal if number.isdigit()])
        .order_by("-created_at")
    )
    seen = set()
    payload = []
    for issue in issues:
        if issue.issue_id in seen:
            continue
        seen.add(issue.issue_id)
        payload.append(
            {
                "issue_id": issue.issue_id,
                "title": issue.title,
                "status": issue.status_name,
                "company": issue.company_name,
                "serial_numbers": issue.serial_numbers,
                "author": issue.author_name,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "url": f"{web_root}/issues/{issue.issue_id}",
            }
        )
    return JsonResponse({"issues": payload})


@login_required
@require_GET
def api_okdesk_device_search(request):
    """Подбор устройства для ручного ввода заявки Okdesk в журнал."""
    if not request.user.has_perm("contracts.close_service_request"):
        raise PermissionDenied("Нет права заводить заявки Okdesk в журнал")

    from .models import ContractDevice

    q = (request.GET.get("q", "") or "").strip()
    if len(q) < 2:
        return JsonResponse({"devices": []})

    devices = (
        ContractDevice.objects.filter(
            Q(serial_number__icontains=q)
            | Q(address__icontains=q)
            | Q(organization__name__icontains=q)
            | Q(city__name__icontains=q)
        )
        .select_related("organization", "city", "model__manufacturer")
        .order_by("serial_number")[:10]
    )
    return JsonResponse(
        {
            "devices": [
                {
                    "id": device.pk,
                    "serial_number": device.serial_number,
                    "model": str(device.model) if device.model_id else "",
                    "organization": device.organization.name if device.organization_id else "",
                    "city": device.city.name if device.city_id else "",
                    "address": device.address,
                }
                for device in devices
            ]
        }
    )


@login_required
@require_POST
def api_okdesk_issue_import(request, issue_id):
    """Ручной ввод заявки Okdesk без устройства в журнал: связь живёт в журнале, не в зеркале."""
    if not request.user.has_perm("contracts.close_service_request"):
        raise PermissionDenied("Нет права заводить заявки Okdesk в журнал")

    import requests as http

    from integrations.models import OkdeskIssue

    from .models import ContractDevice
    from .services_okdesk_import import import_issue_with_device

    device_id = request.POST.get("device_id", "")
    device = get_object_or_404(ContractDevice, pk=device_id) if device_id.isdigit() else None
    if device is None:
        return JsonResponse({"ok": False, "error": "Устройство не выбрано."}, status=400)

    try:
        service_request = import_issue_with_device(issue_id, device)
    except OkdeskIssue.DoesNotExist:
        return JsonResponse({"ok": False, "error": f"Заявка {issue_id} не найдена в зеркале Okdesk."}, status=404)
    except http.RequestException as exc:
        logger.warning("Ручной ввод заявки Okdesk %s не удался: %s", issue_id, exc)
        return JsonResponse({"ok": False, "error": "Okdesk недоступен, попробуйте позже."}, status=502)

    logger.info(
        "Заявка Okdesk %s заведена в журнал как %s (устройство %s) пользователем %s",
        issue_id,
        service_request.number,
        device.serial_number or device.pk,
        request.user,
    )
    return JsonResponse({"ok": True, "request": {"id": service_request.pk, "number": service_request.number}})


@login_required
@require_POST
def api_message_attach(request, pk):
    """Привязывает письмо к заявке по её номеру."""
    if not request.user.has_perm("contracts.close_service_request"):
        raise PermissionDenied("Нет права привязывать письма к заявкам")

    message = get_object_or_404(ServiceRequestMessage, pk=pk)
    number = (request.POST.get("number", "") or "").strip()

    # Номер выводится из id заявки, поэтому ищем по нему и сверяем строку целиком:
    # так опечатка в годе не привяжет письмо к чужой заявке.
    _, _, raw_pk = number.partition("-")
    service_request = ServiceRequest.objects.filter(pk=raw_pk).first() if raw_pk.isdigit() else None
    if service_request is None or service_request.number != number:
        return JsonResponse({"ok": False, "error": f"Заявка № {number} не найдена."}, status=404)

    message.service_request = service_request
    message.save(update_fields=["service_request"])
    logger.info("Письмо %s привязано к заявке %s пользователем %s", message.pk, number, request.user)

    # Формальное письмо без нашего номера в теме закрывает заявку только сейчас,
    # когда стало понятно, к какой именно оно относится.
    closed = close_by_letter(service_request, message)
    notify_subscribers(message)

    return JsonResponse({"ok": True, "closed_by_letter": closed})


@login_required
@require_POST
def api_attachment_fetch(request, pk):
    """Докачивает файл вложения Okdesk, от которого сохранены только метаданные."""
    attachment = get_object_or_404(ServiceRequestAttachment.objects.select_related("message__service_request"), pk=pk)
    initiator_id = attachment.message.service_request.initiator_id if attachment.message.service_request_id else None
    if not (request.user.has_perm("contracts.view_servicerequest") or initiator_id == request.user.pk):
        raise PermissionDenied("Нет доступа к вложениям переписки")

    if attachment.file:
        return JsonResponse({"ok": True, "url": attachment.file.url})

    try:
        downloaded = download_attachment_file(attachment)
    except requests.RequestException as exc:
        logger.warning("Вложение %s не скачано: %s", pk, mask_api_token(exc))
        return JsonResponse({"ok": False, "error": "Хранилище файлов Okdesk недоступно."}, status=502)

    if not downloaded:
        return JsonResponse({"ok": False, "error": "Okdesk не отдал ссылку на файл."}, status=502)

    return JsonResponse({"ok": True, "url": attachment.file.url, "size": attachment.size})
