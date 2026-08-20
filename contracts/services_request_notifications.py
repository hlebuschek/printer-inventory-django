"""Уведомления подписчикам заявки о входящих сообщениях подрядчика."""

from access.models import Notification
from access.services.notifications import notify

from .models import ServiceRequestMessage


def target_key(service_request):
    """Ключ, по которому открытая лента гасит все уведомления этой заявки."""
    return f"contracts.servicerequest:{service_request.pk}"


def notify_subscribers(message, *, author=None):
    """Зовётся, когда сообщение оказалось в ленте заявки.

    Входящее — ответ подрядчика, его получают все подписчики. Исходящее —
    комментарий коллеги: подписчики должны узнать о нём, а сам автор — нет.
    """
    if message.service_request_id is None:
        return

    service_request = message.service_request
    if message.direction == ServiceRequestMessage.INCOMING:
        title = f"Ответ по заявке {service_request.number}"
        subtitle = message.subject or message.body_text[:300]
    else:
        name = (author.get_full_name() or author.username) if author else "Коллега"
        title = f"Письмо по заявке {service_request.number}"
        subtitle = f"{name}: {message.body_text[:250]}"

    notify(
        [
            subscription.user
            for subscription in service_request.subscriptions.select_related("user")
            if subscription.user != author
        ],
        kind=Notification.SERVICE_REQUEST_REPLY,
        title=title,
        subtitle=subtitle,
        url=f"/contracts/requests/?request={service_request.pk}",
        target_key=target_key(service_request),
        event_key=f"contracts.servicerequestmessage:{message.pk}",
    )
