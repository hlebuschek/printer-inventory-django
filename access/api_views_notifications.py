"""API колокольчика: непрочитанное, история и отметка прочтения."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Notification

HISTORY_LIMIT = 50


def _serialize(notification):
    return {
        "id": notification.pk,
        "kind": notification.kind,
        "title": notification.title,
        "subtitle": notification.subtitle,
        "url": notification.url,
        "created_at": notification.created_at.isoformat(),
        "read": notification.read_at is not None,
    }


@login_required
@require_GET
def notifications_api(request):
    """Непрочитанные уведомления, а с `history=1` — ещё и прочитанные."""
    qs = Notification.objects.filter(user=request.user)
    unread_count = qs.filter(read_at__isnull=True).count()

    if request.GET.get("history") not in ("1", "true"):
        qs = qs.filter(read_at__isnull=True)

    return JsonResponse({"unread_count": unread_count, "items": [_serialize(item) for item in qs[:HISTORY_LIMIT]]})


@login_required
@require_POST
def notification_read_api(request, pk):
    """Отметка одного уведомления — остальные остаются непрочитанными."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])

    return JsonResponse({"ok": True, "notification": _serialize(notification)})


@login_required
@require_POST
def notifications_read_all_api(request):
    """Разобрать колокольчик целиком — история при этом никуда не девается."""
    marked = Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"ok": True, "marked": marked})
