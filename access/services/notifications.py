"""Создание уведомлений. Источники зовут `notify()`, колокольчик о них не знает."""

from django.utils import timezone

from ..models import Notification


def notify(users, *, kind, title, subtitle="", url="", target_key="", event_key=""):
    """Кладёт уведомление каждому из users. Повтор того же события молча пропускается."""
    recipients = [user for user in users if user is not None]
    if not recipients:
        return

    # ignore_conflicts не проставляет pk созданным строкам, поэтому ничего не возвращаем
    Notification.objects.bulk_create(
        [
            Notification(
                user=user,
                kind=kind,
                title=title[:200],
                subtitle=subtitle[:300],
                url=url[:500],
                target_key=target_key,
                event_key=event_key,
            )
            for user in recipients
        ],
        ignore_conflicts=True,
    )


def mark_target_read(user, target_key):
    """Человек открыл сам объект — уведомления по нему больше не новость."""
    return Notification.objects.filter(user=user, target_key=target_key, read_at__isnull=True).update(
        read_at=timezone.now()
    )
