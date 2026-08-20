"""Отдача сканов технических актов и вложений из переписки с подрядчиком.

MEDIA не раздаётся веб-сервером: акт — документ, которым обосновываются
показатели K1/K2 и оплата, поэтому ссылка не должна открываться без прав.
Файл ищется по записи журнала, так что имя из URL в файловую систему не попадает.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from .models import ServiceRequest, ServiceRequestAttachment


@login_required
@require_GET
def serve_service_act(request, path):
    service_request = ServiceRequest.objects.filter(act_scan=f"service-acts/{path}").first()
    if service_request is None:
        raise Http404("Скан акта не найден")

    if not (request.user.has_perm("contracts.view_servicerequest") or service_request.initiator_id == request.user.pk):
        raise PermissionDenied("Нет доступа к сканам актов")

    return FileResponse(service_request.act_scan.open("rb"), filename=service_request.act_scan.name.rsplit("/", 1)[-1])


@login_required
@require_GET
def serve_service_mail_attachment(request, path):
    """Вложение письма. Непривязанное письмо видно только тем, кому открыт весь журнал."""
    attachment = (
        ServiceRequestAttachment.objects.filter(file=f"service-mail/{path}")
        .select_related("message__service_request")
        .first()
    )
    if attachment is None:
        raise Http404("Вложение не найдено")

    initiator_id = attachment.message.service_request.initiator_id if attachment.message.service_request_id else None
    if not (request.user.has_perm("contracts.view_servicerequest") or initiator_id == request.user.pk):
        raise PermissionDenied("Нет доступа к вложениям переписки")

    return FileResponse(attachment.file.open("rb"), filename=attachment.filename)
